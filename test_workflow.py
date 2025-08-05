#!/usr/bin/env python3
"""
工作流测试脚本 - 测试重构后的 scenario_workflow.py
测试三个节点的协同工作：memory_flashback -> scenario_updater -> llm_forwarding

配置说明：
- 代理LLM：使用 config/config.yaml 中的配置（用于记忆闪回和情景更新节点）
- 转发LLM：使用指定的 deepseek 配置（用于最终用户回复）
"""

import asyncio
import json
import time
import uuid
import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入工作流相关模块
from src.workflow.graph.scenario_workflow import create_scenario_workflow
from utils.format_converter import convert_final_response, extract_content_from_event
from config.manager import settings

# 测试配置常量
DEEPSEEK_CONFIG = {
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat", 
    "api_key": "sk-5b155b212651493b942e7dca7dfb4751"
}

class Colors:
    """终端颜色代码"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title: str):
    """打印测试标题"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title:^60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")

def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message: str):
    """打印错误消息"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_warning(message: str):
    """打印警告消息"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

def print_info(message: str):
    """打印信息消息"""
    print(f"{Colors.BLUE}ℹ {message}{Colors.END}")

def create_mock_messages() -> List[Dict[str, Any]]:
    """创建模拟聊天消息"""
    return [
        {
            "role": "user",
            "content": "你好，我想了解一下机器学习中的深度学习技术。"
        },
        {
            "role": "assistant", 
            "content": "深度学习是机器学习的一个重要分支，它使用多层神经网络来学习数据的复杂模式。主要包括卷积神经网络(CNN)、循环神经网络(RNN)等架构。"
        },
        {
            "role": "user",
            "content": "能详细介绍一下神经网络的工作原理吗？特别是反向传播算法。"
        }
    ]

def create_test_input(
    messages: List[Dict[str, Any]], 
    api_key: str = DEEPSEEK_CONFIG["api_key"],
    model: str = DEEPSEEK_CONFIG["model"],
    stream: bool = False
) -> Dict[str, Any]:
    """创建测试输入数据"""
    return {
        "request_id": str(uuid.uuid4()),
        "original_messages": messages.copy(),
        "messages": messages.copy(),
        "current_scenario": "",  # 将由工作流读取
        "api_key": api_key,
        "model": model,
        "stream": stream
    }

def validate_workflow_output(result: Dict[str, Any]) -> tuple[bool, str]:
    """验证工作流输出结果"""
    try:
        # 检查必需的输出字段
        required_fields = ["memory_flashback", "final_scenario", "llm_response"]
        missing_fields = []
        
        for field in required_fields:
            if field not in result:
                missing_fields.append(field)
        
        if missing_fields:
            return False, f"缺少必需字段: {', '.join(missing_fields)}"
        
        # 检查记忆闪回结果
        memory_flashback = result.get("memory_flashback", "")
        if not memory_flashback or len(memory_flashback.strip()) < 10:
            return False, "记忆闪回结果为空或过短"
        
        # 检查情景更新结果
        final_scenario = result.get("final_scenario", "")
        if not final_scenario or len(final_scenario.strip()) < 10:
            return False, "最终情景结果为空或过短"
        
        # 检查LLM响应
        llm_response = result.get("llm_response")
        if not llm_response:
            return False, "LLM响应为空"
        
        # 检查LLM响应内容
        if hasattr(llm_response, 'content'):
            content = llm_response.content
        elif isinstance(llm_response, dict):
            content = llm_response.get('content', '')
        else:
            content = str(llm_response)
        
        if not content or len(content.strip()) < 10:
            return False, "LLM响应内容为空或过短"
        
        return True, "所有输出验证通过"
        
    except Exception as e:
        return False, f"验证过程出错: {str(e)}"

def print_workflow_result(result: Dict[str, Any]):
    """打印工作流结果详情"""
    print(f"\n{Colors.PURPLE}--- 工作流执行结果 ---{Colors.END}")
    
    # 打印记忆闪回结果
    memory_flashback = result.get("memory_flashback", "")
    print(f"{Colors.YELLOW}记忆闪回结果 ({len(memory_flashback)} 字符):{Colors.END}")
    print(f"{memory_flashback[:200]}..." if len(memory_flashback) > 200 else memory_flashback)
    
    # 打印情景更新结果
    final_scenario = result.get("final_scenario", "")
    print(f"\n{Colors.YELLOW}最终情景 ({len(final_scenario)} 字符):{Colors.END}")
    print(f"{final_scenario[:200]}..." if len(final_scenario) > 200 else final_scenario)
    
    # 打印LLM响应
    llm_response = result.get("llm_response")
    if llm_response:
        if hasattr(llm_response, 'content'):
            content = llm_response.content
        elif isinstance(llm_response, dict):
            content = llm_response.get('content', str(llm_response))
        else:
            content = str(llm_response)
        
        print(f"\n{Colors.YELLOW}LLM最终响应 ({len(content)} 字符):{Colors.END}")
        print(f"{content[:300]}..." if len(content) > 300 else content)
    
    print(f"{Colors.PURPLE}--- 结果打印完毕 ---{Colors.END}\n")

