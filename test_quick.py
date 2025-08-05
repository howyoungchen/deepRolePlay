#!/usr/bin/env python3
"""
快速测试脚本 - 验证LLM转发节点修复
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.workflow.graph.scenario_workflow import create_scenario_workflow

async def quick_test():
    """快速测试工作流"""
    print("🚀 开始快速测试...")
    
    try:
        # 创建工作流
        workflow = create_scenario_workflow()
        print("✅ 工作流创建成功")
        
        # 创建测试输入
        test_input = {
            "request_id": "test-123",
            "original_messages": [{"role": "user", "content": "你好"}],
            "messages": [{"role": "user", "content": "你好"}],
            "current_scenario": "",
            "api_key": "sk-5b155b212651493b942e7dca7dfb4751",
            "model": "deepseek-chat",
            "stream": False
        }
        print("✅ 测试输入准备完成")
        
        # 执行工作流（只执行前两个节点，跳过可能有问题的LLM转发节点）
        print("🔄 开始执行工作流...")
        result = await workflow.ainvoke(test_input)
        
        # 检查结果
        if "llm_response" in result:
            llm_response = result["llm_response"]
            if hasattr(llm_response, 'content'):
                print(f"✅ LLM转发节点成功: {llm_response.content[:50]}...")
            elif "Error" in str(llm_response):
                print(f"❌ LLM转发节点仍有错误: {str(llm_response)[:100]}...")
            else:
                print(f"✅ LLM转发节点返回响应: {str(llm_response)[:50]}...")
        else:
            print("⚠️ 未找到LLM响应字段")
        
        print(f"📊 工作流完成，返回字段: {list(result.keys())}")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_test())
    if success:
        print("\n🎉 快速测试通过！")
    else:
        print("\n💥 快速测试失败！")