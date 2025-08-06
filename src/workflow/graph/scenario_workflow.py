"""
Scenario Update Workflow - Integrating Memory Flashback and Scenario Update using a LangGraph Parent Graph
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

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from config.manager import settings
from utils.workflow_logger import workflow_logger
from src.prompts.memory_flashback_prompts import MEMORY_FLASHBACK_PROMPT, MEMORY_FLASHBACK_USER_TEMPLATE
from src.prompts.scenario_updater_prompts import SCENARIO_UPDATER_PROMPT, SCENARIO_UPDATER_USER_TEMPLATE
from src.workflow.tools.sequential_thinking import sequential_thinking
from src.workflow.tools.re_search_tool import re_search
from src.workflow.tools.write_tool import write_file
from src.workflow.tools.read_tool import read_target_file
from src.workflow.tools.edit_tool import edit_file

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper



# Create Wikipedia search tool
def create_wikipedia_tool():
    """Create a Wikipedia search tool."""
    api_wrapper = WikipediaAPIWrapper(
        top_k_results=1,  # Return the top 1 search result
        doc_content_chars_max=2000,  # Maximum characters per document
        lang="en"  # Use English Wikipedia
    )
    
    wikipedia_tool = WikipediaQueryRun(
        name="wikipedia_search",
        description="Search for information on Wikipedia. The input should be a search query.",
        api_wrapper=api_wrapper
    )
    
    return wikipedia_tool




class ParentState(TypedDict):
    """Parent graph state definition."""
    # Input parameters
    current_scenario: str       # Current scenario file content
    messages: List[Dict[str, Any]]  # Complete list of messages
    
    # Intermediate state
    memory_flashback: str      # Memory flashback result
    last_ai_message: str       # Latest AI message extracted from messages
    
    # Output results
    final_scenario: str        # Final updated scenario
    
    # 新增字段 - 请求处理相关（使用Optional避免必需字段错误）
    request_id: Optional[str] = None                    # 请求追踪ID
    original_messages: Optional[List[Dict]] = None      # 原始消息（未注入情景）
    injected_messages: Optional[List[Dict]] = None      # 注入情景后的消息
    llm_response: Optional[Any] = None                  # 最终LLM响应
    api_key: Optional[str] = None                       # API密钥（从请求中提取）
    model: Optional[str] = None                         # 模型名称（从请求中提取）
    stream: Optional[bool] = None                       # 是否流式响应


def create_model():
    """Create a ChatOpenAI model instance."""
    agent_config = settings.agent
    return ChatOpenAI(
        base_url=agent_config.base_url,
        model=agent_config.model,
        api_key=agent_config.api_key,
        temperature=agent_config.temperature,
        max_tokens=agent_config.max_tokens,
        top_p=agent_config.top_p
    )


def extract_latest_ai_message(messages: List[Dict[str, Any]], offset: int = 1) -> str:
    """Extract the nth-to-last AI message from the message list."""
    ai_messages = []
    for msg in messages:
        if msg.get("role") == "assistant":
            ai_messages.append(msg.get("content", ""))
    
    if len(ai_messages) >= offset:
        return ai_messages[-offset]  # Return the nth-to-last AI message
    elif ai_messages:
        return ai_messages[-1]  # If there are fewer than offset messages, return the last one
    else:
        return ""  # No AI message





def extract_memory_flashback_result(response: Dict[str, Any]) -> str:
    """Extract the memory flashback result from the agent response."""
    try:
        messages = response.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content') and last_message.content:
                content = last_message.content.strip()
                return f"<memory_flashback>\n{content}\n</memory_flashback>"
        
        return "<memory_flashback>\nNo relevant historical memory available.\n</memory_flashback>"
        
    except Exception as e:
        print(f"Failed to extract memory flashback result: {str(e)}")
        return "<memory_flashback>\nError during memory search, unable to retrieve historical information.\n</memory_flashback>"






async def memory_flashback_node(state: ParentState) -> Dict[str, Any]:
    """Memory flashback node function."""
    # 检查是否开启only_forward模式，如果是则跳过该节点
    if settings.langgraph.only_forward:
        return {
            "memory_flashback": "",
            "last_ai_message": ""
        }
    
    import time
    start_time = time.time()
    
    # Prepare input data
    messages = state.get("messages", [])
    langgraph_config = settings.langgraph
    offset = langgraph_config.history_ai_message_offset
    last_ai_message = extract_latest_ai_message(messages, offset)
    
    inputs = {
        "current_scenario": state.get("current_scenario", ""),
        "messages_count": len(messages),
        "last_ai_message_length": len(last_ai_message),
        "history_offset": offset
    }
    
    try:
        # ================ Create Model and Agent ================
        wikipedia_tool = create_wikipedia_tool()
        model = create_model()
        agent_config = settings.agent
        
        agent = create_react_agent(
            model=model,
            tools=[sequential_thinking, re_search, wikipedia_tool],
            prompt=MEMORY_FLASHBACK_PROMPT,
            debug=agent_config.debug,
        )
        
        # ================ Set History and Build Prompt ================
        user_prompt = MEMORY_FLASHBACK_USER_TEMPLATE.format(
            current_scenario=state["current_scenario"] if state["current_scenario"] else "[No scenario information available]",
            last_ai_message=last_ai_message if last_ai_message else "[No latest message available]"
        )
        
        # ================ Invoke Agent for Memory Flashback ================
        recursion_limit = 2 * agent_config.max_iterations + 1
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_prompt}]},
            config={"configurable": {"conversation_history": messages}, "recursion_limit": recursion_limit}
        )
        
        # ================ Extract and Process Result ================
        memory_result = extract_memory_flashback_result(response)
        duration = time.time() - start_time
        
        outputs = {
            "memory_flashback": memory_result,
            "last_ai_message": last_ai_message,
            "result_length": len(memory_result) if memory_result else 0
        }
        
        # Log workflow execution
        await workflow_logger.log_agent_execution(
            node_type="memory_flashback",
            inputs=inputs,
            agent_response=response,
            outputs=outputs,
            duration=duration
        )
        
        return {
            "memory_flashback": memory_result,
            "last_ai_message": last_ai_message
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        duration = time.time() - start_time
        
        # Log error
        await workflow_logger.log_execution_error(
            node_type="memory_flashback",
            inputs=inputs,
            error_message=str(e),
            error_details=error_details
        )
        
        return {
            "memory_flashback": "=== Memory Flashback ===\n\nError during memory search, unable to retrieve historical information.",
            "last_ai_message": ""
        }


async def scenario_updater_node(state: ParentState) -> Dict[str, Any]:
    """Scenario updater node function."""
    # 检查是否开启only_forward模式，如果是则跳过该节点
    if settings.langgraph.only_forward:
        return {"final_scenario": state.get("current_scenario", "")}
    
    import time
    start_time = time.time()
    
    # Prepare input data
    current_scenario = state.get("current_scenario", "")
    last_ai_message = state.get("last_ai_message", "")
    memory_flashback = state.get("memory_flashback", "")
    
    inputs = {
        "current_scenario_length": len(current_scenario),
        "last_ai_message_length": len(last_ai_message),
        "memory_flashback_length": len(memory_flashback),
        "scenario_exists": bool(current_scenario and current_scenario.strip())
    }
    
    print(f"Starting scenario update. Current scenario length: {len(current_scenario)}, AI message length: {len(last_ai_message)}, Memory flashback length: {len(memory_flashback)}")
    
    try:
        
        # ================ Create Model and Agent ================
        model = create_model()
        agent_config = settings.agent
        
        agent = create_react_agent(
            model=model,
            tools=[write_file, read_target_file, edit_file, sequential_thinking],
            prompt=SCENARIO_UPDATER_PROMPT,
            debug=agent_config.debug,
        )
        
        # ================ Build Prompt ================
        from utils.scenario_utils import get_scenario_file_path
        scenario_file_path = get_scenario_file_path()
        
        user_prompt = SCENARIO_UPDATER_USER_TEMPLATE.format(
            current_scenario=current_scenario if current_scenario else "[No current scenario]",
            last_ai_message=last_ai_message if last_ai_message else "[No latest message available]",
            memory_flashback=memory_flashback if memory_flashback else "[No memory flashback information available]",
            scenario_file_path=scenario_file_path
        )
        
        # ================ Invoke Agent for Scenario Update ================
        recursion_limit = 2 * agent_config.max_iterations + 1
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_prompt}]},
            config={"recursion_limit": recursion_limit}
        )
        
        # ================ Read and Process Result ================
        from utils.scenario_utils import read_scenario
        # Wait a short period to ensure file writing is complete
        await asyncio.sleep(0.5)
        scenario_result = await read_scenario()
        
        duration = time.time() - start_time
        
        outputs = {
            "final_scenario_length": len(scenario_result) if scenario_result else 0,
            "update_successful": bool(scenario_result and scenario_result.strip())
        }
        
        if scenario_result and scenario_result.strip():
            print(f"Scenario update successful, result length: {len(scenario_result)}")
        else:
            print("Scenario update did not produce a valid result")
            scenario_result = "Scenario update failed"
        
        # Log workflow execution
        await workflow_logger.log_agent_execution(
            node_type="scenario_updater",
            inputs=inputs,
            agent_response=response,
            outputs=outputs,
            duration=duration
        )
        
        return {"final_scenario": scenario_result}
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        duration = time.time() - start_time
        
        # Log error
        await workflow_logger.log_execution_error(
            node_type="scenario_updater",
            inputs=inputs,
            error_message=str(e),
            error_details=error_details
        )
        
        try:
            print(f"Scenario updater node execution failed: {str(e)}")
        except UnicodeEncodeError:
            print(f"Scenario updater node execution failed: [encoding error in message]")
        return {"final_scenario": "Scenario update failed"}


async def llm_forwarding_node(state: ParentState) -> Dict[str, Any]:
    """LLM转发节点：使用原生OpenAI SDK，支持推理内容获取"""
    import time
    from openai import AsyncOpenAI
    start_time = time.time()
    
    # 准备输入数据
    original_messages = state.get("original_messages", state.get("messages", []))
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
                            think_start_chunk.choices[0].delta.content = "<think>"
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
                            think_end_chunk.choices[0].delta.content = "</think>\n"
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
    from openai import AsyncOpenAI
    start_time = time.time()
    
    # 使用代理配置或默认配置
    proxy_config = settings.proxy
    agent_config = settings.agent
    base_url = proxy_config.target_url
    final_api_key = api_key if api_key else agent_config.api_key
    final_model = model if model else "deepseek-chat"
    final_temperature = agent_config.temperature
    
    inputs = {
        "model": final_model,
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
        
        # 4. 调用LLM流式接口
        response_stream = await client.chat.completions.create(
            model=final_model,
            messages=injected_messages,
            stream=True,
            temperature=final_temperature
        )
        
        # 5. 创建处理<think>标签的包装生成器
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
                    think_start_chunk.choices[0].delta.content = "<think>"
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
                    think_end_chunk.choices[0].delta.content = "</think>\n"
                    yield think_end_chunk
                    content_started = True
                
                # 直接传递原始chunk
                yield chunk
            else:
                # 传递其他chunk（如finish_reason等）
                yield chunk
        
        duration = time.time() - start_time
        
        outputs = {
            "injected_messages": injected_messages,
            "injected_messages_count": len(injected_messages),
            "current_scenario": current_scenario,
            "duration": duration,
            "model_used": final_model
        }
        
        # 记录日志（简化版）
        agent_response = {
            "messages": [],
            "model_config": {"model": final_model, "base_url": base_url, "stream": True},
            "input_messages": injected_messages,
            "output_content": "[Streaming Response]",
            "execution_status": "streaming_completed"
        }
        
        await workflow_logger.log_agent_execution(
            node_type="llm_forwarding_standalone",
            inputs=inputs,
            agent_response=agent_response,
            outputs=outputs,
            duration=duration
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        duration = time.time() - start_time
        
        # 记录错误
        await workflow_logger.log_execution_error(
            node_type="llm_forwarding_standalone",
            inputs=inputs,
            error_message=str(e),
            error_details=error_details
        )
        
        print(f"独立LLM转发执行失败: {str(e)}")
        
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


def create_scenario_workflow():
    """Create the scenario update workflow."""
    builder = StateGraph(ParentState)
    
    # Add nodes - 只保留情景更新相关节点
    builder.add_node("memory_flashback", memory_flashback_node)
    builder.add_node("scenario_updater", scenario_updater_node)
    
    # Add edges - 移除llm_forwarding节点：START → memory_flashback → scenario_updater → END
    builder.add_edge(START, "memory_flashback")
    builder.add_edge("memory_flashback", "scenario_updater")
    builder.add_edge("scenario_updater", END)  # 直接结束
    
    return builder.compile()


def extract_latest_messages(messages: List[Dict[str, Any]]) -> str:
    """Extract the latest AI message from the message list."""
    last_ai_message = ""
    
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "assistant" and not last_ai_message:
            last_ai_message = msg.get("content", "")
            break
    
    return last_ai_message


# Test function for streaming events
async def test_workflow_streaming_events():
    """Test workflow streaming events."""
    from utils.pretty_print import pretty_print_stream_events
    
    print("Starting test for workflow streaming events...")
    
    # Create workflow
    workflow = create_scenario_workflow()
    
    # Mock input
    test_input = {
        "current_scenario": "This is a scene at a magic academy",
        "messages": [
            {"role": "user", "content": "Teach me some magic spells"},
            {"role": "assistant", "content": "Let me teach you a few basic magic spells. First is Lumos, a spell for illumination..."}
        ]
    }
    
    try:
        # Use astream_events to get streaming events and pretty-print the output
        async for event in workflow.astream_events(test_input, version="v2"):
            pretty_print_stream_events(event)
                        
    except Exception as e:
        print(f"❌ Streaming event test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_workflow_streaming_events())