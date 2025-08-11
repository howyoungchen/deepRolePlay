"""
Message processing utility functions

Provides various utility functions for processing message lists
"""
from typing import List, Dict, Any
from config.manager import settings


def inject_scenario(messages: List[Dict[str, Any]], scenario_content: str) -> List[Dict[str, Any]]:
    """
    Injects scenario content into the message list and trims history messages based on max_history_length.
    
    Args:
        messages: The original message list.
        scenario_content: The scenario content.
        
    Returns:
        The message list after injecting the scenario.
    """
    if not messages:
        return messages
    
    # Copy the message list to avoid modifying the original data
    processed_messages = messages.copy()
    
    # 1. Separate system messages from other messages
    # Some LLMs' system prompts may be in the first message as a user role, handle this for compatibility
    system_messages = []
    other_messages = []
    
    # Flag to check if it is the first message
    is_first = True
    for msg in processed_messages:
        # If it's the first message and the role is 'user', or if the role is 'system', treat it as a system message
        if (is_first and msg.get("role") == "user") or msg.get("role") == "system":
            system_messages.append(msg)
        else:
            other_messages.append(msg)
        is_first = False
    
    # 2. Unified scenario injection and history trimming
    max_history_length = settings.langgraph.max_history_length
    last_ai_messages_index = settings.langgraph.last_ai_messages_index
    
    # Find target user position and apply history trimming
    target_user_position = -1
    user_count = 0
    
    # First pass: find the target user position (倒数第last_ai_messages_index个user)
    for i in range(len(other_messages) - 1, -1, -1):
        if other_messages[i].get("role") == "user":
            user_count += 1
            if user_count == last_ai_messages_index:
                target_user_position = i
                break
    
    # Apply history trimming if target found and max_history_length > 0
    if target_user_position >= 0 and max_history_length > 0:
        # Count backwards from target position to find max_history_length complete pairs
        ai_count = 0
        cutoff_index = 0
        
        # Count AI messages before target_user_position to determine history cutoff
        for i in range(target_user_position - 1, -1, -1):
            if other_messages[i].get("role") == "assistant":
                ai_count += 1
                if ai_count >= max_history_length:
                    # This AI message is the max_history_length-th one, keep from this AI
                    cutoff_index = i
                    break
        
        # Apply history trimming
        if ai_count >= max_history_length and cutoff_index > 0:
            other_messages = other_messages[cutoff_index:]
            # Update target_user_position after trimming
            target_user_position = target_user_position - cutoff_index
    
    # Inject scenario into target user message
    scenario_injected = False
    if target_user_position >= 0 and scenario_content and scenario_content.strip():
        original_content = other_messages[target_user_position].get("content", "")
        new_content = f"<current_scenario>\n{scenario_content}\n</current_scenario>\n\n{original_content}"
        other_messages[target_user_position] = {
            **other_messages[target_user_position],
            "content": new_content
        }
        scenario_injected = True
    
    # Fallback: if target user not found, inject into the last user message (original behavior)
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
    
    # 3. Recombine messages: system messages + processed other messages
    injected_messages = system_messages + other_messages
    
    return injected_messages