import re
import json
from langchain_core.tools import tool
from src.workflow.context.history_manager import get_conversation_history


@tool
def re_search(
    pattern: str,
    reverse: bool = False,
    max_results: int = 10
) -> str:
    """用于在对话历史中进行记忆搜索和信息回溯的正则表达式搜索工具。
    
    这个工具模拟人脑的记忆检索机制，通过正则表达式在历史对话中搜索相关的段落片段。
    支持从简单的关键词搜索到复杂的模式匹配，帮助构建完整的记忆画面。
    
    何时使用此工具：
    - 需要回溯某个人物、物品或事件的历史信息
    - 搜索特定概念或主题在对话中的所有提及
    - 寻找相关联的记忆片段来理解当前情境
    - 验证或补充对某个实体的认知
    - 构建时间线或关系网络
    - 需要精确定位包含特定模式的对话片段
    
    主要特性：
    - 支持简单关键词和复杂正则表达式
    - 段落级别的精确匹配（以双换行符分割）
    - 灵活的结果排序（最新优先或最旧优先）
    - 自动截取结果避免信息过载
    - 位置追踪显示记忆的时间远近
    - 完整的错误处理和状态反馈
    
    搜索策略建议：
    1. 优先使用多实体联合搜索，如"实体1.*?实体2|实体2.*?实体1"
    2. 单实体搜索往往结果过多且缺乏语境，应谨慎使用
    3. 使用.*?（非贪婪匹配）连接相关实体，捕获它们的关联语境
    4. 利用|符号构建双向搜索模式，确保不遗漏任何组合
    5. 示例："实体1.*?实体2|实体2.*?实体1"比单独搜索"实体2"更有效
    
    Args:
        pattern: 正则表达式模式字符串。建议使用多实体联合搜索获得更精确的语境。
                示例: "实体1.*?实体2|实体2.*?实体1", "人物.*?职业.*?概念", "实体A.*?实体B|实体B.*?实体A"
        reverse: 控制结果排序。False(默认)表示最新的在前(loc降序)，True表示最旧的在前(loc升序)。
                大多数记忆系统优先显示近期内容。
        max_results: 返回的最大结果数量，默认10。更高的值可能提供更多上下文，但可能影响处理效率。
    
    Returns:
        包含搜索结果的JSON字符串，结构如下：
        - query: 搜索使用的正则表达式模式
        - results_counts: 找到的匹配段落总数
        - results: 匹配对象数组，每个包含：
          * content: 完整的匹配段落文本
          * loc: 匹配到段落所在对话的倒序位置(数值越大越早，数值越小越近)
        - info: 状态信息，格式为[级别]消息：
          * [info] 成功搜索时显示匹配数量
          * [warning] 结果超过max_results时提示（建议精简模式）
          * [error] 正则表达式错误或文件访问问题
    """
    
    result = {
        "query": pattern,
        "results_counts": 0,
        "results": [],
        "info": None
    }
    
    try:
        # 编译正则表达式
        regex = re.compile(pattern)
        
        # 从全局状态获取对话历史
        messages = get_conversation_history()
        
        # 如果对话历史为空，返回相应提示
        if not messages:
            result["info"] = "[warning]对话历史为空，无法进行搜索"
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        # 收集所有匹配结果
        matches = []
        total_messages = len(messages)
        
        for idx, msg in enumerate(messages):
            # 计算倒数位置（从1开始）
            loc = total_messages - idx
            
            # 将content按段落分割
            paragraphs = msg["content"].split("\n\n")
            
            # 在每个段落中搜索
            for para in paragraphs:
                if regex.search(para):
                    matches.append({
                        "content": para,
                        "loc": loc
                    })
        
        # 排序处理
        if reverse:
            # 正序：按loc升序（最旧的在前）
            matches.sort(key=lambda x: x["loc"])
        else:
            # 倒序：按loc降序（最新的在前）
            matches.sort(key=lambda x: x["loc"], reverse=True)
        
        # 设置结果
        result["results_counts"] = len(matches)
        result["results"] = matches[:max_results]
        
        # 设置info信息
        if len(matches) > max_results:
            result["info"] = "[warning]匹配内容过多请精简匹配词"
        else:
            result["info"] = f"[info]匹配成功，匹配到{len(matches)}个结果"
    
    except re.error as e:
        result["info"] = f"[error]正则表达式错误: {str(e)}"
    except FileNotFoundError:
        result["info"] = "[error]搜索出错: 找不到消息数据文件"
    except Exception as e:
        result["info"] = f"[error]搜索出错: {str(e)}"
    
    return json.dumps(result, ensure_ascii=False, indent=2)