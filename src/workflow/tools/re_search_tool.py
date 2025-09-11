import re
import json


async def re_search(
    pattern: str,
    txt: str,
    max_results: int = 10,
    context_chars: int = 200
) -> str:
    """
    通用正则表达式文本搜索工具
    
    按段落进行匹配，避免跨段落的无意义匹配
    
    Args:
        pattern: 正则表达式搜索模式
        txt: 要搜索的文本内容
        max_results: 返回结果的最大数量
        context_chars: 匹配结果前后显示的字符数
    """
    
    result = {
        "query": pattern,
        "results_counts": 0,
        "results": [],
        "info": None
    }
    
    try:
        # 编译正则表达式，使用DOTALL标志让.匹配换行符
        regex = re.compile(pattern, re.DOTALL)
        
        # 如果文本为空，返回相应提示
        if not txt:
            result["info"] = "[warning]文本为空，无法进行搜索"
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        # 收集所有匹配结果
        matches = []
        
        # 按行分割，但允许跨上下两行匹配
        lines = txt.split('\n')
        total_lines = len(lines)
        
        # 使用finditer找到所有匹配，然后按三行窗口过滤
        all_matches = []
        
        # 构建三行窗口，收集所有可能的匹配
        for line_idx in range(total_lines):
            window_start = max(0, line_idx - 1)
            window_end = min(total_lines, line_idx + 2)
            three_lines = '\n'.join(lines[window_start:window_end])
            
            # 在三行窗口中查找匹配
            for match in regex.finditer(three_lines):
                # 计算三行窗口在全文中的起始位置
                window_start_pos = 0
                for i in range(window_start):
                    window_start_pos += len(lines[i]) + 1
                
                # 计算匹配在全文中的绝对位置
                global_start = window_start_pos + match.start()
                global_end = window_start_pos + match.end()
                
                # 计算匹配的主要行号（匹配开始位置所在行）
                match_line = txt[:global_start].count('\n')
                
                all_matches.append({
                    'global_start': global_start,
                    'global_end': global_end,
                    'match_line': match_line,
                    'match_obj': match
                })
        
        # 去重：相同位置的匹配只保留一个
        unique_matches = {}
        for match_info in all_matches:
            key = (match_info['global_start'], match_info['global_end'])
            if key not in unique_matches:
                unique_matches[key] = match_info
        
        # 处理去重后的匹配结果
        for match_info in unique_matches.values():
            global_start = match_info['global_start']
            global_end = match_info['global_end']
            match_line = match_info['match_line']
            
            # 在全文中提取前后指定字符数
            context_start = max(0, global_start - context_chars)
            context_end = min(len(txt), global_end + context_chars)
            
            prefix = "[前文省略]..." if context_start > 0 else ""
            suffix = "...[后文省略]" if context_end < len(txt) else ""
            context = prefix + txt[context_start:context_end] + suffix
            
            # 计算位置到文本末尾的行数
            lines_from_end = total_lines - match_line - 1
            
            matches.append({
                "content": context,
                "loc": f"{lines_from_end}行以前"
            })
        
        # 按照文本中的出现顺序排列（最旧的最靠上）
        matches.sort(key=lambda x: int(x["loc"].replace("行以前", "")), reverse=True)
        
        # 设置结果
        result["results_counts"] = len(matches)
        result["results"] = matches[:max_results]
        
        # 设置info信息
        if len(matches) > max_results:
            result["info"] = "[warning]匹配内容过多请精细搜索条件"
        else:
            result["info"] = f"[info]匹配成功，匹配到{len(matches)}个结果"
    
    except re.error as e:
        result["info"] = f"[error]正则表达式错误: {str(e)}"
    except Exception as e:
        result["info"] = f"[error]搜索出错: {str(e)}"
    
    return json.dumps(result, ensure_ascii=False, indent=2)



def messages_to_txt(messages: list[dict]) -> str:
    """
    将 OpenAI 格式的 messages 转换为纯文本格式
    
    Args:
        messages: OpenAI 格式的消息列表，每个元素包含 role 和 content 字段
        
    Returns:
        转换后的纯文本字符串，不同消息间用双换行符分隔
        
    Example:
        messages = [
            {"role": "system", "content": "123"},
            {"role": "assistant", "content": "456"},
            {"role": "user", "content": "789"}
        ]
        
        result = messages_to_txt(messages)
        # 输出:
        # system:123
        # 
        # assistant:456
        # 
        # user:789
    """
    if not messages:
        return ""
    
    text_parts = []
    
    for message in messages:
        role = message.get("role", "unknown")
        content = message.get("content", "")
        
        # 格式化为 "role:content"
        text_parts.append(f"{role}:{content}")
    
    # 用双换行符连接所有消息
    return "\n\n".join(text_parts)


def create_re_search_tool(search_text: str) -> dict:
    """
    创建一个预配置的正则搜索工具，用于OpenAI函数调用
    
    严格限制工具使用方式：
    - 禁止: (A|B|C|D|E) 这种单纯多词组合，会返回无关联的大量结果
    - 必须: (A|B).*?(C|D)|(C|D).*?(A|B) 这种关联搜索，找实体间关系，注意， (A|B)中A和B是指向同一实体的不同称呼，(C|D)同理。
    
    Args:
        search_text: 要搜索的文本内容
        
    Returns:
        dict: 包含function和schema的工具配置字典
    """
    async def search_in_text(pattern: str, max_results: int = 10) -> str:
        """在预配置的文本中搜索匹配正则表达式的内容"""
        return await re_search(pattern, search_text, max_results, context_chars=200)
    
    # OpenAI 函数调用 schema 定义
    search_schema = {
        "type": "function",
        "function": {
            "name": "search_in_text",
            "description": """搜索实体间关联内容的专用工具，严格要求使用关联搜索模式。

使用场景：
- 搜索实体关联：必须查找两个或多个实体间的具体关系和互动
- 追溯关联历史：在对话历史中查找实体间的相关背景和联系
- 严格禁止：1.单纯罗列词汇、无关联的内容探索、当前对话已明确的信息。2.过大的max_results
- 注意：该工具非常强大！可以在自带的历史库内进行搜索！请充分使用！

返回：匹配内容及前后200字符上下文、位置信息""",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": """【严格禁止】单词组合如 (长谷川结衣|结衣|Chiye|健司|换鞋凳) - 这会返回过多无关数据！

【必须使用】正则表达式搜索模式，强制使用关联搜索：

正确示例：
  "(张三|老张).*?(剑|武器)|(剑|武器).*?(张三|老张)"
  "(林黛玉|林妹妹).*?(宝玉|宝二爷)|(宝玉|宝二爷).*?(林黛玉|林妹妹)"
  "(结衣|长谷川).*?(健司|家)|(健司|家).*?(结衣|长谷川)"
  
注意， (A|B)中A和B是指向同一实体的不同称呼，(C|D)同理。

错误示例：
  "(长谷川结衣|结衣|Chiye|健司|换鞋凳|居家服)" - 禁止！
  "(角色|物品|地点)" - 禁止！

核心规则：必须使用 .*? 连接实体，进行双向关联搜索 A.*?B|B.*?A"""
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回结果的最大数量，范围1-100，一般来说5是一个合适的数字，因为本工具鼓励通过精确搜索来降低返回数量。只有极端情况下才允许超过10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["pattern"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
    
    return {
        "function": search_in_text,
        "schema": search_schema
    }


# 为了方便直接使用，也可以单独导出
__all__ = ["re_search", "messages_to_txt", "create_re_search_tool"]