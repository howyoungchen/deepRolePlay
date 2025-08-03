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
    
    # 2. Trim messages based on max_history_length
    max_history_length = settings.langgraph.max_history_length
    
    if max_history_length > 0:
        # Count AI messages from the end
        ai_message_count = 0
        cutoff_index = 0  # Default to keeping all messages from the beginning
        
        for i in range(len(other_messages) - 1, -1, -1):
            if other_messages[i].get("role") == "assistant":
                ai_message_count += 1
                if ai_message_count >= max_history_length:
                    # Found the max_history_length-th AI message, keep messages from this point
                    cutoff_index = i
                    break
        
        # Trim only when enough AI messages are found
        if ai_message_count >= max_history_length:
            other_messages = other_messages[cutoff_index:]
    
    # 3. Recombine messages: system messages + trimmed other messages
    injected_messages = system_messages + other_messages
    
    # 4. Inject scenario content into the last user message
    if scenario_content and scenario_content.strip():
        # Find the last user message and insert the scenario at the beginning of its content
        for i in range(len(injected_messages) - 1, -1, -1):
            message = injected_messages[i]
            if message.get("role") == "user":
                # Add scenario at the beginning of the user message content
                original_content = message.get("content", "")
                new_content = f"<current_scenario>\n{scenario_content}\n</current_scenario>\n\n{original_content}"
                
                # Create a new message object
                injected_messages[i] = {
                    **message,  # Keep other fields unchanged
                    "content": new_content
                }
                break
    
    return injected_messages