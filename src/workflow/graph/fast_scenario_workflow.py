"""
Fast Scenario Update Workflow - 四节点快速版本
使用两个LLM节点和两个工具集合节点实现快速情景更新
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
from langchain.chat_models import init_chat_model
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

from config.manager import settings
from utils.workflow_logger import workflow_logger
from src.workflow.tools.re_search_tool import re_search
from src.workflow.tools.read_tool import read_target_file
from src.workflow.tools.edit_tool import edit_file
from utils.scenario_utils import get_scenario_file_path, read_scenario


class FastState(TypedDict):
    """快速工作流状态定义"""
    # 输入参数
    current_scenario: str
    messages: List[Dict[str, Any]]
    
    # 中间状态
    last_ai_message: str
    search_tool_calls: List[Dict[str, Any]]
    search_results: List[str]
    edit_tool_calls: List[Dict[str, Any]]
    
    # 输出结果
    final_scenario: str
    
    # 请求处理相关
    request_id: Optional[str] = None
    original_messages: Optional[List[Dict]] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    stream: Optional[bool] = None


def create_wikipedia_tool():
    """创建Wikipedia搜索工具"""
    api_wrapper = WikipediaAPIWrapper(
        top_k_results=1,
        doc_content_chars_max=2000,
        lang="en"
    )
    
    return WikipediaQueryRun(
        name="wikipedia_search",
        description="搜索Wikipedia信息。输入应该是搜索查询。",
        api_wrapper=api_wrapper
    )


def extract_latest_ai_message(messages: List[Dict[str, Any]], offset: int = 1) -> str:
    """提取最新的AI消息"""
    ai_messages = []
    for msg in messages:
        if msg.get("role") == "assistant":
            ai_messages.append(msg.get("content", ""))
    
    if len(ai_messages) >= offset:
        return ai_messages[-offset]
    elif ai_messages:
        return ai_messages[-1]
    else:
        return ""


async def check_and_init_scenario_file(current_scenario: str) -> str:
    """检查情景文件是否存在，不存在则初始化"""
    if not current_scenario or not current_scenario.strip():
        # 创建新情景文件
        scenario_file_path = get_scenario_file_path()
        initial_scenario = "New roleplay scenario beginning."
        
        # 写入初始情景
        with open(scenario_file_path, 'w', encoding='utf-8') as f:
            f.write(initial_scenario)
        
        print(f"Initializing new scenario file: {scenario_file_path}")
        return initial_scenario
    
    return current_scenario


async def llm_search_node(state: FastState) -> Dict[str, Any]:
    """第一个LLM节点：判断需要搜索的内容并输出工具调用"""
    print("🧠Starting memory flashback node execution...", flush=True)
    print("🔍 Executing search LLM node...", flush=True)
    
    import time
    start_time = time.time()
    
    # 准备输入数据用于日志
    messages = state.get("messages", [])
    current_scenario = state.get("current_scenario", "")
    last_ai_message = extract_latest_ai_message(messages)
    
    inputs = {
        "current_scenario_length": len(current_scenario),
        "messages_count": len(messages),
        "last_ai_message_length": len(last_ai_message),
        "current_scenario_preview": current_scenario[:200] if current_scenario else "[Empty]",
        "last_ai_message_preview": last_ai_message[:200] if last_ai_message else "[Empty]"
    }
    
    try:
        # 导入搜索LLM提示词
        from src.prompts.fast_memory_search_prompts import SEARCH_LLM_PROMPT, SEARCH_USER_TEMPLATE
        
        # 初始化模型
        agent_config = settings.agent
        model = init_chat_model(
            f"openai:{agent_config.model}",
            api_key=agent_config.api_key,
            base_url=agent_config.base_url,
            temperature=agent_config.temperature
        )
        
        # 定义搜索工具（Pydantic模型）
        from pydantic import BaseModel, Field
        
        class SearchMemory(BaseModel):
            """搜索内部记忆"""
            pattern: str = Field(description="正则搜索模式")
        
        class SearchWikipedia(BaseModel):
            """搜索Wikipedia"""
            query: str = Field(description="搜索查询")
        
        # 绑定工具
        search_tools = [SearchMemory, SearchWikipedia]
        model_with_tools = model.bind_tools(search_tools)
        
        # 构建提示
        user_input = SEARCH_USER_TEMPLATE.format(
            current_scenario=current_scenario,
            last_ai_message=last_ai_message
        )
        
        # 记录完整的输入prompt
        print(f"📥 Search LLM Input:", flush=True)
        print(f"  System prompt length: {len(SEARCH_LLM_PROMPT)}", flush=True)
        print(f"  User input length: {len(user_input)}", flush=True)
        print(f"  User input preview: {user_input[:300]}...", flush=True)
        
        # 调用LLM
        response = await model_with_tools.ainvoke([
            {"role": "system", "content": SEARCH_LLM_PROMPT},
            {"role": "user", "content": user_input}
        ])
        
        # 记录完整的输出
        print(f"📤 Search LLM Output:", flush=True)
        print(f"  Response content length: {len(response.content) if hasattr(response, 'content') else 0}", flush=True)
        print(f"  Response content preview: {response.content[:300] if hasattr(response, 'content') else '[No content]'}...", flush=True)
        
        # 提取工具调用
        tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []
        print(f"Search LLM output tool calls count: {len(tool_calls)}")
        for i, tc in enumerate(tool_calls):
            print(f"  {i+1}. {tc.get('name')}: {tc.get('args')}")
        
        duration = time.time() - start_time
        
        outputs = {
            "last_ai_message": last_ai_message,
            "search_tool_calls_count": len(tool_calls),
            "search_tool_calls_names": [tc.get('name') for tc in tool_calls]
        }
        
        # 记录日志到文件
        from utils.workflow_logger import workflow_logger
        await workflow_logger.log_agent_execution(
            node_type="llm_search_fast",
            inputs=inputs,
            agent_response={"messages": [response]} if hasattr(response, 'content') else {"messages": []},
            outputs=outputs,
            duration=duration
        )
        
        return {
            "last_ai_message": last_ai_message,
            "search_tool_calls": tool_calls
        }
        
    except Exception as e:
        duration = time.time() - start_time
        import traceback
        error_details = traceback.format_exc()
        
        # 记录错误日志
        from utils.workflow_logger import workflow_logger
        await workflow_logger.log_execution_error(
            node_type="llm_search_fast",
            inputs=inputs,
            error_message=str(e),
            error_details=error_details
        )
        
        print(f"Search LLM node execution failed: {str(e)}")
        return {
            "last_ai_message": "",
            "search_tool_calls": []
        }


async def tool_search_node(state: FastState) -> Dict[str, Any]:
    """第一个工具节点：执行搜索相关工具"""
    print("🛠️ Executing search tool node...", flush=True)
    
    try:
        tool_calls = state.get("search_tool_calls", [])
        search_results = []
        messages = state.get("messages", [])
        
        # 创建Wikipedia工具
        wikipedia_tool = create_wikipedia_tool()
        
        # 执行工具调用
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            args = tool_call.get("args", {})
            
            try:
                if tool_name == "SearchMemory":
                    # 调用re_search，需要传递config
                    from langchain_core.runnables import RunnableConfig
                    config = RunnableConfig(
                        configurable={
                            "conversation_history": messages
                        }
                    )
                    result = re_search.invoke(args.get("pattern", ""), config)
                    search_results.append(f"[Internal Memory] {result}")
                
                elif tool_name == "SearchWikipedia":
                    # 调用Wikipedia搜索
                    result = wikipedia_tool.invoke(args.get("query", ""))
                    search_results.append(f"[External Knowledge] {result}")
                    
            except Exception as e:
                search_results.append(f"[{tool_name}] Search failed: {str(e)}")
        
        return {"search_results": search_results}
        
    except Exception as e:
        print(f"Search tool node execution failed: {str(e)}")
        return {"search_results": []}


async def llm_edit_node(state: FastState) -> Dict[str, Any]:
    """第二个LLM节点：决定如何编辑情景文件并输出工具调用"""
    print("📖Starting scenario updater node execution...", flush=True)
    print("✏️ Executing edit LLM node...", flush=True)
    
    import time
    start_time = time.time()
    
    # 准备输入数据用于日志
    current_scenario = state.get("current_scenario", "")
    last_ai_message = state.get("last_ai_message", "")
    search_results = state.get("search_results", [])
    scenario_file_path = get_scenario_file_path()
    
    inputs = {
        "current_scenario_length": len(current_scenario),
        "last_ai_message_length": len(last_ai_message),
        "search_results_count": len(search_results),
        "search_results_total_length": sum(len(r) for r in search_results),
        "scenario_file_path": scenario_file_path,
        "current_scenario_preview": current_scenario[:200] if current_scenario else "[Empty]",
        "last_ai_message_preview": last_ai_message[:200] if last_ai_message else "[Empty]",
        "search_results_preview": [r[:100] for r in search_results[:3]]  # 前3个搜索结果的预览
    }
    
    try:
        # 导入编辑LLM提示词
        from src.prompts.fast_scenario_edit_prompts import EDIT_LLM_PROMPT, EDIT_USER_TEMPLATE
        
        # 初始化模型
        agent_config = settings.agent
        model = init_chat_model(
            f"openai:{agent_config.model}",
            api_key=agent_config.api_key,
            base_url=agent_config.base_url,
            temperature=agent_config.temperature
        )
        
        # 定义编辑工具（Pydantic模型）
        from pydantic import BaseModel, Field
        
        class EditScenarioFile(BaseModel):
            """编辑情景文件"""
            file_path: str = Field(description="文件路径")
            old_content: str = Field(description="要替换的旧内容")
            new_content: str = Field(description="新内容")
        
        # 绑定工具
        edit_tools = [EditScenarioFile]
        model_with_tools = model.bind_tools(edit_tools)
        
        # 构建提示
        search_results_text = "\n".join(search_results) if search_results else "No search results"
        
        user_input = EDIT_USER_TEMPLATE.format(
            current_scenario=current_scenario,
            last_ai_message=last_ai_message,
            search_results=search_results_text,
            scenario_file_path=scenario_file_path
        )
        
        # 记录完整的输入prompt
        print(f"📥 Edit LLM Input:", flush=True)
        print(f"  System prompt length: {len(EDIT_LLM_PROMPT)}", flush=True)
        print(f"  User input length: {len(user_input)}", flush=True)
        print(f"  User input preview: {user_input[:300]}...", flush=True)
        print(f"  Current scenario in prompt: {current_scenario[:200]}..." if current_scenario else "  Current scenario: [Empty]", flush=True)
        
        # 调用LLM
        response = await model_with_tools.ainvoke([
            {"role": "system", "content": EDIT_LLM_PROMPT},
            {"role": "user", "content": user_input}
        ])
        
        # 记录完整的输出
        print(f"📤 Edit LLM Output:", flush=True)
        print(f"  Response content length: {len(response.content) if hasattr(response, 'content') else 0}", flush=True)
        print(f"  Response content preview: {response.content[:300] if hasattr(response, 'content') else '[No content]'}...", flush=True)
        
        # 提取工具调用
        tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []
        print(f"Edit LLM output tool calls count: {len(tool_calls)}")
        for i, tc in enumerate(tool_calls):
            print(f"  {i+1}. {tc.get('name')}: {tc.get('args')}")
            if tc.get('name') == 'EditScenarioFile':
                args = tc.get('args', {})
                print(f"    old_content length: {len(args.get('old_content', ''))}")
                print(f"    new_content length: {len(args.get('new_content', ''))}")
                print(f"    old_content preview: {args.get('old_content', '')[:200]}...", flush=True)
                print(f"    new_content preview: {args.get('new_content', '')[:200]}...", flush=True)
        
        duration = time.time() - start_time
        
        outputs = {
            "edit_tool_calls_count": len(tool_calls),
            "edit_tool_calls_names": [tc.get('name') for tc in tool_calls],
            "edit_args_summary": [
                {
                    "name": tc.get('name'),
                    "old_content_length": len(tc.get('args', {}).get('old_content', '')),
                    "new_content_length": len(tc.get('args', {}).get('new_content', ''))
                } for tc in tool_calls if tc.get('name') == 'EditScenarioFile'
            ]
        }
        
        # 记录日志到文件
        from utils.workflow_logger import workflow_logger
        await workflow_logger.log_agent_execution(
            node_type="llm_edit_fast",
            inputs=inputs,
            agent_response={"messages": [response]} if hasattr(response, 'content') else {"messages": []},
            outputs=outputs,
            duration=duration
        )
        
        return {"edit_tool_calls": tool_calls}
        
    except Exception as e:
        duration = time.time() - start_time
        import traceback
        error_details = traceback.format_exc()
        
        # 记录错误日志
        from utils.workflow_logger import workflow_logger
        await workflow_logger.log_execution_error(
            node_type="llm_edit_fast",
            inputs=inputs,
            error_message=str(e),
            error_details=error_details
        )
        
        print(f"Edit LLM node execution failed: {str(e)}")
        return {"edit_tool_calls": []}


async def tool_edit_node(state: FastState) -> Dict[str, Any]:
    """第二个工具节点：执行文件编辑操作"""
    print("📝 Executing edit tool node...", flush=True)
    
    try:
        tool_calls = state.get("edit_tool_calls", [])
        scenario_file_path = get_scenario_file_path()
        
        # 执行工具调用
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            args = tool_call.get("args", {})
            
            try:
                if tool_name == "EditScenarioFile":
                    # 编辑文件
                    result = edit_file.invoke({
                        "file_path": args.get("file_path", scenario_file_path),
                        "old_string": args.get("old_content", ""),
                        "new_string": args.get("new_content", ""),
                        "expected_replacements": 1
                    })
                    print(f"File edit result: {result}")
                    
            except Exception as e:
                print(f"Tool execution failed {tool_name}: {str(e)}")
        
        # 读取最终结果
        await asyncio.sleep(0.5)  # 等待文件写入完成
        final_scenario = await read_scenario()
        
        return {"final_scenario": final_scenario or ""}
        
    except Exception as e:
        print(f"Edit tool node execution failed: {str(e)}")
        return {"final_scenario": state.get("current_scenario", "")}


async def init_scenario_node(state: FastState) -> Dict[str, Any]:
    """初始化节点：读取现有情景文件或创建新文件"""
    print("🚀 Executing scenario file initialization...", flush=True)
    
    try:
        # 尝试读取现有情景文件
        current_scenario = await read_scenario()
        
        if not current_scenario or not current_scenario.strip():
            # 如果文件不存在或为空，创建新的情景文件
            scenario_file_path = get_scenario_file_path()
            initial_scenario = "New roleplay scenario beginning."
            
            # 写入初始情景
            os.makedirs(os.path.dirname(scenario_file_path), exist_ok=True)
            with open(scenario_file_path, 'w', encoding='utf-8') as f:
                f.write(initial_scenario)
            
            print(f"Initializing new scenario file: {scenario_file_path}")
            current_scenario = initial_scenario
        else:
            print(f"Read existing scenario file, length: {len(current_scenario)}")
        
        return {"current_scenario": current_scenario}
        
    except Exception as e:
        print(f"Scenario file initialization failed: {str(e)}")
        return {"current_scenario": "New roleplay scenario beginning."}


def create_fast_scenario_workflow():
    """创建快速情景更新工作流"""
    builder = StateGraph(FastState)
    
    # 添加五个节点（包含初始化节点）
    builder.add_node("init_scenario", init_scenario_node)
    builder.add_node("llm_search", llm_search_node)
    builder.add_node("tool_search", tool_search_node)
    builder.add_node("llm_edit", llm_edit_node)
    builder.add_node("tool_edit", tool_edit_node)
    
    # 添加边：线性流程
    builder.add_edge(START, "init_scenario")
    builder.add_edge("init_scenario", "llm_search")
    builder.add_edge("llm_search", "tool_search")
    builder.add_edge("tool_search", "llm_edit")
    builder.add_edge("llm_edit", "tool_edit")
    builder.add_edge("tool_edit", END)
    
    return builder.compile()


async def test_fast_workflow():
    """测试快速工作流"""
    print("Starting fast scenario update workflow test...")
    
    # 创建工作流
    workflow = create_fast_scenario_workflow()
    
    # 模拟输入
    test_input = {
        "current_scenario": "这是一个魔法学院的场景",
        "messages": [
            {"role": "user", "content": "教我一些魔法咒语"},
        ]
    }
    
    try:
        # 执行工作流（初始化在工作流内部完成）
        result = await workflow.ainvoke(test_input)
        print(f"✅ Fast workflow execution successful")
        print(f"Final scenario length: {len(result.get('final_scenario', ''))}")
        print(f"Final scenario content preview: {result.get('final_scenario', '')[:200]}...")
        
    except Exception as e:
        print(f"❌ Fast workflow execution failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_fast_workflow())