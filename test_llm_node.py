#!/usr/bin/env python3
"""
测试LLM转发节点
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:    
    sys.path.insert(0, project_root)

async def test_llm_node():
    """测试LLM转发节点"""
    print("🔧 测试LLM转发节点配置...")
    
    try:
        # 导入必要模块
        from src.workflow.graph.scenario_workflow import llm_forwarding_node
        from config.manager import settings
        
        print(f"✅ 配置加载成功")
        print(f"   - proxy.target_url: {settings.proxy.target_url}")
        print(f"   - agent.api_key: {settings.agent.api_key[:8]}...{settings.agent.api_key[-8:]}")
        
        # 创建测试状态
        test_state = {
            "original_messages": [{"role": "user", "content": "你好，测试消息"}],
            "messages": [{"role": "user", "content": "你好，测试消息"}], 
            "api_key": "sk-5b155b212651493b942e7dca7dfb4751",
            "model": "deepseek-chat",
            "stream": True
        }
        
        print("🚀 开始测试LLM转发节点...")
        
        # 测试节点
        result = await llm_forwarding_node(test_state)
        
        # 检查结果
        if "llm_response" in result:
            llm_response = result["llm_response"]
            if hasattr(llm_response, 'content'):
                content = llm_response.content
                print(f"✅ LLM节点成功返回内容: {content[:100]}...")
                return True
            elif "Error" in str(llm_response):
                print(f"❌ LLM节点返回错误: {str(llm_response)}")
                return False
            else:
                print(f"✅ LLM节点返回响应: {str(llm_response)[:100]}...")
                return True
        else:
            print("❌ LLM节点未返回响应")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(test_llm_node())
    if success:
        print("\n🎉 LLM转发节点测试通过！")
    else:
        print("\n💥 LLM转发节点测试失败！")