"""
LLM Forwarding Workflow - 独立的LLM转发工作流
从scenario_workflow.py中提取的LLM转发相关功能
"""
import asyncio
import sys
import os
from typing import Dict, Any, List, Optional
from src.api.proxy import ChatCompletionRequest
from typing_extensions import TypedDict

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.manager import settings
from utils.simple_logger import save_log
from src.workflow.tools.scenario_table_tools import scenario_manager

# 模块级初始化scenario_manager
scenario_manager.init(settings.scenario.file_path)

# 参数模式定义
# v3.2兼容模式：只传递基础参数（移除了可能导致问题的参数）
V32_COMPATIBLE_PARAMS = {
    'model', 'temperature'  # v3.2实际只传递了这两个核心参数
}

# 当前扩展模式：传递所有参数（保持现有功能）
EXTENDED_MODE_PARAMS = {
    'model', 'temperature', 'max_tokens', 'top_p', 'frequency_penalty',
    'presence_penalty', 'stop', 'n', 'logprobs', 'echo', 'suffix',
    'max_completion_tokens', 'logit_bias', 'user', 'seed'
}


class LLMState(TypedDict):
    """LLM转发工作流状态定义"""
    request_id: Optional[str]
    original_messages: List[Dict]
    api_key: str
    model: str
    stream: bool
    injected_messages: Optional[List[Dict]]
    llm_response: Optional[Any]


