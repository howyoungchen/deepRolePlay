"""
消息处理工具函数

提供用于处理消息列表的各类工具函数
"""
from typing import List, Dict, Any
from config.manager import settings


def auto_find_ai_message_index(messages: List[Dict[str, Any]]) -> int:
    """
    从消息列表的尾部开始，查找第一个内容长度大于配置阈值的AI消息，返回其倒数索引
    只检查最近5个AI消息，避免消耗过多算力
    
    Args:
        messages: 消息列表
        
    Returns:
        倒数索引值 (1=最后一个AI消息, 2=倒数第二个, 以此类推)
        如果没找到符合条件的AI消息，返回1
    """
    # 从消息尾部开始遍历，边找边检查，最多检查5个AI消息
    ai_count = 0
    
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            ai_count += 1
            content = msg.get("content", "")
            if len(content) > settings.langgraph.ai_message_min_length:
                # 找到第一个符合条件的，直接返回倒数索引
                return ai_count
            if ai_count >= 5:  # 已检查5个AI消息，停止
                break
    
    # 如果检查了AI消息但都不符合条件，或者没有AI消息
    # 如果没找到符合条件的，回退到最后一个AI消息
    return 1


def inject_scenario(messages: List[Dict[str, Any]], scenario_content: str) -> List[Dict[str, Any]]:
    """
    将场景内容注入消息列表，并根据 max_history_length 裁剪历史消息。

    Args:
        messages: 原始消息列表。
        scenario_content: 场景内容。

    Returns:
        注入场景后的消息列表。
    """
    if not messages:
        return messages
    
    # 复制消息列表，避免修改原始数据
    processed_messages = messages.copy()
    
    # 1. 将系统消息与其他消息分离
    # 兼容性处理：有些模型的系统提示可能放在第一条 user 角色消息中
    system_messages = []
    other_messages = []
    
    # 标记是否为第一条消息
    is_first = True
    for msg in processed_messages:
        # 若为第一条且角色为 user，或角色为 system，则视为系统消息
        if (is_first and msg.get("role") == "user") or msg.get("role") == "system":
            system_messages.append(msg)
        else:
            other_messages.append(msg)
        is_first = False
    
    # 2. 统一进行场景注入与历史裁剪
    max_history_length = settings.langgraph.max_history_length
    last_ai_messages_index = settings.langgraph.last_ai_messages_index
    
    # 如果配置为-1，自动查找第一个内容长度>配置阈值的AI消息索引
    if last_ai_messages_index == -1:
        last_ai_messages_index = auto_find_ai_message_index(processed_messages)
    
    # 查找目标 user 位置并应用历史裁剪
    target_user_position = -1
    user_count = 0
    
    # 第一遍：找到目标 user 位置（倒数第 last_ai_messages_index 个 user）
    for i in range(len(other_messages) - 1, -1, -1):
        if other_messages[i].get("role") == "user":
            user_count += 1
            if user_count == last_ai_messages_index:
                target_user_position = i
                break
    
    # 若找到目标且 max_history_length > 0，则进行历史裁剪
    if target_user_position >= 0 and max_history_length > 0:
        # 从目标位置向前统计，寻找第 max_history_length 个完整的 AI 回复边界
        ai_count = 0
        cutoff_index = 0
        
        # 在目标位置之前统计 AI 消息数量以决定截断点
        for i in range(target_user_position - 1, -1, -1):
            if other_messages[i].get("role") == "assistant":
                ai_count += 1
                if ai_count >= max_history_length:
                    # 该条 AI 消息为第 max_history_length 条，从这里开始保留
                    cutoff_index = i
                    break
        
        # 应用历史裁剪
        if ai_count >= max_history_length and cutoff_index > 0:
            other_messages = other_messages[cutoff_index:]
            # 裁剪后更新目标 user 位置
            target_user_position = target_user_position - cutoff_index
    
    # 将场景注入到目标 user 消息
    scenario_injected = False
    if target_user_position >= 0 and scenario_content and scenario_content.strip():
        original_content = other_messages[target_user_position].get("content", "")
        new_content = f"<current_scenario>\n{scenario_content}\n</current_scenario>\n\n{original_content}"
        other_messages[target_user_position] = {
            **other_messages[target_user_position],
            "content": new_content
        }
        scenario_injected = True
    
    # 兜底：若未找到目标 user，则注入到最后一条 user 消息（与原行为一致）
    if scenario_content and scenario_content.strip() and not scenario_injected:
        for i in range(len(other_messages) - 1, -1, -1):
            message = other_messages[i]
            if message.get("role") == "user":
                original_content = message.get("content", "")
                new_content = f"<current_scenario>\n{scenario_content}\n</current_scenario>\n\n{original_content}"
                other_messages[i] = {
                    **message,
                    "content": new_content
                }
                break
    
    # 3. 重新组合消息：系统消息 + 处理后的其他消息
    injected_messages = system_messages + other_messages
    
    return injected_messages
