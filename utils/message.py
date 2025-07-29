"""
消息处理工具函数
用于情景注入和历史记录提取
"""
from typing import List, Dict, Any


def inject_scenario(messages: List[Dict[str, Any]], scenario_content: str) -> List[Dict[str, Any]]:
    """
    将情景内容注入到消息列表中
    
    Args:
        messages: 原始消息列表
        scenario_content: 情景内容
        
    Returns:
        注入情景后的消息列表
    """
    if not scenario_content or not scenario_content.strip():
        return messages
    
    # 复制消息列表避免修改原始数据
    injected_messages = messages.copy()
    
    # 查找第一个用户消息并在前面插入情景
    for i, message in enumerate(injected_messages):
        if message.get("role") == "user":
            # 在用户消息内容前加上情景
            original_content = message.get("content", "")
            new_content = f"【情景背景】\n{scenario_content}\n\n【用户消息】\n{original_content}"
            
            # 创建新的消息对象
            injected_messages[i] = {
                **message,  # 保持其他字段不变
                "content": new_content
            }
            break
    
    return injected_messages


def extract_history(messages: List[Dict[str, Any]], max_history_length: int = 20) -> List[Dict[str, Any]]:
    """
    从请求消息中提取对话历史
    
    Args:
        messages: 消息列表
        max_history_length: 最大历史长度
        
    Returns:
        提取的历史记录列表
    """
    if not messages:
        return []
    
    # 限制历史长度
    if len(messages) > max_history_length:
        # 保留最新的消息
        history = messages[-max_history_length:]
    else:
        history = messages.copy()
    
    # 过滤掉包含情景注入的消息，还原原始用户消息
    clean_history = []
    for message in history:
        if message.get("role") == "user":
            content = message.get("content", "")
            # 如果是注入了情景的消息，提取原始用户消息
            if "【情景背景】" in content and "【用户消息】" in content:
                # 提取用户消息部分
                parts = content.split("【用户消息】\n", 1)
                if len(parts) == 2:
                    clean_content = parts[1]
                    clean_history.append({
                        **message,
                        "content": clean_content
                    })
                else:
                    clean_history.append(message)
            else:
                clean_history.append(message)
        else:
            clean_history.append(message)
    
    return clean_history


def format_history_for_analysis(messages: List[Dict[str, Any]]) -> str:
    """
    将消息历史格式化为用于分析的文本
    
    Args:
        messages: 消息列表
        
    Returns:
        格式化的历史文本
    """
    if not messages:
        return "暂无对话历史"
    
    formatted_lines = []
    for i, message in enumerate(messages, 1):
        role = message.get("role", "unknown")
        content = message.get("content", "")
        
        role_name = {
            "system": "系统",
            "user": "用户", 
            "assistant": "助手"
        }.get(role, role)
        
        formatted_lines.append(f"{i}. {role_name}: {content}")
    
    return "\n".join(formatted_lines)


def create_scenario_summary_request(history: List[Dict[str, Any]]) -> str:
    """
    创建情景摘要生成请求
    
    Args:
        history: 对话历史
        
    Returns:
        情景摘要生成请求文本
    """
    history_text = format_history_for_analysis(history)
    
    request_text = f"""请分析以下对话历史，生成一个简洁的情景文件摘要。
    
对话历史：
{history_text}

请总结：
1. 对话的主要角色和身份设定
2. 当前的情境和背景
3. 重要的情节发展
4. 需要记住的关键信息

请以简洁明了的文本形式输出，适合作为下次对话的背景情景。文本长度控制在200-500字之间。
直接输出情景内容，不需要额外的格式说明。"""

    return request_text