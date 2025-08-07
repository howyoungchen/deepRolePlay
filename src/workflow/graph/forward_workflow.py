"""
LLM Forwarding Workflow - 独立的LLM转发工作流
从scenario_workflow.py中提取的LLM转发相关功能
"""
import asyncio
import sys
import os
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.manager import settings
from utils.workflow_logger import workflow_logger


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
        # 1. 读取最新情景内容
        from utils.scenario_utils import read_scenario
        current_scenario = await read_scenario()
        
        # 2. 情景注入
        from utils.messages_process import inject_scenario
        injected_messages = inject_scenario(original_messages, current_scenario)
        
        # 3. 创建OpenAI客户端
        client = AsyncOpenAI(
            api_key=final_api_key,
            base_url=base_url
        )
        
        # 4. 调用LLM
        if stream:
            # 流式模式 - 创建包装的生成器来处理<think>标签
            response_stream = await client.chat.completions.create(
                model=final_model,
                messages=injected_messages,
                stream=True,
                temperature=final_temperature
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
                temperature=final_temperature
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
        
        await workflow_logger.log_agent_execution(
            node_type="llm_forwarding",
            inputs=inputs,
            agent_response=agent_response,
            outputs=outputs,
            duration=duration
        )
        
        return {
            "injected_messages": injected_messages,
            "llm_response": llm_response
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        duration = time.time() - start_time
        
        # 记录错误
        await workflow_logger.log_execution_error(
            node_type="llm_forwarding",
            inputs=inputs,
            error_message=str(e),
            error_details=error_details
        )
        
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
    
    # 1. 读取最新情景内容
    from utils.scenario_utils import read_scenario
    current_scenario = await read_scenario()
    
    # 2. 情景注入
    from utils.messages_process import inject_scenario
    injected_messages = inject_scenario(original_messages, current_scenario)
    
    # 3. 创建OpenAI客户端
    client = AsyncOpenAI(
        api_key=final_api_key,
        base_url=base_url
    )
    
    return client, injected_messages, final_model, final_temperature


async def forward_to_llm_non_streaming(original_messages: List[Dict], api_key: str, model: str):
    """
    独立的LLM转发函数（非流式版本）
    在情景更新完成后调用，进行非流式LLM调用
    
    Args:
        original_messages: 原始消息列表
        api_key: API密钥
        model: 模型名称
    
    Returns:
        完整的LLM响应对象
    """
    import time
    start_time = time.time()
    
    try:
        # 准备LLM调用
        client, injected_messages, final_model, final_temperature = await _prepare_llm_call(
            original_messages, api_key, model
        )
        
        # 获取配置用于日志记录
        proxy_config = settings.proxy
        base_url = proxy_config.target_url
        
        # 调用LLM非流式接口
        response = await client.chat.completions.create(
            model=final_model,
            messages=injected_messages,
            stream=False,
            temperature=final_temperature
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
        
        # 日志记录
        await workflow_logger.log_agent_execution(
            node_type="llm_forwarding_non_streaming",
            inputs={
                "model": final_model,
                "messages_count": len(original_messages),
                "temperature": final_temperature
            },
            agent_response={
                "model_config": {
                    "model": final_model,
                    "base_url": base_url,
                    "temperature": final_temperature,
                    "stream": False
                },
                "input_messages": injected_messages,
                "output_content": full_content,
                "reasoning_content": reasoning_content,
                "has_reasoning": bool(reasoning_content),
                "usage_metadata": response.usage.model_dump() if response.usage else {},
                "execution_status": "completed"
            },
            outputs={
                "content_length": len(full_content),
                "duration": duration
            },
            duration=duration
        )
        
        return NonStreamResponse(full_content, response)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        await workflow_logger.log_execution_error(
            node_type="llm_forwarding_non_streaming",
            inputs={"model": model, "messages_count": len(original_messages)},
            error_message=str(e),
            error_details=error_details
        )
        
        print(f"非流式LLM转发执行失败: {str(e)}")
        raise


async def forward_to_llm_streaming(original_messages: List[Dict], api_key: str, model: str):
    """
    独立的LLM转发函数，从工作流中拆分出来
    在情景更新完成后调用，直接进行流式LLM调用
    
    Args:
        original_messages: 原始消息列表
        api_key: API密钥
        model: 模型名称
    
    Yields:
        流式LLM响应块
    """
    import time
    start_time = time.time()
    
    try:
        # 准备LLM调用
        client, injected_messages, final_model, final_temperature = await _prepare_llm_call(
            original_messages, api_key, model
        )
        
        # 获取配置用于日志记录
        proxy_config = settings.proxy
        base_url = proxy_config.target_url
        
        # 调用LLM流式接口
        response_stream = await client.chat.completions.create(
            model=final_model,
            messages=injected_messages,
            stream=True,
            temperature=final_temperature
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
        
        await workflow_logger.log_agent_execution(
            node_type="llm_forwarding_streaming",
            inputs={
                "model": final_model,
                "messages_count": len(original_messages),
                "temperature": final_temperature
            },
            agent_response={
                "model_config": {
                    "model": final_model,
                    "base_url": base_url,
                    "temperature": final_temperature,
                    "stream": True
                },
                "input_messages": injected_messages,
                "output_content": full_content,
                "reasoning_content": collected_reasoning,
                "has_reasoning": bool(collected_reasoning),
                "execution_status": "streaming_completed"
            },
            outputs={
                "content_length": len(full_content),
                "duration": duration
            },
            duration=duration
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        await workflow_logger.log_execution_error(
            node_type="llm_forwarding_streaming",
            inputs={"model": model, "messages_count": len(original_messages)},
            error_message=str(e),
            error_details=error_details
        )
        
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