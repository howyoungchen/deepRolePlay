"""
消息处理工具函数

提供各种消息列表处理的工具函数
"""
from typing import List, Dict, Any
from config.manager import settings


def inject_scenario(messages: List[Dict[str, Any]], scenario_content: str) -> List[Dict[str, Any]]:
    """
    将情景内容注入到消息列表中，并根据max_history_length裁剪历史消息
    
    Args:
        messages: 原始消息列表
        scenario_content: 情景内容
        
    Returns:
        注入情景后的消息列表
    """
    if not messages:
        return messages
    
    # 复制消息列表避免修改原始数据
    processed_messages = messages.copy()
    
    # 1. 分离system消息和其他消息
    system_messages = []
    other_messages = []
    
    for msg in processed_messages:
        if msg.get("role") == "system":
            system_messages.append(msg)
        else:
            other_messages.append(msg)
    
    # 2. 根据max_history_length裁剪消息
    max_history_length = settings.langgraph.max_history_length
    
    if max_history_length > 0:
        # 从后往前计数AI消息
        ai_message_count = 0
        cutoff_index = 0  # 默认从开头保留所有消息
        
        for i in range(len(other_messages) - 1, -1, -1):
            if other_messages[i].get("role") == "assistant":
                ai_message_count += 1
                if ai_message_count >= max_history_length:
                    # 找到第max_history_length条AI消息，从这里开始保留
                    cutoff_index = i
                    break
        
        # 只有当找到足够的AI消息时才进行裁剪
        if ai_message_count >= max_history_length:
            other_messages = other_messages[cutoff_index:]
    
    # 3. 重新组合消息：system消息 + 裁剪后的其他消息
    injected_messages = system_messages + other_messages
    
    # 4. 在最后一个用户消息中注入情景内容
    if scenario_content and scenario_content.strip():
        # 查找最后一个用户消息并在其内容开头插入情景
        for i in range(len(injected_messages) - 1, -1, -1):
            message = injected_messages[i]
            if message.get("role") == "user":
                # 在用户消息内容开头加上情景
                original_content = message.get("content", "")
                new_content = f"<当前情景>\n{scenario_content}\n</当前情景>\n\n{original_content}"
                
                # 创建新的消息对象
                injected_messages[i] = {
                    **message,  # 保持其他字段不变
                    "content": new_content
                }
                break
    
    return injected_messages