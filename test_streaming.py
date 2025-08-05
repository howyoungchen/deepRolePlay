#!/usr/bin/env python3
"""
简化的流式输出测试
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 屏蔽sequential_thinking工具的可视化输出
os.environ["DISABLE_THOUGHT_LOGGING"] = "true"

from src.workflow.graph.scenario_workflow import create_scenario_workflow
from utils.pretty_print import pretty_print_stream_events

async def main():
    """简化的流式测试"""
    print("🚀 开始流式输出测试...")
    
    try:
        # 创建工作流
        workflow = create_scenario_workflow()
        print("✓ 工作流创建成功")
        
        # 简单的测试输入
        test_input = {
            "request_id": "test-123", 
            "messages": [
                {"role": "user", "content": "你好，我想学习AI和机器学习相关的知识"}
            ],
            "current_scenario": "",
            "api_key": "sk-5b155b212651493b942e7dca7dfb4751",
            "model": "deepseek-chat",
            "stream": True
        }
        
        print("开始执行工作流...")
        
        # 使用astream_events获取详细的流式事件并使用pretty_print显示
        async for event in workflow.astream_events(test_input, version="v2"):
            pretty_print_stream_events(event)
        
        print("✓ 流式输出测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())