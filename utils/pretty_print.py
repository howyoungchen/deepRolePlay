"""
Pretty print tool, supports formatted display of LangGraph stream events
"""


def pretty_print_stream_events(event):
    """
    Pretty prints LangGraph stream events.
    
    Args:
        event: The event dictionary from astream_events.
    """
    event_type = event.get("event", "unknown")
    name = event.get("name", "")
    data = event.get("data", {})
    
    # 调试：打印所有事件类型以查看缺失的AI消息事件
    # print(f"DEBUG: {event_type} - {name}")
    
    # Global state tracking (using function attributes)
    if not hasattr(pretty_print_stream_events, 'current_node'):
        pretty_print_stream_events.current_node = None
    if not hasattr(pretty_print_stream_events, 'message_buffer'):
        pretty_print_stream_events.message_buffer = ""
    if not hasattr(pretty_print_stream_events, 'ai_message_started'):
        pretty_print_stream_events.ai_message_started = False
    
    # Detect node start
    if event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater", "llm_forwarding"]:
        pretty_print_stream_events.current_node = name
        # 对llm_forwarding节点不显示开始信息
        if name != "llm_forwarding":
            print(f"\n🔄 Update from node {name}:")
            print()
        return
    
    # Handle AI message stream output
    if event_type == "on_chat_model_stream" and name == "ChatOpenAI" and pretty_print_stream_events.current_node:
        chunk = data.get("chunk", {})
        if hasattr(chunk, 'content'):
            if not pretty_print_stream_events.ai_message_started:
                # 对llm_forwarding节点不显示AI消息标题
                if pretty_print_stream_events.current_node != "llm_forwarding":
                    print("================================== Ai Message ==================================")
                    print(f"Name: {pretty_print_stream_events.current_node}_agent")
                pretty_print_stream_events.ai_message_started = True
            
            # 只有当content不为空时才输出和累积
            if chunk.content:
                # Accumulate message content
                pretty_print_stream_events.message_buffer += chunk.content
                print(chunk.content, end="", flush=True)
        return
    
    # Newline at the end of the AI message
    if event_type == "on_chat_model_end" and name == "ChatOpenAI" and pretty_print_stream_events.current_node:
        if pretty_print_stream_events.ai_message_started:
            print("\n")
            pretty_print_stream_events.ai_message_started = False
            pretty_print_stream_events.message_buffer = ""
        return
    
    # Detect tool call start
    if event_type == "on_tool_start" and pretty_print_stream_events.current_node:
        tool_name = name
        tool_input = data.get("input", {})
        
        # If there is an AI message buffer, end it first
        if pretty_print_stream_events.ai_message_started:
            print("\n")
            pretty_print_stream_events.ai_message_started = False
        
        print("Tool Calls:")
        print(f"  {tool_name}")  
        if tool_input:
            print("  Args:")
            for key, value in tool_input.items():
                print(f"    {key}: {value}")
        print()
        return
    
    # Detect tool call end
    if event_type == "on_tool_end" and pretty_print_stream_events.current_node:
        tool_name = name
        tool_output = data.get("output", "")
        
        # 对sequential_thinking工具的输出进行特殊处理
        if tool_name == "sequential_thinking":
            # sequential_thinking已经有自己的可视化输出（框框），这里只显示简化的结果
            try:
                import json
                # 检查tool_output是否有content属性
                if hasattr(tool_output, 'content'):
                    content = tool_output.content
                elif isinstance(tool_output, str):
                    content = tool_output
                else:
                    content = str(tool_output)
                
                result = json.loads(content)
                success = result.get("success", False)
                thought_num = result.get("thought_number", "?")
                total_thoughts = result.get("total_thoughts", "?")
                next_needed = result.get("next_thought_needed", False)
                history_length = result.get("thought_history_length", "?")
                
                print(f"Tool Results:")
                print(f"  sequential_thinking")
                print(f"  Returns:")
                print(f"    success: {str(success).lower()}")
                print(f"    thought_number: {thought_num}")
                print(f"    total_thoughts: {total_thoughts}")
                print(f"    next_thought_needed: {str(next_needed).lower()}")
                print(f"    thought_history_length: {history_length}")
            except Exception as e:
                print(f"Tool Results:")
                print(f"  sequential_thinking")
                print(f"  Returns: {tool_output}")
                print(f"  (Error parsing: {e})")
        else:
            # 其他工具保持原有的详细显示
            print(f"\n🔧 Update from node tools:")
            print()
            print("================================= Tool Message =================================")
            print(f"Name: {tool_name}")
            print()
            
            if isinstance(tool_output, str):
                if len(tool_output) > 500:
                    print(f"{tool_output[:500]}... (truncated)")
                else:
                    print(tool_output)
            else:
                print(tool_output)
            print()
        return
    
    # Detect node completion
    if event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater", "llm_forwarding"]:
        node_output = data.get("output", {})
        
        # If there is an AI message buffer, end it first
        if pretty_print_stream_events.ai_message_started:
            print("\n")
            pretty_print_stream_events.ai_message_started = False
        
        # 对llm_forwarding节点做特殊处理，不显示技术细节
        if name == "llm_forwarding":
            pretty_print_stream_events.current_node = None
            return
        
        print(f"✅ Node {name} completed:")
        for key, value in node_output.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}... (truncated)")
            else:
                print(f"  {key}: {value}")
        print("-" * 80)
        pretty_print_stream_events.current_node = None
        return


