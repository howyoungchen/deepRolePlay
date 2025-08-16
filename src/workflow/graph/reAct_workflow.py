"""
基于reAct架构的情景管理工作流
完全脱离LangGraph框架，使用reAct智能体实现记忆闪回和情景更新
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
from src.prompts.reAct_scenario_prompts import REACT_SYSTEM_PROMPT, REACT_USER_TEMPLATE
from src.workflow.tools.re_search_tool import re_search
from src.workflow.tools.scenario_table_tools import scenario_manager, create_row, delete_row, update_cell
from src.workflow.tools.sequential_thinking import sequential_thinking
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.runnables import RunnableConfig


class ReActWorkflow:
    """基于reAct架构的情景管理工作流"""
    
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
    
    def _wrap_sequential_thinking(self):
        """包装顺序思考工具"""
        def sequential_thinking_tool(
            thought: str,
            next_thought_needed: bool,
            thought_number: int,
            total_thoughts: int,
            is_revision: bool = False,
            revises_thought: int = None,
            branch_from_thought: int = None,
            branch_id: str = None,
            needs_more_thoughts: bool = False
        ) -> str:
            """用于动态和反思性问题解决的详细思考工具
            
            Args:
                thought: 当前的思考步骤
                next_thought_needed: 是否需要另一个思考步骤
                thought_number: 当前思考编号
                total_thoughts: 预估总思考数
                is_revision: 是否修订之前的思考
                revises_thought: 正在重新考虑哪个思考
                branch_from_thought: 分支点思考编号
                branch_id: 分支标识符
                needs_more_thoughts: 是否需要更多思考
                
            Returns:
                JSON格式的处理结果
            """
            try:
                result = sequential_thinking.invoke({
                    "thought": thought,
                    "next_thought_needed": next_thought_needed,
                    "thought_number": thought_number,
                    "total_thoughts": total_thoughts,
                    "is_revision": is_revision,
                    "revises_thought": revises_thought,
                    "branch_from_thought": branch_from_thought,
                    "branch_id": branch_id,
                    "needs_more_thoughts": needs_more_thoughts
                })
                return result
            except Exception as e:
                return f"❌ 思考工具失败: {str(e)}"
        
        sequential_thinking_tool.__name__ = "sequential_thinking"
        return sequential_thinking_tool
    
    def _build_tools(self, messages: List[Dict[str, Any]]):
        """构建工具列表"""
        return [
            self._wrap_sequential_thinking(),
            self._wrap_search_memory(messages),
            self._wrap_search_wikipedia(),
            self._wrap_create_row(),
            self._wrap_update_cell(),
            self._wrap_delete_row()
        ]
    
    async def run(self, state: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """运行reAct工作流
        
        Args:
            state: 工作流状态，包含messages、session_timestamp等信息
            
        Yields:
            str: 流式输出的处理结果
        """
        try:
            print("🚀 ReAct Scenario Workflow starting...", flush=True)
            
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
            
            # 如果配置为-1，自动查找第一个内容长度>配置阈值的AI消息索引
            ai_msg_index = settings.langgraph.last_ai_messages_index
            if ai_msg_index == -1:
                from utils.messages_process import auto_find_ai_message_index
                ai_msg_index = auto_find_ai_message_index(messages)
            
            # 提取最新AI消息
            last_ai_message = self._extract_latest_ai_message(messages, ai_msg_index)
            
            # 构建工具列表
            tools = self._build_tools(messages)
            
            # 构建用户输入
            user_input = REACT_USER_TEMPLATE.format(
                current_scenario=current_scenario,
                last_ai_message=last_ai_message
            )
            
            # 获取配置
            agent_config = settings.agent
            log_config = settings.log
            
            # 创建会话日志目录
            session_log_path = log_config.get_session_log_path(session_timestamp)
            
            print(f"  📝 消息数量: {len(messages)}, AI消息长度: {len(last_ai_message)}", flush=True)
            print(f"  🔧 工具数量: {len(tools)}, 最大迭代: {agent_config.max_iterations}", flush=True)
            print(f"  📁 会话日志目录: {session_log_path}", flush=True)
            
            # 动态填充系统提示词中的schema
            dynamic_system_prompt = REACT_SYSTEM_PROMPT.format(
                schema_text=scenario_manager.get_table_schema_text()
            )
            
            # 创建ReAct智能体（使用动态系统提示词）
            agent = ReActAgent(
                model=self.client,
                max_iterations=agent_config.max_iterations,
                system_prompt=dynamic_system_prompt,
                user_input=user_input,
                tools_list=tools,
                model_name=agent_config.model,
                temperature=agent_config.temperature,
                max_tokens=agent_config.max_tokens if hasattr(agent_config, 'max_tokens') else None,
                history_type=log_config.history_format if log_config.enable_agent_history else "none",
                history_path=session_log_path
            )
            
            # 根据配置选择流式方法执行智能体
            print("🤖 ReAct Agent executing...", flush=True)
            if agent_config.stream_mode:
                # 真流式：实时字符输出
                async for chunk in agent.astream():
                    yield chunk
            else:
                # 伪流式：每次迭代输出完整响应
                async for chunk in agent.ainvoke():
                    yield chunk
                
            print("\n✅ ReAct Scenario Workflow completed!", flush=True)
            
        except Exception as e:
            error_msg = f"❌ ReAct Workflow 执行失败: {str(e)}"
            print(error_msg, flush=True)
            yield error_msg
    
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


# 创建工作流实例的工厂函数
def create_react_scenario_workflow() -> ReActWorkflow:
    """创建ReAct情景管理工作流实例"""
    return ReActWorkflow()


# 测试函数
async def test_react_workflow():
    """测试ReAct工作流"""
    try:
        print("=== 测试 ReAct 情景管理工作流 ===")
        
        # 创建工作流
        workflow = create_react_scenario_workflow()
        
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
    asyncio.run(test_react_workflow())