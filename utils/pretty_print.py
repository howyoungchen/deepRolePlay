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
    
    # Global state tracking (using function attributes)
    if not hasattr(pretty_print_stream_events, 'current_node'):
        pretty_print_stream_events.current_node = None
    if not hasattr(pretty_print_stream_events, 'message_buffer'):
        pretty_print_stream_events.message_buffer = ""
    if not hasattr(pretty_print_stream_events, 'ai_message_started'):
        pretty_print_stream_events.ai_message_started = False
    
    # Detect node start
    if event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater"]:
        pretty_print_stream_events.current_node = name
        print(f"\n🔄 Update from node {name}:")
        print()
        return
    
    # Handle AI message stream output
    if event_type == "on_chat_model_stream" and pretty_print_stream_events.current_node:
        chunk = data.get("chunk", {})
        if hasattr(chunk, 'content') and chunk.content:
            if not pretty_print_stream_events.ai_message_started:
                print("================================== Ai Message ==================================")
                print(f"Name: {pretty_print_stream_events.current_node}_agent")
                pretty_print_stream_events.ai_message_started = True
            
            # Accumulate message content
            pretty_print_stream_events.message_buffer += chunk.content
            print(chunk.content, end="", flush=True)
        return
    
    # Newline at the end of the AI message
    if event_type == "on_chat_model_end" and pretty_print_stream_events.current_node:
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
    if event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater"]:
        node_output = data.get("output", {})
        
        # If there is an AI message buffer, end it first
        if pretty_print_stream_events.ai_message_started:
            print("\n")
            pretty_print_stream_events.ai_message_started = False
        
        print(f"✅ Node {name} completed:")
        for key, value in node_output.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}... (truncated)")
            else:
                print(f"  {key}: {value}")
        print("-" * 80)
        pretty_print_stream_events.current_node = None
        return


