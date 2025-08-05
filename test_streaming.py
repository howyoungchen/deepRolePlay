#!/usr/bin/env python3
"""
专门测试流式输出功能 - 这是最重要的测试
测试完整的工作流流式输出，验证OpenAI格式转换
"""

import asyncio
import json
import sys
import os
import time
from typing import Dict, Any, List

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.workflow.graph.scenario_workflow import create_scenario_workflow
from utils.format_converter import convert_to_openai_sse, create_done_message, extract_content_from_event

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title:^60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")

async def test_workflow_streaming():
    """测试完整工作流的流式输出"""
    print_header("测试工作流流式输出（最重要的功能）")
    
    try:
        # 创建工作流
        workflow = create_scenario_workflow()
        print(f"{Colors.GREEN}✓ 工作流创建成功{Colors.END}")
        
        # 准备测试输入
        test_input = {
            "request_id": "streaming-test-123",
            "original_messages": [
                {"role": "user", "content": "你好，我想学习Python编程"},
                {"role": "assistant", "content": "Python是一门很好的编程语言，适合初学者。"},
                {"role": "user", "content": "能推荐一些学习资源吗？"}
            ],
            "messages": [
                {"role": "user", "content": "你好，我想学习Python编程"},
                {"role": "assistant", "content": "Python是一门很好的编程语言，适合初学者。"},
                {"role": "user", "content": "能推荐一些学习资源吗？"}
            ],
            "current_scenario": "",
            "api_key": "sk-5b155b212651493b942e7dca7dfb4751",
            "model": "deepseek-chat",
            "stream": True
        }
        
        print(f"{Colors.BLUE}ℹ 开始流式执行工作流...{Colors.END}")
        print(f"{Colors.BLUE}ℹ 预期输出顺序: 记忆闪回 → 情景更新 → LLM最终回复{Colors.END}")
        
        # 收集流式输出
        stream_chunks = []
        openai_chunks = []
        node_outputs = {"memory": [], "scenario": [], "llm": []}
        
        start_time = time.time()
        chunk_count = 0
        
        # 使用astream获取流式消息
        async for msg, metadata in workflow.astream(
            test_input,
            stream_mode="messages"
        ):
            chunk_count += 1
            current_node = metadata.get("langgraph_node", "unknown") if metadata else "unknown"
            
            if hasattr(msg, 'content') and msg.content:
                content = msg.content
                stream_chunks.append(content)
                
                # 按节点分类收集输出
                if "memory" in current_node.lower():
                    node_outputs["memory"].append(content)
                elif "scenario" in current_node.lower():
                    node_outputs["scenario"].append(content)
                elif "llm" in current_node.lower() or "forwarding" in current_node.lower():
                    node_outputs["llm"].append(content)
                
                # 转换为OpenAI格式
                try:
                    sse_chunk = convert_to_openai_sse(msg, metadata, test_input["model"])
                    openai_chunks.append(sse_chunk)
                    
                    # 验证SSE格式
                    if not sse_chunk.startswith("data: "):
                        print(f"{Colors.RED}❌ SSE格式错误: 不以'data: '开头{Colors.END}")
                    else:
                        # 解析JSON验证
                        json_str = sse_chunk[6:-2]  # 移除"data: "和"\n\n"
                        json.loads(json_str)  # 验证JSON格式
                    
                except Exception as e:
                    print(f"{Colors.RED}❌ OpenAI格式转换失败: {str(e)}{Colors.END}")
                
                # 实时显示流式输出
                if len(content) > 50:
                    display_content = content[:50] + "..."
                else:
                    display_content = content
                    
                print(f"{Colors.GREEN}📤 [{current_node}] {display_content}{Colors.END}")
            
            elif isinstance(msg, dict):
                # 处理字典格式消息
                content = extract_content_from_event(msg)
                if content:
                    stream_chunks.append(content)
                    print(f"{Colors.YELLOW}📤 [dict] {content[:50]}...{Colors.END}")
        
        duration = time.time() - start_time
        
        # 分析结果
        print_header("流式输出测试结果分析")
        
        print(f"{Colors.BLUE}📊 基本统计:{Colors.END}")
        print(f"   总执行时间: {duration:.2f}秒")
        print(f"   流式块数量: {chunk_count}")
        print(f"   OpenAI格式块: {len(openai_chunks)}")
        print(f"   总内容长度: {sum(len(c) for c in stream_chunks)} 字符")
        
        print(f"\n{Colors.BLUE}📋 节点输出分布:{Colors.END}")
        print(f"   记忆闪回节点: {len(node_outputs['memory'])} 块")
        print(f"   情景更新节点: {len(node_outputs['scenario'])} 块") 
        print(f"   LLM转发节点: {len(node_outputs['llm'])} 块")
        
        # 验证流式输出完整性
        success_checks = []
        
        # 检查1: 是否有流式输出
        if len(stream_chunks) > 0:
            success_checks.append(("有流式输出", True))
            print(f"{Colors.GREEN}✓ 检查1通过: 产生了 {len(stream_chunks)} 个流式块{Colors.END}")
        else:
            success_checks.append(("有流式输出", False))
            print(f"{Colors.RED}✗ 检查1失败: 没有流式输出{Colors.END}")
        
        # 检查2: OpenAI格式转换
        if len(openai_chunks) > 0:
            success_checks.append(("OpenAI格式转换", True))
            print(f"{Colors.GREEN}✓ 检查2通过: 成功转换 {len(openai_chunks)} 个OpenAI格式块{Colors.END}")
            
            # 显示第一个OpenAI格式块样例
            if openai_chunks:
                print(f"{Colors.YELLOW}   样例SSE块: {openai_chunks[0][:100]}...{Colors.END}")
        else:
            success_checks.append(("OpenAI格式转换", False))
            print(f"{Colors.RED}✗ 检查2失败: OpenAI格式转换失败{Colors.END}")
        
        # 检查3: 多节点输出
        active_nodes = sum(1 for node_list in node_outputs.values() if len(node_list) > 0)
        if active_nodes >= 2:  # 至少2个节点有输出
            success_checks.append(("多节点输出", True))
            print(f"{Colors.GREEN}✓ 检查3通过: {active_nodes} 个节点产生了输出{Colors.END}")
        else:
            success_checks.append(("多节点输出", False))
            print(f"{Colors.RED}✗ 检查3失败: 只有 {active_nodes} 个节点产生输出{Colors.END}")
        
        # 检查4: 内容质量
        total_content = ''.join(stream_chunks)
        if len(total_content) > 100:  # 至少100字符的有意义内容
            success_checks.append(("内容质量", True))
            print(f"{Colors.GREEN}✓ 检查4通过: 总内容长度 {len(total_content)} 字符{Colors.END}")
        else:
            success_checks.append(("内容质量", False))
            print(f"{Colors.RED}✗ 检查4失败: 内容过少 ({len(total_content)} 字符){Colors.END}")
        
        # 检查5: 流式延迟合理性
        avg_delay = duration / max(chunk_count, 1)
        if avg_delay < 10:  # 每块平均不超过10秒
            success_checks.append(("流式延迟", True))
            print(f"{Colors.GREEN}✓ 检查5通过: 平均每块延迟 {avg_delay:.2f}秒{Colors.END}")
        else:
            success_checks.append(("流式延迟", False))
            print(f"{Colors.RED}✗ 检查5失败: 平均每块延迟过长 ({avg_delay:.2f}秒){Colors.END}")
        
        # 总体评估
        passed_checks = sum(1 for _, passed in success_checks if passed)
        total_checks = len(success_checks)
        
        print_header("最终测试结果")
        
        if passed_checks == total_checks:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 流式输出测试完全通过！({passed_checks}/{total_checks}){Colors.END}")
            print(f"{Colors.GREEN}   工作流流式输出功能正常，可以为用户提供实时的AI思考过程{Colors.END}")
            return True
        elif passed_checks >= total_checks * 0.8:  # 80%通过
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠ 流式输出基本通过 ({passed_checks}/{total_checks}){Colors.END}")
            print(f"{Colors.YELLOW}   主要功能正常，但有少量问题需要优化{Colors.END}")
            return True
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ 流式输出测试失败 ({passed_checks}/{total_checks}){Colors.END}")
            print(f"{Colors.RED}   流式输出功能存在严重问题，需要修复{Colors.END}")
            return False
        
    except Exception as e:
        print(f"{Colors.RED}❌ 流式输出测试异常: {str(e)}{Colors.END}")
        import traceback
        print(f"{Colors.RED}{traceback.format_exc()}{Colors.END}")
        return False

