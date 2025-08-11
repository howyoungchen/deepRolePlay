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
from src.workflow.tools.scenario_table_tools import scenario_manager, create_row, delete_row, update_cell

# 模块级初始化scenario_manager
scenario_manager.init(settings.scenario.file_path)


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




async def llm_search_node(state: FastState) -> Dict[str, Any]:
    """第一个LLM节点：判断需要搜索的内容并输出工具调用"""
    print("🔍 Memory search node executing...", flush=True)
    
    import time
    start_time = time.time()
    
    # 准备输入数据用于日志
    messages = state.get("messages", [])
    current_scenario = state.get("current_scenario", "")
    last_ai_message = extract_latest_ai_message(messages, settings.langgraph.last_ai_messages_index)
    
    inputs = {
        "current_scenario_length": len(current_scenario),
        "messages_count": len(messages),
        "last_ai_message_length": len(last_ai_message),
        "current_scenario": current_scenario if current_scenario else "[Empty]",
        "last_ai_message": last_ai_message if last_ai_message else "[Empty]"
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
        
        # 简洁的输入信息
        print(f"  Messages: {len(messages)}, Scenario length: {len(current_scenario)}", flush=True)
        
        # 调用LLM
        response = await model_with_tools.ainvoke([
            {"role": "system", "content": SEARCH_LLM_PROMPT},
            {"role": "user", "content": user_input}
        ])
        
        # 提取工具调用
        tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []
        print(f"  Planned {len(tool_calls)} search operations: {[tc.get('name') for tc in tool_calls]}", flush=True)
        
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
        
        print(f"❌ Memory search node failed: {str(e)}", flush=True)
        return {
            "last_ai_message": "",
            "search_tool_calls": []
        }


async def tool_search_node(state: FastState) -> Dict[str, Any]:
    """第一个工具节点：执行搜索相关工具"""
    print("🛠️ Search tool node executing...", flush=True)
    
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
        print(f"❌ Search tool node failed: {str(e)}", flush=True)
        return {"search_results": []}


async def llm_edit_node(state: FastState) -> Dict[str, Any]:
    """第二个LLM节点：决定如何编辑情景文件并输出工具调用"""
    print("✏️ Scenario updater node executing...", flush=True)
    
    import time
    start_time = time.time()
    
    # 准备输入数据用于日志
    current_scenario = state.get("current_scenario", "")
    last_ai_message = state.get("last_ai_message", "")
    search_results = state.get("search_results", [])
    
    inputs = {
        "current_scenario_length": len(current_scenario),
        "last_ai_message_length": len(last_ai_message),
        "search_results_count": len(search_results),
        "search_results_total_length": sum(len(r) for r in search_results),
        "current_scenario": current_scenario if current_scenario else "[Empty]",
        "last_ai_message": last_ai_message if last_ai_message else "[Empty]",
        "search_results": search_results  # 完整的搜索结果
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
        
        # 直接使用已定义的工具
        edit_tools = [create_row, delete_row, update_cell]
        model_with_tools = model.bind_tools(edit_tools)
        
        # 构建提示
        search_results_text = "\n".join(search_results) if search_results else "No search results"
        
        user_input = EDIT_USER_TEMPLATE.format(
            current_scenario=current_scenario,
            last_ai_message=last_ai_message,
            search_results=search_results_text
        )
        
        # 简洁的输入信息
        print(f"  Search results: {len(search_results)}, Total search text length: {sum(len(r) for r in search_results)}", flush=True)
        
        # 动态填充系统提示词中的schema
        dynamic_system_prompt = EDIT_LLM_PROMPT.format(
            schema_text=scenario_manager.get_table_schema_text()
        )
        
        # 调用LLM
        response = await model_with_tools.ainvoke([
            {"role": "system", "content": dynamic_system_prompt},
            {"role": "user", "content": user_input}
        ])
        
        # 提取工具调用
        tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else []
        print(f"  Planned {len(tool_calls)} table operations: {[tc.get('name') for tc in tool_calls]}", flush=True)
        
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
        
        print(f"❌ Scenario updater node failed: {str(e)}", flush=True)
        return {"edit_tool_calls": []}


async def tool_edit_node(state: FastState) -> Dict[str, Any]:
    """第二个工具节点：执行表格编辑操作"""
    print("📝 Table edit tool node executing...", flush=True)
    
    try:
        tool_calls = state.get("edit_tool_calls", [])
        
        # 执行工具调用
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            args = tool_call.get("args", {})
            
            try:
                if tool_name == "create_row":
                    result = create_row.invoke({
                        "table_name": args.get("table_name", ""),
                        "row_data": args.get("row_data", {})
                    })
                    print(f"  ✓ Created row in {args.get('table_name', 'unknown table')}", flush=True)
                
                elif tool_name == "delete_row":
                    result = delete_row.invoke({
                        "table_name": args.get("table_name", ""),
                        "row_id": args.get("row_id", "")
                    })
                    print(f"  ✓ Deleted row {args.get('row_id', '')} from {args.get('table_name', 'unknown table')}", flush=True)
                
                elif tool_name == "update_cell":
                    result = update_cell.invoke({
                        "table_name": args.get("table_name", ""),
                        "row_id": args.get("row_id", ""),
                        "column_name": args.get("column_name", ""),
                        "new_value": args.get("new_value", "")
                    })
                    print(f"  ✓ Updated {args.get('column_name', '')} in {args.get('table_name', 'unknown table')}", flush=True)
                    
            except Exception as e:
                print(f"  ❌ Tool execution failed {tool_name}: {str(e)}", flush=True)
        
        return {}  # 不需要返回final_scenario，注入时会重新读取
        
    except Exception as e:
        print(f"❌ Table edit tool node failed: {str(e)}", flush=True)
        return {}


async def init_scenario_node(state: FastState) -> Dict[str, Any]:
    """初始化节点：读取表格内容"""
    print("🚀 Scenario table initialization...", flush=True)
    
    try:
        # 直接从scenario_manager读取所有表格内容
        current_scenario = scenario_manager.get_all_pretty_tables(description=True, operation_guide=True)
        
        print(f"  ✓ Loaded scenario tables, total length: {len(current_scenario)}", flush=True)
        return {"current_scenario": current_scenario}
        
    except Exception as e:
        print(f"  ❌ Scenario table initialization failed: {str(e)}", flush=True)
        return {"current_scenario": "Scenario tables not initialized or empty."}


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
    print("🧪 Fast scenario workflow test starting...", flush=True)
    
    workflow = create_fast_scenario_workflow()
    
    test_input = {
        "current_scenario": "这是一个魔法学院的场景",
        "messages": [
            {"role": "user", "content": "教我一些魔法咒语"},
        ]
    }
    
    try:
        result = await workflow.ainvoke(test_input)
        print(f"✅ Fast workflow test completed successfully", flush=True)
        
    except Exception as e:
        print(f"❌ Fast workflow test failed: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_fast_workflow())