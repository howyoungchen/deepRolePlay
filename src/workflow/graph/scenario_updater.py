"""
情景更新工作流
基于LangGraph的create_react_agent，用于分析对话历史并生成情景文件
"""
import os
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config.manager import settings
from utils.pretty_print import log_workflow_execution
from utils.message import format_history_for_analysis
from utils.logger import request_logger

# 导入工具
from src.workflow.tools.write_tool import write_file
from src.workflow.tools.read_tool import read_target_file
from src.workflow.tools.edit_tool import edit_file
from src.workflow.tools.sequential_thinking import sequential_thinking


class ScenarioUpdaterAgent:
    """基于LangGraph的情景更新代理"""
    
    def __init__(self):
        """初始化ScenarioUpdaterAgent"""
        # 使用agent配置
        agent_config = settings.agent
        
        # DeepSeek API配置
        self.model = ChatOpenAI(
            base_url=agent_config.base_url,
            model=agent_config.model,
            api_key=agent_config.api_key,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            top_p=agent_config.top_p
        )
        
        # 系统提示词
        self.system_prompt = """
你是一个专业的情景分析和总结助手。你的任务是分析对话历史，生成简洁准确的情景描述文件。

工作原则：
1. 仔细分析用户提供的对话历史
2. 提取关键的角色、情境、情节发展信息
3. 生成200-500字的情景摘要
4. 摘要应该为下次对话提供有用的背景信息
5. 直接输出情景内容，不需要额外的格式说明
6. 使用中文输出
7. 将生成的情景内容保存到指定文件

可用工具：
- write_file: 将生成的情景内容写入文件
- read_target_file: 读取文件内容（如需参考现有情景文件）
- edit_file: 编辑文件的特定部分
- sequential_thinking: 进行结构化的深度思考分析（复杂情况时使用）

重要操作规则：
- 每次使用edit_file工具前，必须先使用read_target_file工具读取文件当前内容
- 这样可以确保编辑操作基于最新的文件状态，避免内容冲突

请根据对话历史分析并生成情景文件。如果对话历史较复杂，可以先使用sequential_thinking进行深度分析。
"""
        
        # 创建智能代理，使用所有可用工具
        self.agent = create_react_agent(
            model=self.model,
            tools=[write_file, read_target_file, edit_file, sequential_thinking],
            prompt=self.system_prompt,
            debug=agent_config.debug,
        )
        
        print("ScenarioUpdaterAgent 初始化完成!")
    
    def build_user_prompt(self, history: List[Dict[str, Any]]) -> str:
        """
        构建完整的用户提示词
        
        Args:
            history: 对话历史
            
        Returns:
            完整的用户提示词
        """
        # 获取情景文件的绝对路径
        from src.scenario.manager import scenario_manager
        scenario_file_path = os.path.abspath(scenario_manager.scenario_file_path)
        
        # 格式化对话历史
        history_text = format_history_for_analysis(history)
        
        # 构造完整的用户提示词
        user_prompt = f"""请根据当前对话历史，更新情景文件。

对话历史：
{history_text}

情景文件位置：{scenario_file_path}

任务要求：
1. 首先读取现有情景文件内容，了解当前情景状态
2. 根据情景文件状态选择操作方式：
   - 如果文件为空或不存在：使用write_file工具创建新的情景内容
   - 如果文件有内容：使用edit_file工具修改需要更新的具体部分
3. 分析当前对话历史，更新以下信息：
   - 对话的主要角色和身份设定
   - 当前的情境和背景
   - 重要的情节发展
   - 需要记住的关键信息
4. 完成更新后，读取情景文件并返回完整内容

注意：如果现有情景文件有内容，请保持其结构和有用信息，只修改需要更新的部分。
如果是空文件，请生成简洁明了的情景内容，文本长度控制在200-500字之间。"""
        
        return user_prompt

    async def generate_scenario(self, history: List[Dict[str, Any]]) -> str:
        """
        生成情景文件
        
        Args:
            history: 对话历史
            
        Returns:
            生成的情景内容
        """
        try:
            # 获取当前情景文件路径，直接更新这个文件
            from src.scenario.manager import scenario_manager
            scenario_file_path = os.path.abspath(scenario_manager.scenario_file_path)
            
            # 构建用户提示词
            user_message = self.build_user_prompt(history)
            
            await request_logger.log_info(f"开始生成情景，历史消息数量: {len(history)}")
            
            # 直接异步调用agent
            response = await self._run_agent_async(user_message)
            
            # 记录工作流执行日志
            log_workflow_execution("scenario_updater", response)
            
            # 尝试从生成的文件中读取内容
            scenario_content = await self._read_generated_scenario(scenario_file_path)
            
            if scenario_content:
                await request_logger.log_info(f"情景生成成功，内容长度: {len(scenario_content)}")
                return scenario_content
            else:
                # 如果文件读取失败，尝试从agent响应中提取
                await request_logger.log_warning("从文件读取情景失败，尝试从响应中提取")
                return await self._extract_scenario_from_response(response)
                
        except Exception as e:
            await request_logger.log_error(f"情景生成失败: {str(e)}")
            # 返回基于历史的简单摘要作为降级方案
            return self._create_fallback_scenario(history)
    
    async def _run_agent_async(self, user_message: str) -> Dict[str, Any]:
        """
        异步运行agent
        
        Args:
            user_message: 用户消息
            
        Returns:
            agent响应
        """
        return await self.agent.ainvoke({
            "messages": [{"role": "user", "content": user_message}]
        })
    
    async def _read_generated_scenario(self, file_path: str) -> str:
        """
        读取生成的情景文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容，如果读取失败返回空字符串
        """
        try:
            # 等待一小段时间确保文件写入完成
            await asyncio.sleep(0.5)
            
            if not os.path.exists(file_path):
                await request_logger.log_warning(f"情景文件不存在: {file_path}")
                return ""
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if content:
                await request_logger.log_info(f"成功读取生成的情景文件: {file_path}")
                return content
            else:
                await request_logger.log_warning(f"情景文件为空: {file_path}")
                return ""
                
        except Exception as e:
            await request_logger.log_error(f"读取情景文件失败 {file_path}: {str(e)}")
            return ""
    
    async def _extract_scenario_from_response(self, response: Dict[str, Any]) -> str:
        """
        从agent响应中提取情景内容
        
        Args:
            response: agent响应
            
        Returns:
            提取的情景内容
        """
        try:
            # 从response中提取最后一条assistant消息
            messages = response.get("messages", [])
            for message in reversed(messages):
                if hasattr(message, 'content') and message.content:
                    content = message.content.strip()
                    # 简单的启发式过滤，移除明显的工具调用结果
                    if len(content) > 50 and not content.startswith("文件"):
                        await request_logger.log_info("从响应中成功提取情景内容")
                        return content
            
            await request_logger.log_warning("无法从响应中提取有效的情景内容")
            return ""
            
        except Exception as e:
            await request_logger.log_error(f"从响应提取情景内容失败: {str(e)}")
            return ""
    
    def _create_fallback_scenario(self, history: List[Dict[str, Any]]) -> str:
        """
        创建降级情景（当AI生成失败时使用）
        
        Args:
            history: 对话历史
            
        Returns:
            简单的降级情景
        """
        try:
            if not history:
                return "这是一个全新的对话开始。"
            
            # 统计用户和助手消息数量
            user_count = sum(1 for msg in history if msg.get("role") == "user")
            assistant_count = sum(1 for msg in history if msg.get("role") == "assistant")
            
            # 获取最近的几条消息关键词
            recent_messages = history[-3:] if len(history) >= 3 else history
            recent_content = " ".join([
                msg.get("content", "")[:50] for msg in recent_messages 
                if msg.get("role") in ["user", "assistant"]
            ])
            
            fallback_scenario = f"""这是一个正在进行的对话。
            
对话概况：
- 已进行 {user_count} 轮用户输入，{assistant_count} 轮助手回复
- 最近讨论的内容涉及：{recent_content[:100]}...
- 当前对话氛围：继续之前的话题讨论

这是系统自动生成的基础情景，下次对话时会尝试生成更详细的情景分析。"""
            
            return fallback_scenario
            
        except Exception:
            return "这是一个继续中的对话。"


# 测试用的异步函数
async def test_scenario_updater():
    """测试情景更新器"""
    updater = ScenarioUpdaterAgent()
    
    # 模拟对话历史
    test_history = [
        {"role": "user", "content": "你好，我是小明，是一名程序员"},
        {"role": "assistant", "content": "你好小明！很高兴认识你这位程序员朋友。"},
        {"role": "user", "content": "最近在学习Python，有什么好的建议吗？"},
        {"role": "assistant", "content": "学习Python的话我建议你从基础语法开始..."}
    ]
    
    print("开始测试情景生成...")
    scenario = await updater.generate_scenario(test_history)
    print(f"生成的情景内容:\n{scenario}")


if __name__ == "__main__":
    asyncio.run(test_scenario_updater())