"""
基于 ReAct 架构的快速情景管理工作流
完全脱离 LangGraph 框架，使用两个 ReActAgent 实现记忆闪回和情景更新
"""

import asyncio
import sys
import os
from typing import Dict, Any, List, AsyncGenerator
from openai import AsyncOpenAI

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.manager import settings
from src.workflow.graph.reAct import ReActAgent
from src.prompts.fast_memory_search_prompts import SEARCH_LLM_PROMPT, SEARCH_USER_TEMPLATE
from src.prompts.fast_scenario_edit_prompts import EDIT_LLM_PROMPT, EDIT_USER_TEMPLATE
from src.workflow.tools.re_search_tool import create_re_search_tool, messages_to_txt
from src.workflow.tools.simple_thinking import thinking_tool
from src.workflow.tools.scenario_table_tools import (
    scenario_manager, 
    table_tools
)
from src.workflow.tools.wikipedia_search_tool import create_wikipedia_search_tool
from utils.external_knowledge_manager import external_knowledge_manager


class FastReActWorkflow:
    """基于 ReAct 架构的快速情景管理工作流"""
    
    def __init__(self):
        """初始化工作流"""
        # scenario_manager 现在会自动初始化，无需手动调用
        
        # 初始化OpenAI客户端
        agent_config = settings.agent
        self.client = AsyncOpenAI(
            api_key=agent_config.api_key,
            base_url=agent_config.base_url
        )
        
    
    def _build_search_tools(self, messages: List[Dict[str, Any]]):
        """构建搜索工具列表"""
        tools = []
        
        # 添加思考工具
        tools.append(thinking_tool)
        
        # 创建搜索文本
        search_text = messages_to_txt(messages)
        
        # 从管理器获取已缓存的外部知识库内容
        external_knowledge = external_knowledge_manager.get_knowledge_content()
        if external_knowledge:
            # 将外部知识库内容添加到搜索文本前面
            search_text = f"=== 外部知识库 ===\n{external_knowledge}\n\n=== 对话历史 ===\n{search_text}"
            print(f"\\ 使用已缓存的外部知识库: {external_knowledge_manager.get_knowledge_path()}", flush=True)
        
        # 添加记忆搜索工具
        memory_search_tool = create_re_search_tool(search_text)
        tools.append(memory_search_tool)
        
        # 根据配置决定是否添加Wikipedia工具
        if settings.agent.enable_wiki_search:
            tools.append(create_wikipedia_search_tool())
        
        return tools
    
    def _build_edit_tools(self):
        """构建编辑工具列表"""
        # 从 table_tools 中筛选需要的工具
        edit_tool_names = ['create_row', 'update_cell', 'delete_row']
        return [
            tool for tool in table_tools 
            if tool['function'].__name__ in edit_tool_names
        ]
    
    def _extract_latest_ai_message(self, messages: List[Dict[str, Any]], offset: int = 1) -> str:
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
    

    async def run(self, state: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """运行快速 ReAct 工作流
        
        Args:
            state: 工作流状态，包含messages、session_timestamp等信息
            
        Yields:
            str: 流式输出的处理结果
        """
        try:
            print("🤖 Fast ReAct Scenario Workflow starting...", flush=True)
            
            # 获取输入数据
            messages = state.get("messages", [])
            current_scenario = state.get("current_scenario", "")
            session_timestamp = state.get("session_timestamp")
            
            # 如果没有提供session_timestamp，生成一个
            if not session_timestamp:
                from datetime import datetime
                session_timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            
            # 如果没有current_scenario，从scenario_manager读取
            if not current_scenario:
                current_scenario = scenario_manager.get_all_pretty_tables(
                    description=True, 
                    operation_guide=True
                )
                print(f"\\ 加载情景表格，总长度: {len(current_scenario)}", flush=True)
            
            # 如果配置为-1，自动查找第一个内容长度>100的AI消息索引
            ai_msg_index = settings.langgraph.last_ai_messages_index
            if ai_msg_index == -1:
                from utils.messages_process import auto_find_ai_message_index
                ai_msg_index = auto_find_ai_message_index(messages)
            
            # 提取最新AI消息
            last_ai_message = self._extract_latest_ai_message(messages, ai_msg_index)
            
            # 获取配置
            agent_config = settings.agent
            log_config = settings.log
            
            # 创建会话日志目录
            session_log_path = log_config.get_session_log_path(session_timestamp)
            
            print(f"\\ 接收消息数: {len(messages)}, AI消息长度: {len(last_ai_message)}", flush=True)
            print(f"\\ 会话日志目录: {session_log_path}", flush=True)
            
            # === 阶段1：搜索记忆 ReAct Agent ===
            print("✅ Phase 1: Memory Search Agent...", flush=True)
            
            # 构建搜索工具列表
            search_tools = self._build_search_tools(messages)
            
            # 构建搜索用户输入
            search_user_input = SEARCH_USER_TEMPLATE.format(
                current_scenario=current_scenario,
                last_ai_message=last_ai_message
            )
            
            # 创建搜索 ReAct 智能体（限制1次迭代）
            search_agent = ReActAgent(
                model=self.client,
                max_iterations=1,  # 强制限制为1次迭代
                system_prompt=SEARCH_LLM_PROMPT,
                user_input=search_user_input,
                tools_with_schemas=search_tools,
                model_name=agent_config.model,
                temperature=agent_config.temperature,
                max_tokens=agent_config.max_tokens if hasattr(agent_config, 'max_tokens') else None,
                history_type=log_config.history_format if log_config.enable_agent_history else "none",
                history_path=session_log_path
            )
            
            # 根据配置选择流式方法执行搜索智能体，收集LLM输出（用于展示）
            search_model_output = ""
            if agent_config.stream_mode:
                # 真流式：实时字符输出
                async for chunk in search_agent.astream():
                    search_model_output += chunk
                    yield chunk
            else:
                # 伪流式：每次迭代输出完整响应
                async for chunk in search_agent.ainvoke():
                    search_model_output += chunk
                    yield chunk

            # 修正：使用工具执行的真实输出作为搜索结果（而非模型文本）
            search_tool_output = search_agent.get_tool_outputs_text()
            
            
            # === 阶段2：编辑情景 ReAct Agent ===
            print("✅ Phase 2: Scenario Edit Agent...", flush=True)
            
            # 构建编辑工具列表
            edit_tools = self._build_edit_tools()
            
            # 构建编辑用户输入（包含第一阶段的工具搜索结果）
            edit_user_input = EDIT_USER_TEMPLATE.format(
                current_scenario=current_scenario,
                last_ai_message=last_ai_message,
                # 传入第一阶段工具的输出结果（修正前为模型输出，现已修正）
                search_results=search_tool_output
            )
            
            # 动态填充编辑系统提示词中的schema
            dynamic_edit_system_prompt = EDIT_LLM_PROMPT.format(
                schema_text=scenario_manager.get_table_schema_text()
            )
            
            # 创建编辑 ReAct 智能体（限制1次迭代）
            edit_agent = ReActAgent(
                model=self.client,
                max_iterations=1,  # 强制限制为1次迭代
                system_prompt=dynamic_edit_system_prompt,
                user_input=edit_user_input,
                tools_with_schemas=edit_tools,
                model_name=agent_config.model,
                temperature=agent_config.temperature,
                max_tokens=agent_config.max_tokens if hasattr(agent_config, 'max_tokens') else None,
                history_type=log_config.history_format if log_config.enable_agent_history else "none",
                history_path=session_log_path
            )
            
            # 根据配置选择流式方法执行编辑智能体
            if agent_config.stream_mode:
                # 真流式：实时字符输出
                async for chunk in edit_agent.astream():
                    yield chunk
            else:
                # 伪流式：每次迭代输出完整响应
                async for chunk in edit_agent.ainvoke():
                    yield chunk
                
            print("\n✅ Fast ReAct Scenario Workflow completed!", flush=True)
            
        except Exception as e:
            error_msg = f"❌ Fast ReAct Workflow 执行失败: {str(e)}"
            print(error_msg, flush=True)
            yield error_msg


# 创建工作流实例的工厂函数
def create_fast_scenario_workflow() -> FastReActWorkflow:
    """创建快速 ReAct 情景管理工作流实例"""
    return FastReActWorkflow()


# 测试函数
async def test_fast_react_workflow():
    """测试快速 ReAct 工作流"""
    try:
        print("=== 测试 Fast ReAct 情景管理工作流 ===")
        
        # 创建工作流
        workflow = create_fast_scenario_workflow()
        
        # 模拟输入状态
        test_state = {
            "messages": [
                {"role": "user", "content": "你好，我是新来的魔法学院学生"},
                {"role": "assistant", "content": "欢迎来到霍格沃茨！我是你的导师教授。让我为你介绍一下这里的环境和规则。"}
            ]
        }
        
        print("🏃 开始执行工作流...")
        
        # 流式执行
        async for chunk in workflow.run(test_state):
            print(chunk, end='', flush=True)
            
        print("\n\n🎉 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_fast_react_workflow())