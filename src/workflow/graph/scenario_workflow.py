"""
情景更新工作流 - 使用LangGraph父图整合记忆闪回和情景更新
"""
import asyncio
import sys
import os
from typing import Dict, Any, List
from typing_extensions import TypedDict

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from config.manager import settings
from utils.logger import request_logger
from src.prompts.memory_flashback_prompts import MEMORY_FLASHBACK_PROMPT, MEMORY_FLASHBACK_USER_TEMPLATE
from src.prompts.scenario_updater_prompts import SCENARIO_UPDATER_PROMPT, SCENARIO_UPDATER_USER_TEMPLATE
from src.workflow.tools.sequential_thinking import sequential_thinking
from src.workflow.tools.re_search_tool import re_search
from src.workflow.tools.write_tool import write_file
from src.workflow.tools.read_tool import read_target_file
from src.workflow.tools.edit_tool import edit_file




class ParentState(TypedDict):
    """父图状态定义"""
    # 输入参数
    current_scenario: str       # 当前情景文件内容
    messages: List[Dict[str, Any]]  # 完整的消息列表
    
    # 中间状态
    memory_flashback: str      # 记忆闪回结果
    last_ai_message: str       # 从messages中提取的最新AI消息
    
    # 输出结果
    final_scenario: str        # 最终更新的情景


def create_model():
    """创建ChatOpenAI模型实例"""
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
    """从消息列表中提取倒数第offset个AI消息"""
    ai_messages = []
    for msg in messages:
        if msg.get("role") == "assistant":
            ai_messages.append(msg.get("content", ""))
    
    if len(ai_messages) >= offset:
        return ai_messages[-offset]  # 返回倒数第offset个AI消息
    elif ai_messages:
        return ai_messages[-1]  # 如果不够offset个，返回最后一个
    else:
        return ""  # 没有AI消息





def extract_memory_flashback_result(response: Dict[str, Any]) -> str:
    """从agent响应中提取记忆闪回结果"""
    try:
        messages = response.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content') and last_message.content:
                content = last_message.content.strip()
                return f"<记忆闪回>\n{content}\n</记忆闪回>"
        
        return "<记忆闪回>\n暂无相关历史记忆。\n</记忆闪回>"
        
    except Exception as e:
        request_logger.log_error(f"提取记忆闪回结果失败: {str(e)}")
        return "<记忆闪回>\n记忆搜索出现错误，无法获取历史信息。\n</记忆闪回>"






async def memory_flashback_node(state: ParentState) -> Dict[str, Any]:
    """记忆闪回节点函数"""
    try:
        # ================ 提取和准备数据 ================
        messages = state.get("messages", [])
        langgraph_config = settings.langgraph
        offset = langgraph_config.history_ai_message_offset
        last_ai_message = extract_latest_ai_message(messages, offset)
        
        await request_logger.log_info(
            f"开始记忆闪回，提取的AI消息长度: {len(last_ai_message)}"
        )
        
        # ================ 创建模型和代理 ================
        model = create_model()
        agent_config = settings.agent
        
        agent = create_react_agent(
            model=model,
            tools=[sequential_thinking, re_search],
            prompt=MEMORY_FLASHBACK_PROMPT,
            debug=agent_config.debug,
        )
        
        # ================ 设置历史和构建提示 ================
        user_prompt = MEMORY_FLASHBACK_USER_TEMPLATE.format(
            current_scenario=state["current_scenario"] if state["current_scenario"] else "[暂无情景信息]",
            last_ai_message=last_ai_message if last_ai_message else "[暂无最新消息]"
        )
        
        # ================ 调用代理执行记忆闪回 ================
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_prompt}]},
            config={"configurable": {"conversation_history": messages}}
        )
        
        # ================ 提取和处理结果 ================
        memory_result = extract_memory_flashback_result(response)
        
        if memory_result:
            await request_logger.log_info(f"记忆闪回成功，结果长度: {len(memory_result)}")
        else:
            await request_logger.log_warning("记忆闪回未产生有效结果")
        
        return {
            "memory_flashback": memory_result,
            "last_ai_message": last_ai_message
        }
        
    except Exception as e:
        await request_logger.log_error(f"记忆闪回节点执行失败: {str(e)}")
        return {
            "memory_flashback": "=== 记忆闪回 ===\n\n记忆搜索出现错误，无法获取历史信息。",
            "last_ai_message": ""
        }


