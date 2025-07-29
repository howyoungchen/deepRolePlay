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
from utils.message import create_scenario_summary_request
from utils.logger import request_logger

# 导入工具
from src.workflow.tools.write_tool import write_file


class ScenarioUpdaterAgent:
    """基于LangGraph的情景更新代理"""
    
    def __init__(self):
        """初始化ScenarioUpdaterAgent"""
        # 从配置获取模型配置，如果不存在则使用默认值
        if hasattr(settings, 'langgraph') and hasattr(settings.langgraph, 'model'):
            model_name = settings.langgraph.model
        else:
            model_name = "deepseek-chat"
        
        # DeepSeek API配置
        self.model = ChatOpenAI(
            base_url=settings.proxy.target_url,  # 使用现有的API配置
            model=model_name,
            api_key=settings.proxy.api_key,
            temperature=0.1
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

请根据对话历史分析并生成情景文件。
"""
        
        # 创建智能代理，只使用write_file工具
        self.agent = create_react_agent(
            model=self.model,
            tools=[write_file],
            prompt=self.system_prompt,
            debug=False,
        )
        
        print("ScenarioUpdaterAgent 初始化完成!")
    
    async def generate_scenario(self, history: List[Dict[str, Any]]) -> str:
        """
        生成情景文件
        
        Args:
            history: 对话历史
            
        Returns:
            生成的情景内容
        """
        try:
            # 生成时间戳用于文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            scenario_file_path = os.path.abspath(f"./scenarios/scenario_{timestamp}.txt")
            
            # 创建摘要请求
            summary_request = create_scenario_summary_request(history)
            
            # 构造完整的用户消息
            user_message = f"""{summary_request}

请将生成的情景内容保存到文件: {scenario_file_path}

文件保存完成后，直接返回生成的情景内容。"""
            
            await request_logger.log_info(f"开始生成情景，历史消息数量: {len(history)}")
            
            # 在后台线程中运行同步的agent
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._run_agent_sync, 
                user_message
            )
            
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
    
    def _run_agent_sync(self, user_message: str) -> Dict[str, Any]:
        """
        在同步环境中运行agent
        
        Args:
            user_message: 用户消息
            
        Returns:
            agent响应
        """
        return self.agent.invoke({
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