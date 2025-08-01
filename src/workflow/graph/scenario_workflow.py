"""
情景更新工作流 - 使用LangGraph父图整合记忆闪回和情景更新
"""
import os
import asyncio
from typing import Dict, Any, List
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from config.manager import settings
from utils.logger import request_logger
from utils.message import format_history_for_analysis
from utils.history_manager import set_conversation_history
from src.prompts.memory_flashback import MEMORY_FLASHBACK_PROMPT
from src.prompts.scenario_updater import SCENARIO_UPDATER_PROMPT
from src.workflow.tools.sequential_thinking import sequential_thinking
from src.workflow.tools.re_search_tool import re_search
from src.workflow.tools.write_tool import write_file
from src.workflow.tools.read_tool import read_target_file
from src.workflow.tools.edit_tool import edit_file


class ParentState(TypedDict):
    """父图状态定义"""
    # 输入参数
    current_scenario: str       # 当前情景文件内容
    last_ai_message: str       # 上一条AI消息
    current_user_message: str  # 当前用户消息
    
    # 中间状态
    memory_flashback: str      # 记忆闪回结果
    
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


def build_history_from_state(state: ParentState) -> List[Dict[str, Any]]:
    """从状态构建对话历史"""
    history = []
    if state.get("last_ai_message"):
        history.append({"role": "assistant", "content": state["last_ai_message"]})
    if state.get("current_user_message"):
        history.append({"role": "user", "content": state["current_user_message"]})
    return history


def build_memory_flashback_prompt(current_scenario: str, history: List[Dict[str, Any]]) -> str:
    """构建记忆闪回的用户提示词"""
    history_text = format_history_for_analysis(history)
    
    return f"""当前情景：
{current_scenario if current_scenario else "[暂无情景信息]"}

最新对话：
{history_text}

任务要求：
1. 分析当前情景和最新对话，识别其中的关键实体
2. 基于当前情景判断哪些实体信息已经充分，无需进一步搜索
3. 对需要了解更多背景的实体进行记忆搜索
4. 整合搜索结果，形成结构化的记忆闪回输出
5. 重点关注实体间的关联关系和互动历史

请开始记忆闪回过程。"""


def extract_memory_flashback_result(response: Dict[str, Any]) -> str:
    """从agent响应中提取记忆闪回结果"""
    try:
        messages = response.get("messages", [])
        for message in reversed(messages):
            if hasattr(message, 'content') and message.content:
                content = message.content.strip()
                if "=== 记忆闪回 ===" in content:
                    return content
        
        # 如果没找到记忆闪回格式，返回默认内容
        return "=== 记忆闪回 ===\n\n暂无相关历史记忆。"
        
    except Exception as e:
        request_logger.log_error(f"提取记忆闪回结果失败: {str(e)}")
        return "=== 记忆闪回 ===\n\n记忆搜索出现错误，无法获取历史信息。"


def build_scenario_updater_prompt(history: List[Dict[str, Any]], memory_flashback: str) -> str:
    """构建情景更新的用户提示词"""
    from src.scenario.manager import scenario_manager
    
    history_text = format_history_for_analysis(history)
    scenario_file_path = os.path.abspath(scenario_manager.scenario_file_path)
    memory_section = f"\n\n记忆闪回信息：\n{memory_flashback}" if memory_flashback else ""
    
    return f"""请根据当前对话历史和记忆闪回信息，更新情景文件。

对话历史：
{history_text}{memory_section}

情景文件位置：{scenario_file_path}

任务要求：
1. 首先读取现有情景文件内容，了解当前情景状态
2. 根据情景文件状态选择操作方式：
   - 如果文件为空或不存在：使用write_file工具创建新的情景内容
   - 如果文件有内容：使用edit_file工具修改需要更新的具体部分
3. 分析当前对话历史和记忆闪回信息，更新以下信息：
   - 对话的主要角色和身份设定
   - 当前的情境和背景
   - 重要的情节发展
   - 需要记住的关键信息
   - 结合记忆闪回中的历史背景，确保情景连贯性
4. 完成更新后，读取情景文件并返回完整内容

注意：如果现有情景文件有内容，请保持其结构和有用信息，只修改需要更新的部分。
如果是空文件，请生成简洁明了的情景内容，文本长度控制在200-500字之间。
重要：充分利用记忆闪回信息，确保情景更新的准确性和连贯性。"""