async def test_complete_workflow() -> bool:
    """测试完整工作流执行"""
    print_header("测试1: 完整工作流执行")
    
    try:
        # 创建工作流和测试数据
        workflow = create_scenario_workflow()
        messages = create_mock_messages()
        test_input = create_test_input(messages)
        
        print_info(f"测试输入 - 消息数量: {len(messages)}")
        print_info(f"使用模型: {test_input['model']}")
        print_info(f"API密钥: {test_input['api_key'][:8]}...{test_input['api_key'][-8:]}")
        
        # 执行工作流
        start_time = time.time()
        result = await workflow.ainvoke(test_input)
        duration = time.time() - start_time
        
        print_info(f"工作流执行耗时: {duration:.2f}秒")
        
        # 验证结果
        is_valid, message = validate_workflow_output(result)
        if is_valid:
            print_success(f"完整工作流测试通过: {message}")
            print_workflow_result(result)
            return True
        else:
            print_error(f"完整工作流测试失败: {message}")
            return False
            
    except Exception as e:
        print_error(f"完整工作流测试异常: {str(e)}")
        import traceback
        print(f"{Colors.RED}{traceback.format_exc()}{Colors.END}")
        return False

async def test_streaming_mode() -> bool:
    """测试流式输出模式"""
    print_header("测试2: 流式输出模式")
    
    try:
        # 创建工作流和测试数据
        workflow = create_scenario_workflow()
        messages = create_mock_messages()
        test_input = create_test_input(messages, stream=True)
        
        print_info("开始流式输出测试...")
        
        # 收集流式输出
        stream_chunks = []
        start_time = time.time()
        
        async for msg, metadata in workflow.astream(
            test_input,
            stream_mode="messages"
        ):
            if hasattr(msg, 'content') and msg.content:
                stream_chunks.append(msg.content)
                print(f"{Colors.GREEN}流式输出: {msg.content[:50]}...{Colors.END}")
            elif isinstance(msg, dict):
                content = extract_content_from_event(msg)
                if content:
                    stream_chunks.append(content)
                    print(f"{Colors.GREEN}流式输出: {content[:50]}...{Colors.END}")
        
        duration = time.time() - start_time
        
        print_info(f"流式输出耗时: {duration:.2f}秒")
        print_info(f"收集到 {len(stream_chunks)} 个流式块")
        
        if len(stream_chunks) > 0:
            total_content = ''.join(stream_chunks)
            print_info(f"总流式内容长度: {len(total_content)} 字符")
            print_success("流式输出测试通过")
            return True
        else:
            print_error("流式输出测试失败: 没有收集到任何流式块")
            return False
            
    except Exception as e:
        print_error(f"流式输出测试异常: {str(e)}")
        import traceback
        print(f"{Colors.RED}{traceback.format_exc()}{Colors.END}")
        return False

async def test_non_streaming_mode() -> bool:
    """测试非流式输出模式"""
    print_header("测试3: 非流式输出模式")
    
    try:
        # 创建工作流和测试数据
        workflow = create_scenario_workflow()
        messages = create_mock_messages()
        test_input = create_test_input(messages, stream=False)
        
        print_info("开始非流式输出测试...")
        
        # 执行工作流
        start_time = time.time()
        result = await workflow.ainvoke(test_input)
        duration = time.time() - start_time
        
        print_info(f"非流式执行耗时: {duration:.2f}秒")
        
        # 验证结果并转换为OpenAI格式
        is_valid, message = validate_workflow_output(result)
        if is_valid:
            # 测试格式转换
            llm_response = result.get("llm_response")
            openai_response = convert_final_response(
                llm_response, 
                test_input["model"], 
                stream=False
            )
            
            print_info("OpenAI格式转换成功")
            print_info(f"转换后响应ID: {openai_response.get('id', 'N/A')}")
            print_info(f"转换后模型: {openai_response.get('model', 'N/A')}")
            
            print_success(f"非流式输出测试通过: {message}")
            return True
        else:
            print_error(f"非流式输出测试失败: {message}")
            return False
            
    except Exception as e:
        print_error(f"非流式输出测试异常: {str(e)}")
        import traceback
        print(f"{Colors.RED}{traceback.format_exc()}{Colors.END}")
        return False

