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
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_prompt}]},
            config={"configurable": {"conversation_history": messages}}
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
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": user_prompt}]
        })
        
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
        
        print(f"Scenario updater node execution failed: {str(e)}")
        return {"final_scenario": "Scenario update failed"}


async def llm_forwarding_node(state: ParentState) -> Dict[str, Any]:
    """LLM转发节点：整合情景注入和LLM调用"""
    import time
    start_time = time.time()
    
    # 准备输入数据
    original_messages = state.get("original_messages", state.get("messages", []))
    api_key = state.get("api_key", "")
    model_name = state.get("model", "")
    stream = state.get("stream", False)
    
    inputs = {
        "messages_count": len(original_messages),
        "model": model_name,
        "stream": stream,
        "has_api_key": bool(api_key)
    }
    
    try:
        # 1. 读取最新情景内容
        from utils.scenario_utils import read_scenario
        current_scenario = await read_scenario()
        
        # 2. 情景注入（作为节点内的前置操作）
        from utils.messages_process import inject_scenario
        injected_messages = inject_scenario(
            original_messages, 
            current_scenario
        )
        
        # 3. 创建LLM模型（使用请求中的配置）
        from langchain_openai import ChatOpenAI
        proxy_config = settings.proxy
        
        # 使用proxy配置中的target_url作为转发LLM的base_url
        # target_url: "https://api.deepseek.com/v1" 
        base_url = proxy_config.target_url
        
        # 构建LLM实例（使用请求中的API密钥和模型名称）
        llm = ChatOpenAI(
            base_url=base_url,
            model=model_name if model_name else "deepseek-chat",
            api_key=api_key if api_key else settings.agent.api_key,
            temperature=0.7,
            streaming=stream
        )
        
        # 4. 转换消息格式为LangChain格式
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        langchain_messages = []
        for msg in injected_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
        
        # 5. 调用LLM
        response = await llm.ainvoke(langchain_messages)
        
        duration = time.time() - start_time
        
        outputs = {
            "injected_messages_count": len(injected_messages),
            "response_content_length": len(response.content) if hasattr(response, 'content') else 0,
            "duration": duration
        }
        
        # 记录日志
        await workflow_logger.log_agent_execution(
            node_type="llm_forwarding",
            inputs=inputs,
            agent_response={"response": response.content if hasattr(response, 'content') else str(response)},
            outputs=outputs,
            duration=duration
        )
        
        return {
            "injected_messages": injected_messages,
            "llm_response": response
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
        from langchain_core.messages import AIMessage
        return {
            "injected_messages": original_messages,
            "llm_response": AIMessage(content=f"Error: {str(e)}")
        }


def create_scenario_workflow():
    """Create the scenario update workflow."""
    builder = StateGraph(ParentState)
    
    # Add nodes
    builder.add_node("memory_flashback", memory_flashback_node)
    builder.add_node("scenario_updater", scenario_updater_node)
    builder.add_node("llm_forwarding", llm_forwarding_node)  # 新增LLM转发节点
    
    # Add edges - 修改边：START → memory_flashback → scenario_updater → llm_forwarding → END
    builder.add_edge(START, "memory_flashback")
    builder.add_edge("memory_flashback", "scenario_updater")
    builder.add_edge("scenario_updater", "llm_forwarding")  # 新增边
    builder.add_edge("llm_forwarding", END)  # 修改结束边
    
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