async def read_generated_scenario_file() -> str:
    """读取生成的情景文件"""
    try:
        from src.scenario.manager import scenario_manager
        scenario_file_path = os.path.abspath(scenario_manager.scenario_file_path)
        
        # 等待一小段时间确保文件写入完成
        await asyncio.sleep(0.5)
        
        if os.path.exists(scenario_file_path):
            with open(scenario_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                return content
        
        return "情景更新失败"
        
    except Exception as e:
        await request_logger.log_error(f"读取生成的情景文件失败: {str(e)}")
        return "情景更新失败"


async def memory_flashback_node(state: ParentState) -> Dict[str, Any]:
    """记忆闪回节点函数"""
    try:
        # 创建模型和代理
        model = create_model()
        agent_config = settings.agent
        
        agent = create_react_agent(
            model=model,
            tools=[sequential_thinking, re_search],
            prompt=MEMORY_FLASHBACK_PROMPT,
            debug=agent_config.debug,
        )
        
        # 构建最新一轮对话history
        history = build_history_from_state(state)
        
        # 设置全局历史供re_search工具使用
        set_conversation_history(history)
        
        # 构建用户提示词
        user_prompt = build_memory_flashback_prompt(state["current_scenario"], history)
        
        await request_logger.log_info(f"开始记忆闪回，历史消息数量: {len(history)}")
        
        # 调用代理
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": user_prompt}]
        })
        
        # 提取记忆闪回结果
        memory_result = extract_memory_flashback_result(response)
        
        if memory_result:
            await request_logger.log_info(f"记忆闪回成功，结果长度: {len(memory_result)}")
        else:
            await request_logger.log_warning("记忆闪回未产生有效结果")
        
        return {"memory_flashback": memory_result}
        
    except Exception as e:
        await request_logger.log_error(f"记忆闪回节点执行失败: {str(e)}")
        return {"memory_flashback": "=== 记忆闪回 ===\n\n记忆搜索出现错误，无法获取历史信息。"}


async def scenario_updater_node(state: ParentState) -> Dict[str, Any]:
    """情景更新节点函数"""
    try:
        # 创建模型和代理
        model = create_model()
        agent_config = settings.agent
        
        agent = create_react_agent(
            model=model,
            tools=[write_file, read_target_file, edit_file, sequential_thinking],
            prompt=SCENARIO_UPDATER_PROMPT,
            debug=agent_config.debug,
        )
        
        # 构建最新一轮对话history（不包含完整messages，保持原有逻辑）
        history = build_history_from_state(state)
        
        # 构建用户提示词
        user_prompt = build_scenario_updater_prompt(history, state.get("memory_flashback", ""))
        
        await request_logger.log_info(f"开始情景更新，历史消息数量: {len(history)}")
        
        # 调用代理
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": user_prompt}]
        })
        
        # 从文件读取结果
        scenario_result = await read_generated_scenario_file()
        
        if scenario_result and scenario_result != "情景更新失败":
            await request_logger.log_info(f"情景更新成功，内容长度: {len(scenario_result)}")
        else:
            await request_logger.log_warning("情景更新未产生有效结果")
        
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


def extract_latest_messages(messages: List[Dict[str, Any]]) -> tuple[str, str]:
    """从消息列表中提取最新的AI和用户消息"""
    last_ai_message = ""
    current_user_message = ""
    
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "user" and not current_user_message:
            current_user_message = msg.get("content", "")
        elif msg.get("role") == "assistant" and not last_ai_message:
            last_ai_message = msg.get("content", "")
        
        # 如果都找到了就停止
        if current_user_message and last_ai_message:
            break
    
    return last_ai_message, current_user_message


# 测试用的异步函数
async def test_scenario_workflow():
    """测试情景更新工作流"""
    print("开始测试情景更新工作流...")
    
    # 创建工作流
    workflow = create_scenario_workflow()
    
    # 模拟输入
    test_input = {
        "current_scenario": "这是一个关于哈利波特的对话场景",
        "last_ai_message": "守护神咒语是一个强大的防御魔法...",
        "current_user_message": "告诉我关于守护神咒语的故事"
    }
    
    # 调用工作流
    result = await workflow.ainvoke(test_input)
    
    print(f"工作流执行完成:")
    print(f"记忆闪回结果: {result.get('memory_flashback', '')[:100]}...")
    print(f"最终情景结果: {result.get('final_scenario', '')[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_scenario_workflow())