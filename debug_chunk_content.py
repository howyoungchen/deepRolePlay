#!/usr/bin/env python3
"""
调试AIMessageChunk的详细内容
"""
import asyncio
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def debug_chunk_content():
    """详细调试AIMessageChunk的内容"""
    print("🔍 调试AIMessageChunk的详细内容...")
    
    try:
        from config.manager import settings
        from src.scenario.manager import scenario_manager
        
        # 准备测试数据
        test_messages = [
            {"role": "user", "content": "你好"},
        ]
        
        workflow_input = {
            "current_scenario": "测试场景",
            "messages": test_messages,
            "original_messages": test_messages,
            "api_key": settings.agent.api_key,
            "model": settings.agent.model,
            "stream": True,
            "request_id": "debug-test"
        }
        
        print("🔍 开始调试...")
        
        event_count = 0
        async for event in scenario_manager.update_scenario_streaming(workflow_input):
            event_count += 1
            
            # 检查ChatOpenAI流式事件
            if (event.get("event") == "on_chat_model_stream" and 
                event.get("name") == "ChatOpenAI"):
                
                chunk = event.get("data", {}).get("chunk")
                if chunk:
                    print(f"🔍 事件 #{event_count}:")
                    print(f"   - 类型: {type(chunk)}")
                    print(f"   - 所有属性: {dir(chunk)}")
                    print(f"   - content: '{getattr(chunk, 'content', 'NO_CONTENT')}'")
                    print(f"   - id: {getattr(chunk, 'id', 'NO_ID')}")
                    print(f"   - additional_kwargs: {getattr(chunk, 'additional_kwargs', 'NO_KWARGS')}")
                    print(f"   - response_metadata: {getattr(chunk, 'response_metadata', 'NO_METADATA')}")
                    
                    # 检查content是否为空字符串vs None vs其他
                    content = getattr(chunk, 'content', None)
                    print(f"   - content类型: {type(content)}")
                    print(f"   - content长度: {len(content) if content else 'None'}")
                    print(f"   - content repr: {repr(content)}")
                    print()
                    
                    # 只打印前5个有内容的事件
                    if content and len(content.strip()) > 0:
                        print(f"✅ 找到有内容的chunk: '{content}'")
                        break
            
            # 限制调试输出
            if event_count > 20:
                print("⏰ 达到调试限制，停止")
                break
        
        print(f"📊 调试完成，共处理 {event_count} 个事件")
        
    except Exception as e:
        print(f"❌ 调试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_chunk_content())