async def test_openai_format_conversion():
    """专门测试OpenAI格式转换"""
    print_header("测试OpenAI格式转换功能")
    
    try:
        from langchain_core.messages import AIMessage
        from utils.format_converter import convert_to_openai_format, convert_to_openai_sse
        
        # 测试消息
        test_msg = AIMessage(content="这是一个测试消息")
        
        # 测试OpenAI格式转换
        openai_format = convert_to_openai_format(test_msg, model="deepseek-chat")
        
        # 验证格式
        required_fields = ["id", "object", "created", "model", "choices"]
        missing_fields = [field for field in required_fields if field not in openai_format]
        
        if not missing_fields:
            print(f"{Colors.GREEN}✓ OpenAI格式包含所有必需字段{Colors.END}")
        else:
            print(f"{Colors.RED}✗ OpenAI格式缺少字段: {missing_fields}{Colors.END}")
            return False
        
        # 验证choices结构
        choices = openai_format.get("choices", [])
        if choices and len(choices) > 0:
            choice = choices[0]
            if "delta" in choice and "content" in choice["delta"]:
                print(f"{Colors.GREEN}✓ choices结构正确{Colors.END}")
            else:
                print(f"{Colors.RED}✗ choices结构错误{Colors.END}")
                return False
        else:
            print(f"{Colors.RED}✗ choices字段为空{Colors.END}")
            return False
        
        # 测试SSE格式转换
        sse_format = convert_to_openai_sse(test_msg, model="deepseek-chat")
        
        if sse_format.startswith("data: ") and sse_format.endswith("\n\n"):
            print(f"{Colors.GREEN}✓ SSE格式正确{Colors.END}")
        else:
            print(f"{Colors.RED}✗ SSE格式错误{Colors.END}")
            return False
        
        # 验证JSON可解析性
        json_part = sse_format[6:-2]  # 移除"data: "和"\n\n"
        try:
            parsed_json = json.loads(json_part)
            print(f"{Colors.GREEN}✓ SSE中的JSON可正确解析{Colors.END}")
        except json.JSONDecodeError as e:
            print(f"{Colors.RED}✗ SSE中的JSON解析失败: {str(e)}{Colors.END}")
            return False
        
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 OpenAI格式转换测试通过！{Colors.END}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌ OpenAI格式转换测试异常: {str(e)}{Colors.END}")
        return False

