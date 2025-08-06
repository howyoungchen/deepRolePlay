#!/usr/bin/env python3
"""
测试扩展后的流式输出功能，包括工具调用、工具输出、LLM输出
"""
import asyncio
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_enhanced_streaming():
    """测试扩展后的工作流流式输出，包括工具调用和LLM输出"""
    print("🧪 测试扩展后的流式输出功能...")
    
    try:
        from config.manager import settings
        from src.scenario.manager import scenario_manager
        from utils.format_converter import convert_workflow_event_to_sse
        
        # 准备测试数据
        test_messages = [
            {"role": "user", "content": "你好，我想学习魔法知识"},
        ]
        
        workflow_input = {
            "current_scenario": "这是一个魔法学院的场景",
            "messages": test_messages,
            "original_messages": test_messages,
            "api_key": settings.agent.api_key,
            "model": settings.agent.model,
            "stream": True,
            "request_id": "test-enhanced-streaming"
        }
        
        print("📡 开始测试扩展的scenario工作流流式输出...")
        print("=" * 60)
        
        event_count = 0
        sse_count = 0
        event_types = {}
        
        async for event in scenario_manager.update_scenario_streaming(workflow_input):
            event_count += 1
            event_type = event.get("event", "unknown")
            name = event.get("name", "")
            
            # 统计事件类型
            event_key = f"{event_type}:{name}"
            event_types[event_key] = event_types.get(event_key, 0) + 1
            
            # 测试新的转换函数
            sse_chunk = convert_workflow_event_to_sse(event, workflow_input["model"], workflow_input["request_id"])
            if sse_chunk:
                sse_count += 1
                # 解析SSE数据以显示实际内容
                try:
                    import json
                    if sse_chunk.startswith("data: "):
                        json_str = sse_chunk[6:].strip()
                        if json_str != "[DONE]":
                            sse_data = json.loads(json_str)
                            content = sse_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                print(f"📨 SSE输出: {content.strip()}")
                except:
                    print(f"📨 SSE输出: [解析失败]")
            
            # 限制输出长度
            if event_count > 200:
                print("⏰ 达到事件数量限制，停止测试")
                break
        
        print("=" * 60)
        print(f"📊 测试结果:")
        print(f"   - 总事件数: {event_count}")
        print(f"   - 成功转换的SSE数: {sse_count}")
        print(f"   - 事件类型统计:")
        for event_type, count in sorted(event_types.items()):
            print(f"     {event_type}: {count}")
        
        if sse_count > 0:
            print("✅ 扩展的流式输出功能正常！")
        else:
            print("❌ 没有生成任何SSE输出")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 开始扩展流式输出测试")
    asyncio.run(test_enhanced_streaming())