async def llm_forwarding_node(state: LLMState) -> Dict[str, Any]:
    """LLM转发节点：使用原生OpenAI SDK，支持推理内容获取"""
    import time
    from openai import AsyncOpenAI
    start_time = time.time()
    
    # 准备输入数据
    original_messages = state.get("original_messages", [])
    api_key = state.get("api_key", "")
    model_name = state.get("model", "")
    stream = state.get("stream", False)
    
    # 使用代理配置或默认配置
    proxy_config = settings.proxy
    agent_config = settings.agent
    base_url = proxy_config.target_url
    final_api_key = api_key if api_key else agent_config.api_key
    final_model = model_name if model_name else "deepseek-chat"
    final_temperature = agent_config.temperature
    
    inputs = {
        "model": final_model,
        "stream": stream,
        "base_url": base_url,
        "temperature": final_temperature,
        "messages_count": len(original_messages)
    }
    
    try:
        # 1. 读取表格内容
        current_scenario = scenario_manager.get_all_pretty_tables(description=True, operation_guide=False)
        
        # 2. 情景注入
        from utils.messages_process import inject_scenario
        injected_messages = inject_scenario(original_messages, current_scenario)
        
        # 3. 创建OpenAI客户端
        client = AsyncOpenAI(
            api_key=final_api_key,
            base_url=base_url
        )
        
        # 4. 调用LLM
        # 构建额外参数
        extra_body = {"provider": {"only": [proxy_config.provider]}} if proxy_config.provider else {}
        
        if stream:
            # 流式模式 - 创建包装的生成器来处理<think>标签
            response_stream = await client.chat.completions.create(
                model=final_model,
                messages=injected_messages,
                stream=True,
                temperature=final_temperature,
                extra_body=extra_body
            )
            
            # 创建处理<think>标签的包装生成器
            async def reasoning_stream_wrapper():
                reasoning_started = False
                content_started = False
                
                async for chunk in response_stream:
                    if not chunk.choices:
                        yield chunk
                        continue
                        
                    delta = chunk.choices[0].delta
                    
                    # 处理推理过程
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        if not reasoning_started:
                            # 创建一个包含<think>标签的新chunk
                            from copy import deepcopy
                            think_start_chunk = deepcopy(chunk)
                            think_start_chunk.choices[0].delta.content = "<think>\n"
                            if hasattr(think_start_chunk.choices[0].delta, 'reasoning_content'):
                                think_start_chunk.choices[0].delta.reasoning_content = None
                            yield think_start_chunk
                            reasoning_started = True
                        
                        # 创建包含推理内容的chunk (将reasoning_content转为content)
                        from copy import deepcopy
                        reasoning_chunk = deepcopy(chunk)
                        reasoning_chunk.choices[0].delta.content = delta.reasoning_content
                        reasoning_chunk.choices[0].delta.reasoning_content = None
                        yield reasoning_chunk
                    
                    # 处理正文回答
                    elif hasattr(delta, "content") and delta.content:
                        if reasoning_started and not content_started:
                            # 创建包含</think>结束标签的chunk
                            from copy import deepcopy
                            think_end_chunk = deepcopy(chunk)
                            think_end_chunk.choices[0].delta.content = "\n</think>\n"
                            yield think_end_chunk
                            content_started = True
                        
                        # 直接传递原始chunk
                        yield chunk
                    else:
                        # 传递其他chunk（如finish_reason等）
                        yield chunk
            
            llm_response = reasoning_stream_wrapper()
            
        else:
            # 非流式模式
            response = await client.chat.completions.create(
                model=final_model,
                messages=injected_messages,
                stream=False,
                temperature=final_temperature,
                extra_body=extra_body
            )
            
            # 构建完整响应内容
            reasoning_content = getattr(response.choices[0].message, 'reasoning_content', '') or ""
            main_content = response.choices[0].message.content or ""
            
            # 组合推理内容和正文内容
            if reasoning_content:
                full_content = f"<think>\n{reasoning_content}\n</think>\n{main_content}"
            else:
                full_content = main_content
            
            # 创建兼容的响应对象
            class NonStreamResponse:
                def __init__(self, content, reasoning_content=""):
                    self.content = content
                    self.reasoning_content = reasoning_content
                    self.response_metadata = {"model": final_model}
                    self.usage_metadata = {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0
                    }
            
            llm_response = NonStreamResponse(full_content, reasoning_content)
        
        duration = time.time() - start_time
        
        outputs = {
            "injected_messages": injected_messages,
            "injected_messages_count": len(injected_messages),
            "current_scenario": current_scenario,
            "response_content_length": len(llm_response.content) if not stream else 0,
            "has_reasoning_content": bool(getattr(llm_response, 'reasoning_content', '')) if not stream else False,
            "duration": duration,
            "model_used": final_model
        }
        
        # 在流式模式下，我们无法提前知道完整内容，因此日志记录简化
        if stream:
            agent_response = {
                "messages": [],
                "model_config": {"model": final_model, "base_url": base_url, "stream": True},
                "input_messages": injected_messages,
                "output_content": "[Streaming Response]",
                "execution_status": "streaming_started"
            }
        else:
            agent_response = {
                "messages": [],
                "model_config": {
                    "model": final_model,
                    "base_url": base_url,
                    "temperature": final_temperature,
                    "stream": stream
                },
                "input_messages": injected_messages,
                "output_content": llm_response.content,
                "reasoning_content": getattr(llm_response, 'reasoning_content', ''),
                "usage_metadata": llm_response.usage_metadata,
                "execution_status": "completed",
                "content_length": len(llm_response.content),
                "has_reasoning": bool(getattr(llm_response, 'reasoning_content', ''))
            }
        
        # 保存日志
        from datetime import datetime
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "node_type": "llm_forwarding",
            "model_config": {
                "model": final_model,
                "base_url": base_url,
                "temperature": final_temperature,
                "stream": stream
            },
            "model_input": injected_messages,
            "model_output": llm_response.content
        }
        
        log_file = f"./logs/workflow/{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}_forwarding.json"
        save_log(log_file, log_data)
        
        return {
            "injected_messages": injected_messages,
            "llm_response": llm_response
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        duration = time.time() - start_time
        
        # 错误不记录日志，只输出到控制台
        
        print(f"LLM forwarding node execution failed: {str(e)}")
        
        # 返回错误响应
        class ErrorResponse:
            def __init__(self, content):
                self.content = content
                self.response_metadata = {}
                self.usage_metadata = {}
        
        return {
            "injected_messages": original_messages,
            "llm_response": ErrorResponse(f"Error: {str(e)}")
        }


async def _prepare_llm_call(original_messages: List[Dict], api_key: str, model: str):
    """
    准备LLM调用的共享逻辑
    
    Returns:
        tuple: (client, injected_messages, final_model, final_temperature)
    """
    from openai import AsyncOpenAI
    
    # 使用代理配置或默认配置
    proxy_config = settings.proxy
    agent_config = settings.agent
    base_url = proxy_config.target_url
    # 注意：这里应该使用传入的api_key，而不是代理的api_key
    # 如果没有提供api_key，应该让请求失败，而不是使用代理的密钥
    final_api_key = api_key if api_key else ""
    final_model = model if model else "deepseek-chat"
    final_temperature = agent_config.temperature
    
    # 1. 读取表格内容
    current_scenario = scenario_manager.get_all_pretty_tables(description=True, operation_guide=False)
    
    # 2. 情景注入
    from utils.messages_process import inject_scenario
    injected_messages = inject_scenario(original_messages, current_scenario)
    
    # 3. 创建OpenAI客户端
    proxy_config = settings.proxy
    client = AsyncOpenAI(
        api_key=final_api_key,
        base_url=base_url
    )
    
    return client, injected_messages, final_model, final_temperature


async def forward_to_llm_non_streaming(original_messages: List[Dict], api_key: str, chat_request: ChatCompletionRequest):
    """
    独立的LLM转发函数（非流式版本）
    在情景更新完成后调用，进行非流式LLM调用
    
    Args:
        original_messages: 原始消息列表
        api_key: API密钥
        chat_request: 完整的聊天请求对象
    
    Returns:
        完整的LLM响应对象
    """
    import time
    start_time = time.time()
    
    try:
        # 准备LLM调用
        client, injected_messages, final_model, final_temperature = await _prepare_llm_call(
            original_messages, api_key, chat_request.model
        )
        
        # 获取配置用于日志记录
        proxy_config = settings.proxy
        
        # 根据配置决定使用哪种参数模式
        if proxy_config.allow_extra_params:
            # 扩展模式：提取并传递所有参数
            all_params = chat_request.model_dump(exclude={'messages', 'stream'})
            
            # 分离标准 OpenAI 参数和扩展参数
            standard_params = {}
            extra_params = {}
            
            for key, value in all_params.items():
                if key in EXTENDED_MODE_PARAMS and value is not None:
                    standard_params[key] = value
                else:
                    extra_params[key] = value
            
            # 构建 extra_body
            extra_body = {}
            if proxy_config.provider:
                extra_body["provider"] = {"only": [proxy_config.provider]}
            extra_body.update(extra_params)
            
            # 调用LLM非流式接口
            response = await client.chat.completions.create(
                messages=injected_messages,
                stream=False,
                extra_body=extra_body,
                **standard_params  # 传递所有标准参数
            )
        else:
            # v3.2兼容模式：只传递必要参数
            extra_body = {"provider": {"only": [proxy_config.provider]}} if proxy_config.provider else {}
            
            response = await client.chat.completions.create(
                model=final_model,
                messages=injected_messages,
                stream=False,
                temperature=final_temperature,
                extra_body=extra_body
            )
        
        # 构建完整响应内容
        reasoning_content = getattr(response.choices[0].message, 'reasoning_content', '') or ""
        main_content = response.choices[0].message.content or ""
        
        # 组合推理内容和正文内容
        if reasoning_content:
            full_content = f"<think>\n{reasoning_content}\n</think>\n{main_content}"
        else:
            full_content = main_content
        
        # 创建兼容的响应对象
        class NonStreamResponse:
            def __init__(self, content, response_obj):
                self.content = content
                self.reasoning_content = reasoning_content
                self.response_metadata = {"model": final_model}
                self.usage_metadata = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
                self.raw_response = response_obj
        
        duration = time.time() - start_time
        
        # 保存日志
        from datetime import datetime
        
        # 获取完整的请求参数配置
        full_request_config = chat_request.model_dump()
        full_request_config['messages'] = injected_messages  # 使用注入后的消息
        full_request_config['target_url'] = proxy_config.target_url  # 添加目标URL
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "node_type": "llm_forwarding_non_streaming",
            "request_config": full_request_config,  # 保存完整的请求配置
            "model_output": full_content
        }
        
        log_file = f"./logs/workflow/{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}_non_streaming.json"
        save_log(log_file, log_data)
        
        return NonStreamResponse(full_content, response)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        # 错误不记录日志，只输出到控制台
        
        print(f"非流式LLM转发执行失败: {str(e)}")
        raise


