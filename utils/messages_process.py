"""
消息处理工具函数

提供各种消息列表处理的工具函数
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