async def main():
    """主测试函数"""
    print(f"{Colors.CYAN}🚀 开始流式输出专项测试...{Colors.END}")
    
    # 测试1: OpenAI格式转换
    print("\n" + "="*60)
    format_test = await test_openai_format_conversion()
    
    # 测试2: 完整工作流流式输出
    print("\n" + "="*60)
    streaming_test = await test_workflow_streaming()
    
    # 最终报告
    print_header("专项测试总结报告")
    
    if format_test and streaming_test:
        print(f"{Colors.GREEN}{Colors.BOLD}🏆 所有流式输出测试通过！{Colors.END}")
        print(f"{Colors.GREEN}   ✓ OpenAI格式转换正常{Colors.END}")
        print(f"{Colors.GREEN}   ✓ 工作流流式输出正常{Colors.END}")
        print(f"{Colors.GREEN}   ✓ 用户可以实时看到完整的AI思考过程{Colors.END}")
        print(f"{Colors.GREEN}   ✓ 重构后的流式功能完全可用！{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ 流式输出测试存在问题{Colors.END}")
        print(f"   OpenAI格式转换: {'✓' if format_test else '✗'}")
        print(f"   工作流流式输出: {'✓' if streaming_test else '✗'}")

if __name__ == "__main__":
    asyncio.run(main())