#!/usr/bin/env python3
"""
测试修复后的流式输出功能
"""
import asyncio
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_streaming_fix():
    """测试修复后的scenario工作流流式输出"""
    print("🧪 测试修复后的流式输出功能...")
    
    try:
        from config.manager import settings
        from src.scenario.manager import scenario_manager
        from utils.format_converter import convert_langgraph_chunk_to_sse
        
        # 准备测试数据
        test_messages = [
            {"role": "user", "content": "你好，我是一个魔法师学徒"},
        ]
        
        workflow_input = {
            "current_scenario": "这是一个魔法学院的场景",
            "messages": test_messages,
            "original_messages": test_messages,
            "api_key": settings.agent.api_key,
            "model": settings.agent.model,
            "stream": True,
            "request_id": "test-streaming-fix"
        }
        
        print("📡 开始测试scenario工作流流式输出...")
        
        # 测试scenario_manager的流式输出
        event_count = 0
        chat_model_events = 0
        valid_sse_chunks = 0
        
        async for event in scenario_manager.update_scenario_streaming(workflow_input):
            event_count += 1
            
            # 检查是否为ChatOpenAI的流式事件
            if (event.get("event") == "on_chat_model_stream" and 
                event.get("name") == "ChatOpenAI" and
                event.get("data", {}).get("chunk")):
                
                chat_model_events += 1
                chunk = event["data"]["chunk"]
                
                print(f"📨 ChatOpenAI事件 #{chat_model_events}:")
                print(f"   - Chunk类型: {type(chunk)}")
                print(f"   - Chunk内容: {getattr(chunk, 'content', 'N/A')}")
                
                # 测试新的转换函数
                sse_chunk = convert_langgraph_chunk_to_sse(chunk, workflow_input["model"], workflow_input["request_id"])
                if sse_chunk:
                    valid_sse_chunks += 1
                    print(f"   - SSE转换成功: {sse_chunk[:100]}...")
                else:
                    print(f"   - SSE转换失败")
                
                print()
            
            # 添加超时保护
            if event_count > 100:
                print("⏰ 达到事件数量限制，停止测试")
                break
        
        print(f"📊 测试结果:")
        print(f"   - 总事件数: {event_count}")
        print(f"   - ChatOpenAI流式事件数: {chat_model_events}")
        print(f"   - 成功转换的SSE块数: {valid_sse_chunks}")
        
        if chat_model_events > 0 and valid_sse_chunks > 0:
            print("✅ 流式输出修复成功！")
        elif chat_model_events > 0:
            print("⚠️  发现ChatOpenAI事件，但SSE转换失败")
        else:
            print("❌ 没有发现ChatOpenAI流式事件")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 开始流式输出修复测试")
    asyncio.run(test_streaming_fix())