async def forward_to_llm_streaming(original_messages: List[Dict], api_key: str, chat_request: ChatCompletionRequest):
    """
    独立的LLM转发函数，从工作流中拆分出来
    在情景更新完成后调用，直接进行流式LLM调用
    
    Args:
        original_messages: 原始消息列表
        api_key: API密钥
        chat_request: 完整的聊天请求对象
    
    Yields:
        流式LLM响应块
    """
    import time
    start_time = time.time()
    
    try:
        # 准备LLM调用
        client, injected_messages, final_model, final_temperature = await _prepare_llm_call(
            original_messages, api_key, chat_request.model
        )
        
        # 获取配置用于日志记录
        proxy_config = settings.proxy
        
        # 根据配置决定使用哪种参数模式
        if proxy_config.allow_extra_params:
            # 扩展模式：提取并传递所有参数
            all_params = chat_request.model_dump(exclude={'messages', 'stream'})
            
            # 分离标准 OpenAI 参数和扩展参数
            standard_params = {}
            extra_params = {}
            
            for key, value in all_params.items():
                if key in EXTENDED_MODE_PARAMS and value is not None:
                    standard_params[key] = value
                else:
                    extra_params[key] = value
            
            # 构建 extra_body
            extra_body = {}
            if proxy_config.provider:
                extra_body["provider"] = {"only": [proxy_config.provider]}
            extra_body.update(extra_params)
            
            # 调用LLM流式接口
            response_stream = await client.chat.completions.create(
                messages=injected_messages,
                stream=True,
                extra_body=extra_body,
                **standard_params  # 传递所有标准参数
            )
        else:
            # v3.2兼容模式：只传递必要参数
            extra_body = {"provider": {"only": [proxy_config.provider]}} if proxy_config.provider else {}
            
            response_stream = await client.chat.completions.create(
                model=final_model,
                messages=injected_messages,
                stream=True,
                temperature=final_temperature,
                extra_body=extra_body
            )
        
        # 5. 创建处理<think>标签的包装生成器和内容收集器
        reasoning_started = False
        content_started = False
        collected_reasoning = ""
        collected_content = ""
        
        async for chunk in response_stream:
            if not chunk.choices:
                yield chunk
                continue
                
            delta = chunk.choices[0].delta
            
            # 处理推理过程
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                # 收集推理内容
                collected_reasoning += delta.reasoning_content
                
                if not reasoning_started:
                    # 创建一个包含<think>标签的新chunk
                    from copy import deepcopy
                    think_start_chunk = deepcopy(chunk)
                    think_start_chunk.choices[0].delta.content = "<think>\n"
                    if hasattr(think_start_chunk.choices[0].delta, 'reasoning_content'):
                        think_start_chunk.choices[0].delta.reasoning_content = None
                    yield think_start_chunk
                    reasoning_started = True
                
                # 创建包含推理内容的chunk (将reasoning_content转为content)
                from copy import deepcopy
                reasoning_chunk = deepcopy(chunk)
                reasoning_chunk.choices[0].delta.content = delta.reasoning_content
                reasoning_chunk.choices[0].delta.reasoning_content = None
                yield reasoning_chunk
            
            # 处理正文回答
            elif hasattr(delta, "content") and delta.content:
                # 收集正文内容
                collected_content += delta.content
                
                if reasoning_started and not content_started:
                    # 创建包含</think>结束标签的chunk
                    from copy import deepcopy
                    think_end_chunk = deepcopy(chunk)
                    think_end_chunk.choices[0].delta.content = "\n</think>\n"
                    yield think_end_chunk
                    content_started = True
                
                # 直接传递原始chunk
                yield chunk
            else:
                # 传递其他chunk（如finish_reason等）
                yield chunk
        
        # 完整的日志记录（流式完成后）
        duration = time.time() - start_time
        
        # 组合完整的输出内容
        if collected_reasoning:
            full_content = f"<think>\n{collected_reasoning}\n</think>\n{collected_content}"
        else:
            full_content = collected_content
        
        # 保存日志
        from datetime import datetime
        
        # 获取完整的请求参数配置
        full_request_config = chat_request.model_dump()
        full_request_config['messages'] = injected_messages  # 使用注入后的消息
        full_request_config['target_url'] = proxy_config.target_url  # 添加目标URL
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "node_type": "llm_forwarding_streaming",
            "request_config": full_request_config,  # 保存完整的请求配置
            "model_output": full_content
        }
        
        log_file = f"./logs/workflow/{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}_streaming.json"
        save_log(log_file, log_data)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        # 错误不记录日志，只输出到控制台
        
        print(f"流式LLM转发执行失败: {str(e)}")
        
        # 创建错误响应chunk
        class ErrorChunk:
            def __init__(self, error_content):
                self.choices = [type('Choice', (), {
                    'delta': type('Delta', (), {
                        'content': f"Error: {error_content}",
                        'role': 'assistant'
                    })()
                })()]
        
        yield ErrorChunk(str(e))