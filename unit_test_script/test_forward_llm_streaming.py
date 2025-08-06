#!/usr/bin/env python3
"""
测试forward_to_llm_streaming函数
模拟前端调用，使用DeepSeek配置，打印完整的推理+正文内容
"""
import asyncio
import sys
import os
import time

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_forward_llm_streaming():
    """测试forward_to_llm_streaming函数并打印完整内容"""
    print("🧪 开始测试forward_to_llm_streaming函数...")
    
    try:
        # 导入所需模块
        from src.workflow.graph.scenario_workflow import forward_to_llm_streaming
        
        # 模拟前端配置 - 使用用户提供的DeepSeek参数
        api_key = "sk-5b155b212651493b942e7dca7dfb4751"
        model = "deepseek-reasoner"
        
        # 准备测试消息
        original_messages = [
            {"role": "user", "content": "扮演猫咪，100字以内"}
        ]
        
        print(f"📤 测试消息: {original_messages[0]['content']}")
        print(f"🤖 使用模型: {model}")
        print(f"🌐 API地址: https://api.deepseek.com/v1")
        print("\n" + "="*50)
        print("📥 开始接收流式响应...")
        print("="*50)
        
        # 记录开始时间
        start_time = time.time()
        
        # 用于收集完整内容
        full_content = ""
        chunk_count = 0
        
        # 调用forward_to_llm_streaming函数
        async for chunk in forward_to_llm_streaming(original_messages, api_key, model):
            chunk_count += 1
            
            # 检查chunk结构
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta
                
                # 获取内容
                if hasattr(delta, 'content') and delta.content:
                    content = delta.content
                    full_content += content
                    
                    # 实时打印内容（不换行）
                    print(content, end='', flush=True)
                
                # 检查是否结束
                if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason:
                    print(f"\n\n🏁 流式响应结束，原因: {chunk.choices[0].finish_reason}")
                    break
        
        # 计算执行时间
        duration = time.time() - start_time
        
        print("\n" + "="*50)
        print("📊 测试统计信息:")
        print(f"   - 处理chunk数: {chunk_count}")
        print(f"   - 总内容长度: {len(full_content)} 字符")
        print(f"   - 执行时间: {duration:.2f} 秒")
        
        # 检查内容格式
        if "<think>" in full_content and "</think>" in full_content:
            print("✅ 确认包含推理内容标签")
        else:
            print("⚠️  未检测到推理内容标签")
        
        print("\n🎉 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 启动forward_to_llm_streaming单元测试")
    asyncio.run(test_forward_llm_streaming())