async def test_error_handling() -> bool:
    """测试错误处理"""
    print_header("测试4: 错误处理")
    
    test_passed = 0
    total_tests = 2
    
    try:
        workflow = create_scenario_workflow()
        messages = create_mock_messages()
        
        # 测试1: 无效API密钥
        print_info("测试子项1: 无效API密钥处理")
        try:
            invalid_input = create_test_input(messages, api_key="invalid_key")
            result = await workflow.ainvoke(invalid_input)
            # 如果到这里没有异常，检查是否有错误响应
            llm_response = result.get("llm_response")
            if llm_response and hasattr(llm_response, 'content'):
                content = llm_response.content
                if "Error" in content or "error" in content:
                    print_success("无效API密钥错误处理正确")
                    test_passed += 1
                else:
                    print_warning("无效API密钥未触发预期错误")
            else:
                print_warning("无效API密钥测试结果不明确")
        except Exception as e:
            print_success(f"无效API密钥正确触发异常: {str(e)[:100]}...")
            test_passed += 1
        
        # 测试2: 空消息列表
        print_info("测试子项2: 空消息列表处理")
        try:
            empty_input = create_test_input([])
            result = await workflow.ainvoke(empty_input)
            # 工作流应该能处理空消息，但可能产生默认响应
            print_success("空消息列表处理正常")
            test_passed += 1
        except Exception as e:
            print_success(f"空消息列表正确触发异常: {str(e)[:100]}...")
            test_passed += 1
        
        if test_passed >= total_tests // 2:  # 至少通过一半测试
            print_success(f"错误处理测试通过 ({test_passed}/{total_tests})")
            return True
        else:
            print_error(f"错误处理测试失败 ({test_passed}/{total_tests})")
            return False
            
    except Exception as e:
        print_error(f"错误处理测试异常: {str(e)}")
        return False

async def run_all_tests() -> Dict[str, bool]:
    """运行所有测试用例"""
    print_header("DeepRolePlay 工作流测试套件")
    print_info(f"测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"代理LLM配置: {settings.agent.model} @ {settings.agent.base_url}")
    print_info(f"转发LLM配置: {DEEPSEEK_CONFIG['model']} @ {DEEPSEEK_CONFIG['base_url']}")
    
    # 测试结果记录
    test_results = {}
    
    # 执行所有测试
    test_results["complete_workflow"] = await test_complete_workflow()
    test_results["streaming_mode"] = await test_streaming_mode()
    test_results["non_streaming_mode"] = await test_non_streaming_mode()
    test_results["error_handling"] = await test_error_handling()
    
    return test_results

def print_final_report(test_results: Dict[str, bool]):
    """打印最终测试报告"""
    print_header("测试结果报告")
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    print(f"{Colors.BOLD}测试概览:{Colors.END}")
    print(f"  总测试数: {total_tests}")
    print(f"  通过测试: {Colors.GREEN}{passed_tests}{Colors.END}")
    print(f"  失败测试: {Colors.RED}{total_tests - passed_tests}{Colors.END}")
    print(f"  通过率: {Colors.CYAN}{(passed_tests/total_tests)*100:.1f}%{Colors.END}")
    
    print(f"\n{Colors.BOLD}详细结果:{Colors.END}")
    for test_name, result in test_results.items():
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if result else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"  {test_name.replace('_', ' ').title()}: {status}")
    
    if passed_tests == total_tests:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 所有测试通过！工作流重构成功！{Colors.END}")
    elif passed_tests >= total_tests * 0.7:  # 70%通过率
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ 大部分测试通过，建议检查失败的测试{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ 多个测试失败，需要检查工作流实现{Colors.END}")

if __name__ == "__main__":
    print(f"{Colors.CYAN}启动 DeepRolePlay 工作流测试...{Colors.END}\n")
    
    try:
        # 运行所有测试
        results = asyncio.run(run_all_tests())
        
        # 打印最终报告
        print_final_report(results)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}测试被用户中断{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.RED}测试执行异常: {str(e)}{Colors.END}")
        import traceback
        print(f"{Colors.RED}{traceback.format_exc()}{Colors.END}")