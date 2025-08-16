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
from src.workflow.tools.re_search_tool import re_search
from src.workflow.tools.scenario_table_tools import scenario_manager, create_row, delete_row, update_cell
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.runnables import RunnableConfig


class FastReActWorkflow:
    """基于 ReAct 架构的快速情景管理工作流"""
    
    def __init__(self):
        """初始化工作流"""
        # 初始化scenario_manager
        scenario_manager.init(settings.scenario.file_path)
        
        # 初始化OpenAI客户端
        agent_config = settings.agent
        self.client = AsyncOpenAI(
            api_key=agent_config.api_key,
            base_url=agent_config.base_url
        )
        
        # 创建Wikipedia工具
        self.wikipedia_tool = self._create_wikipedia_tool()
        
    def _create_wikipedia_tool(self):
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
    
    def _wrap_search_memory(self, messages: List[Dict[str, Any]]):
        """包装内部记忆搜索工具"""
        def search_memory(pattern: str) -> str:
            """搜索内部记忆
            
            Args:
                pattern: 正则表达式搜索模式，建议使用多实体联合搜索
                
            Returns:
                JSON格式的搜索结果
            """
            try:
                config = RunnableConfig(
                    configurable={
                        "conversation_history": messages
                    }
                )
                result = re_search.invoke(pattern, config)
                return result
            except Exception as e:
                return f"内部记忆搜索失败: {str(e)}"
        
        search_memory.__name__ = "search_memory"
        return search_memory
    
    def _wrap_search_wikipedia(self):
        """包装Wikipedia搜索工具"""
        def search_wikipedia(query: str) -> str:
            """搜索Wikipedia外部知识
            
            Args:
                query: 搜索查询关键词
                
            Returns:
                Wikipedia搜索结果
            """
            try:
                result = self.wikipedia_tool.invoke(query)
                return f"[外部知识] {result}"
            except Exception as e:
                return f"Wikipedia搜索失败: {str(e)}"
        
        search_wikipedia.__name__ = "search_wikipedia"
        return search_wikipedia
    
    def _wrap_create_row(self):
        """包装创建表格行工具"""
        def create_table_row(table_name: str, row_data: dict) -> str:
            """在指定表格中创建新行
            
            Args:
                table_name: 表格名称（必须使用中文）
                row_data: 行数据字典，键必须匹配预定义字段
                
            Returns:
                创建结果信息
            """
            try:
                result = create_row.invoke({
                    "table_name": table_name,
                    "row_data": row_data
                })
                return f"✓ 创建行成功: {table_name} - {result}"
            except Exception as e:
                return f"❌ 创建行失败: {table_name} - {str(e)}"
        
        create_table_row.__name__ = "create_table_row"
        return create_table_row
    
    def _wrap_update_cell(self):
        """包装更新表格单元格工具"""
        def update_table_cell(table_name: str, row_id: str, column_name: str, new_value: str) -> str:
            """更新指定表格的单元格值
            
            Args:
                table_name: 表格名称
                row_id: 行ID
                column_name: 列名
                new_value: 新值
                
            Returns:
                更新结果信息
            """
            try:
                result = update_cell.invoke({
                    "table_name": table_name,
                    "row_id": row_id,
                    "column_name": column_name,
                    "new_value": new_value
                })
                return f"✓ 更新单元格成功: {table_name}[{row_id}].{column_name} = {new_value}"
            except Exception as e:
                return f"❌ 更新单元格失败: {table_name}[{row_id}].{column_name} - {str(e)}"
        
        update_table_cell.__name__ = "update_table_cell"
        return update_table_cell
    
    def _wrap_delete_row(self):
        """包装删除表格行工具"""
        def delete_table_row(table_name: str, row_id: str) -> str:
            """删除指定表格的行
            
            Args:
                table_name: 表格名称
                row_id: 行ID
                
            Returns:
                删除结果信息
            """
            try:
                result = delete_row.invoke({
                    "table_name": table_name,
                    "row_id": row_id
                })
                return f"✓ 删除行成功: {table_name}[{row_id}] - {result}"
            except Exception as e:
                return f"❌ 删除行失败: {table_name}[{row_id}] - {str(e)}"
        
        delete_table_row.__name__ = "delete_table_row"
        return delete_table_row
    
    def _build_search_tools(self, messages: List[Dict[str, Any]]):
        """构建搜索工具列表"""
        return [
            self._wrap_search_memory(messages),
            self._wrap_search_wikipedia(),
        ]
    
    def _build_edit_tools(self):
        """构建编辑工具列表"""
        return [
            self._wrap_create_row(),
            self._wrap_update_cell(),
            self._wrap_delete_row()
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
            print("🚀 Fast ReAct Scenario Workflow starting...", flush=True)
            
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
                print(f"  ✓ 加载情景表格，总长度: {len(current_scenario)}", flush=True)
            
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
            
            print(f"  📝 消息数量: {len(messages)}, AI消息长度: {len(last_ai_message)}", flush=True)
            print(f"  📁 会话日志目录: {session_log_path}", flush=True)
            
            # === 阶段1：搜索记忆 ReAct Agent ===
            print("🔍 Phase 1: Memory Search Agent...", flush=True)
            
            # 构建搜索工具列表
            search_tools = self._build_search_tools(messages)
            
            # 构建搜索用户输入
            search_user_input = SEARCH_USER_TEMPLATE.format(
                current_scenario=current_scenario,
                last_ai_message=last_ai_message,
                tools_description_user=""  # ReAct 会自动生成工具描述
            )
            
            # 创建搜索 ReAct 智能体（限制1次迭代）
            search_agent = ReActAgent(
                model=self.client,
                max_iterations=1,  # 强制限制为1次迭代
                system_prompt=SEARCH_LLM_PROMPT.replace("{tools_description_system}", ""),
                user_input=search_user_input,
                tools_list=search_tools,
                model_name=agent_config.model,
                temperature=agent_config.temperature,
                max_tokens=agent_config.max_tokens if hasattr(agent_config, 'max_tokens') else None,
                history_type=log_config.history_format if log_config.enable_agent_history else "none",
                history_path=session_log_path
            )
            
            # 根据配置选择流式方法执行搜索智能体，收集搜索结果
            search_output = ""
            if agent_config.stream_mode:
                # 真流式：实时字符输出
                async for chunk in search_agent.astream():
                    search_output += chunk
                    yield chunk
            else:
                # 伪流式：每次迭代输出完整响应
                async for chunk in search_agent.ainvoke():
                    search_output += chunk
                    yield chunk
            
            print("\n🔄 Phase 1 completed, transitioning to Phase 2...", flush=True)
            
            # === 阶段2：编辑情景 ReAct Agent ===
            print("✏️ Phase 2: Scenario Edit Agent...", flush=True)
            
            # 构建编辑工具列表
            edit_tools = self._build_edit_tools()
            
            # 构建编辑用户输入（包含搜索结果）
            edit_user_input = EDIT_USER_TEMPLATE.format(
                tools_description_user="",  # ReAct 会自动生成工具描述
                current_scenario=current_scenario,
                last_ai_message=last_ai_message,
                search_results=search_output  # 传入第一阶段的搜索结果
            )
            
            # 动态填充编辑系统提示词中的schema
            dynamic_edit_system_prompt = EDIT_LLM_PROMPT.format(
                tools_description_system="",
                schema_text=scenario_manager.get_table_schema_text()
            )
            
            # 创建编辑 ReAct 智能体（限制1次迭代）
            edit_agent = ReActAgent(
                model=self.client,
                max_iterations=1,  # 强制限制为1次迭代
                system_prompt=dynamic_edit_system_prompt,
                user_input=edit_user_input,
                tools_list=edit_tools,
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