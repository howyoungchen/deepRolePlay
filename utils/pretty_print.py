"""
美化输出工具，支持LangGraph流式事件的美化显示
"""


def pretty_print_stream_events(event):
    """
    美化打印LangGraph流式事件
    
    Args:
        event: 来自 astream_events 的事件字典
    """
    event_type = event.get("event", "unknown")
    name = event.get("name", "")
    data = event.get("data", {})
    
    # 全局状态追踪（使用函数属性）
    if not hasattr(pretty_print_stream_events, 'current_node'):
        pretty_print_stream_events.current_node = None
    if not hasattr(pretty_print_stream_events, 'message_buffer'):
        pretty_print_stream_events.message_buffer = ""
    if not hasattr(pretty_print_stream_events, 'ai_message_started'):
        pretty_print_stream_events.ai_message_started = False
    
    # 检测节点开始
    if event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater"]:
        pretty_print_stream_events.current_node = name
        print(f"\n🔄 Update from node {name}:")
        print()
        return
    
    # 处理AI消息流式输出
    if event_type == "on_chat_model_stream" and pretty_print_stream_events.current_node:
        chunk = data.get("chunk", {})
        if hasattr(chunk, 'content') and chunk.content:
            if not pretty_print_stream_events.ai_message_started:
                print("================================== Ai Message ==================================")
                print(f"Name: {pretty_print_stream_events.current_node}_agent")
                pretty_print_stream_events.ai_message_started = True
            
            # 累积消息内容
            pretty_print_stream_events.message_buffer += chunk.content
            print(chunk.content, end="", flush=True)
        return
    
    # AI消息结束时换行
    if event_type == "on_chat_model_end" and pretty_print_stream_events.current_node:
        if pretty_print_stream_events.ai_message_started:
            print("\n")
            pretty_print_stream_events.ai_message_started = False
            pretty_print_stream_events.message_buffer = ""
        return
    
    # 检测工具调用开始
    if event_type == "on_tool_start" and pretty_print_stream_events.current_node:
        tool_name = name
        tool_input = data.get("input", {})
        
        # 如果有AI消息缓冲，先结束它
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
    
    # 检测工具调用结束
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
                print(f"{tool_output[:500]}... (已截断)")
            else:
                print(tool_output)
        else:
            print(tool_output)
        print()
        return
    
    # 检测节点完成
    if event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater"]:
        node_output = data.get("output", {})
        
        # 如果有AI消息缓冲，先结束它
        if pretty_print_stream_events.ai_message_started:
            print("\n")
            pretty_print_stream_events.ai_message_started = False
        
        print(f"✅ Node {name} completed:")
        for key, value in node_output.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}... (已截断)")
            else:
                print(f"  {key}: {value}")
        print("-" * 80)
        pretty_print_stream_events.current_node = None
        return