async def scenario_updater_node(state: ParentState) -> Dict[str, Any]:
    """情景更新节点函数"""
    try:
        # ================ 提取和准备数据 ================
        last_ai_message = state.get("last_ai_message", "")
        memory_flashback = state.get("memory_flashback", "")
        
        await request_logger.log_info(
            f"开始情景更新，AI消息长度: {len(last_ai_message)}, 记忆闪回长度: {len(memory_flashback)}"
        )
        
        # ================ 创建模型和代理 ================
        model = create_model()
        agent_config = settings.agent
        
        agent = create_react_agent(
            model=model,
            tools=[write_file, read_target_file, edit_file, sequential_thinking],
            prompt=SCENARIO_UPDATER_PROMPT,
            debug=agent_config.debug,
        )
        
        # ================ 构建提示 ================
        from utils.scenario_utils import get_scenario_file_path
        scenario_file_path = get_scenario_file_path()
        
        user_prompt = SCENARIO_UPDATER_USER_TEMPLATE.format(
            last_ai_message=last_ai_message if last_ai_message else "[暂无最新消息]",
            memory_flashback=memory_flashback if memory_flashback else "[暂无记忆闪回信息]",
            scenario_file_path=scenario_file_path
        )
        
        # ================ 调用代理执行情景更新 ================
        await agent.ainvoke({
            "messages": [{"role": "user", "content": user_prompt}]
        })
        
        # ================ 读取和处理结果 ================
        from utils.scenario_utils import read_scenario
        # 等待一小段时间确保文件写入完成
        await asyncio.sleep(0.5)
        scenario_result = await read_scenario()
        
        if scenario_result and scenario_result.strip():
            await request_logger.log_info(f"情景更新成功，结果长度: {len(scenario_result)}")
        else:
            await request_logger.log_warning("情景更新未产生有效结果")
            scenario_result = "情景更新失败"
        
        return {"final_scenario": scenario_result}
        
    except Exception as e:
        await request_logger.log_error(f"情景更新节点执行失败: {str(e)}")
        return {"final_scenario": "情景更新失败"}


def create_scenario_workflow():
    """创建情景更新工作流"""
    builder = StateGraph(ParentState)
    
    # 添加节点
    builder.add_node("memory_flashback", memory_flashback_node)
    builder.add_node("scenario_updater", scenario_updater_node)
    
    # 添加边
    builder.add_edge(START, "memory_flashback")
    builder.add_edge("memory_flashback", "scenario_updater")
    builder.add_edge("scenario_updater", END)
    
    return builder.compile()


def extract_latest_messages(messages: List[Dict[str, Any]]) -> str:
    """从消息列表中提取最新的AI消息"""
    last_ai_message = ""
    
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "assistant" and not last_ai_message:
            last_ai_message = msg.get("content", "")
            break
    
    return last_ai_message


# 流式事件测试函数
async def test_workflow_streaming_events():
    """测试工作流流式事件"""
    from utils.pretty_print import pretty_print_stream_events
    
    print("开始测试工作流流式事件...")
    
    # 创建工作流
    workflow = create_scenario_workflow()
    
    # 模拟输入
    test_input = {
        "current_scenario": "这是一个魔法学院的场景",
        "messages": [
            {"role": "user", "content": "教我一些魔法咒语"},
            {"role": "assistant", "content": "让我来教你几个基础的魔法咒语。首先是荧光闪烁咒(Lumos)，这是一个照明咒语..."}
        ]
    }
    
    try:
        # 使用 astream_events 获取流式事件并美化输出
        async for event in workflow.astream_events(test_input, version="v2"):
            pretty_print_stream_events(event)
                        
    except Exception as e:
        print(f"❌ 流式事件测试失败: {str(e)}")
        import traceback
        traceback.print_exc()






if __name__ == "__main__":
    asyncio.run(test_workflow_streaming_events())