#!/usr/bin/env python3
"""
测试重构后的工作流：分离的情景更新和LLM转发
"""
import asyncio
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_separated_workflow():
    """测试拆分后的工作流功能"""
    print("🧪 开始测试拆分后的工作流...")
    
    try:
        # 从配置文件读取真实的API密钥
        from config.manager import settings
        from utils.pretty_print import pretty_print_stream_events
        
        # 准备测试数据
        test_messages = [
            {"role": "user", "content": "你好，我想学习魔法"},
        ]
        
        test_input = {
            "current_scenario": "这是一个魔法学院的场景",
            "messages": test_messages,
            "original_messages": test_messages,
            "api_key": settings.agent.api_key,  # 使用配置文件中的真实密钥
            "model": settings.agent.model,      # 使用配置文件中的模型名
            "stream": True,
            "request_id": "test-123"
        }
        
        # 1. 测试修改后的工作流（只包含memory_flashback和scenario_updater）
        print("\n📝 测试阶段1：情景更新工作流...")
        from src.workflow.graph.scenario_workflow import create_scenario_workflow
        
        workflow = create_scenario_workflow()
        print(f"✅ 工作流创建成功，节点数量: {len(workflow.nodes)}")
        
        # 检查工作流节点
        workflow_nodes = list(workflow.nodes.keys())
        print(f"📋 工作流节点: {workflow_nodes}")
        
        if 'llm_forwarding' in workflow_nodes:
            print("⚠️  警告：工作流中仍包含llm_forwarding节点")
        else:
            print("✅ 确认：工作流中已移除llm_forwarding节点")
        
        # 执行工作流（使用流式事件）
        print("\n⚙️  执行工作流...")
        final_result = None
        event_count = 0
        
        # 添加超时保护
        import asyncio
        timeout_seconds = 60
        
        try:
            async with asyncio.timeout(timeout_seconds):
                async for event in workflow.astream_events(test_input, version="v2"):
                    pretty_print_stream_events(event)
                    event_count += 1
                    
                    # 检查链结束事件以获取最终结果
                    if event.get("event") == "on_chain_end" and event.get("name") == "LangGraph":
                        final_result = event.get("data", {}).get("output", {})

        except asyncio.TimeoutError:
            print(f"⏰ 工作流执行超时 ({timeout_seconds}秒)，可能存在问题")
                
        print(f"\n✅ 工作流执行成功，处理了 {event_count} 个事件")
        
        if final_result:
            print("\n📋 最终结果获取成功")
            if isinstance(final_result, dict):
                updated_scenario = final_result.get('current_scenario', 'N/A')
                messages_count = len(final_result.get('messages', []))
                print(f"   - 更新后的场景 (摘要): {updated_scenario[:100]}...")
                print(f"   - 更新后的消息数量: {messages_count}")
        else:
            print("\n⚠️  未获取到最终结果")
        
        print(f"\n🎉 工作流测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 开始工作流测试")
    asyncio.run(test_separated_workflow())