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
from src.workflow.tools.re_search_tool import re_search
from utils.history_manager import set_conversation_history


class MemoryFlashbackAgent:
    """记忆闪回代理 - 搜索历史对话中的相关信息"""
    
    def __init__(self):
        """初始化MemoryFlashbackAgent"""
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
        
        # 系统提示词 - 基于search_agent.ipynb的逻辑
        self.system_prompt = """
你是一个记忆闪回代理，模拟人脑的自动记忆联想系统。

核心职责：
当接收到新的情境描述和最新对话时，你要像人脑一样自动触发相关记忆的闪回，提供理解当前情境所需的关键背景信息。

工作流程（必须严格执行）：

1. 情境分析阶段：
   - 使用sequential_thinking工具（1-2个思考步骤）快速识别情境中的所有潜在重要实体
   - 实体类型包括：人物、物品、地点、事件、概念、情感、关系等
   - 思考哪些实体可能有重要的历史背景
   - 特别注意：识别实体之间的潜在关联关系
   - 重要：基于当前情景判断哪些实体信息已经充分，无需进一步搜索

2. 记忆搜索阶段：
   - 强烈推荐使用多实体联合搜索，捕获实体间的关联语境
   - 搜索策略（按优先级）：
     * 首选：多实体联合搜索，如"实体A.*?实体B|实体B.*?实体A"
     * 示例："摄魂怪.*?守护神|守护神.*?摄魂怪"、"卢平.*?守护神|守护神.*?卢平"
     * 次选：相关概念组合搜索，如"(守护神|牡鹿|咒语)"
     * 慎用：单实体搜索（结果过多且缺乏语境）
   - 搜索技巧：
     * 使用.*?（非贪婪匹配）连接实体，限制匹配范围
     * 构建双向搜索模式，确保不遗漏任何语序组合
     * 如果初次搜索无结果，尝试近义词或部分匹配

3. 重要性评估阶段：
   - 使用sequential_thinking工具（2-3个思考步骤）分析搜索结果
   - 评估标准：
     * 实体间的关联强度（通过联合搜索发现的关联更重要）
     * 与当前情境的相关性
     * 对理解剧情发展的必要性
     * 揭示的隐藏联系或背景
     * 情感记忆的重要性
   - 筛选出真正重要的实体（通常3-5个）

4. 记忆整合阶段：
   - 基于搜索到的段落，为每个重要实体构建连贯的记忆描述
   - 特别强调通过联合搜索发现的实体关联
   - 描述应该像真实的记忆闪回：
     * 突出实体之间的联系和互动
     * 包含时间顺序的回忆
     * 包含情感色彩
     * 暗示未来可能的发展

最终输出格式（严格按此格式）：
=== 记忆闪回 ===

**[实体名称]**
[基于搜索结果整合的记忆描述，特别强调与其他实体的关联]

**[实体名称2]**
[记忆描述...]

工具使用规范：
- sequential_thinking：总共使用3-5次，用于分析和评估
- re_search：
  * 必须优先使用多实体联合搜索
  * 每个重要实体都要与其他相关实体进行联合搜索
  * 单实体搜索仅在联合搜索无结果时作为补充

记忆闪回的艺术：
- 重点展现实体间的关联和互动
- 不是机械地列举信息，而是像人类记忆一样自然涌现
- 可以用"这让我想起..."、"记忆中..."、"曾经..."等词汇
- 重要的不是信息的完整性，而是对当前情境的启发性
- 如果某个实体确实没有历史记忆，简单说明"[新出现的实体]"
- 如果基于当前情景判断某实体信息已充分，说明"[信息充分，无需搜索]"

注意：必须基于搜索结果构建描述，不能凭空编造记忆。
"""
        
        # 创建智能代理
        self.agent = create_react_agent(
            model=self.model,
            tools=[sequential_thinking, re_search],
            prompt=self.system_prompt,
            debug=agent_config.debug,
        )
        
        print("MemoryFlashbackAgent 初始化完成!")
    
    def build_user_prompt(self, current_scenario: str, history: List[Dict[str, Any]]) -> str:
        """
        构建记忆闪回的用户提示词
        
        Args:
            current_scenario: 当前情景内容
            history: 对话历史
            
        Returns:
            完整的用户提示词
        """
        # 格式化对话历史
        history_text = format_history_for_analysis(history)
        
        # 构造完整的用户提示词
        user_prompt = f"""当前情景：
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
        
        return user_prompt
    
    async def search_memories(self, current_scenario: str, history: List[Dict[str, Any]]) -> str:
        """
        执行记忆搜索
        
        Args:
            current_scenario: 当前情景内容
            history: 对话历史
            
        Returns:
            记忆闪回结果
        """
        try:
            # 设置全局对话历史，使re_search工具能够访问
            set_conversation_history(history)
            
            # 构建用户提示词
            user_message = self.build_user_prompt(current_scenario, history)
            
            await request_logger.log_info(f"开始记忆搜索，历史消息数量: {len(history)}")
            
            # 直接异步调用agent
            response = await self._run_agent_async(user_message)
            
            # 记录工作流执行日志
            log_workflow_execution("memory_flashback", response)
            
            # 提取搜索结果
            memory_result = await self._extract_memory_from_response(response)
            
            if memory_result:
                await request_logger.log_info(f"记忆搜索成功，结果长度: {len(memory_result)}")
                return memory_result
            else:
                await request_logger.log_warning("记忆搜索未产生有效结果")
                return "=== 记忆闪回 ===\n\n暂无相关历史记忆。"
                
        except Exception as e:
            await request_logger.log_error(f"记忆搜索失败: {str(e)}")
            return "=== 记忆闪回 ===\n\n记忆搜索出现错误，无法获取历史信息。"
    
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
    
    async def _extract_memory_from_response(self, response: Dict[str, Any]) -> str:
        """
        从agent响应中提取记忆闪回内容
        
        Args:
            response: agent响应
            
        Returns:
            提取的记忆内容
        """
        try:
            # 从response中提取最后一条assistant消息
            messages = response.get("messages", [])
            for message in reversed(messages):
                if hasattr(message, 'content') and message.content:
                    content = message.content.strip()
                    # 查找记忆闪回格式的内容
                    if "=== 记忆闪回 ===" in content:
                        await request_logger.log_info("从响应中成功提取记忆闪回内容")
                        return content
            
            await request_logger.log_warning("无法从响应中提取有效的记忆闪回内容")
            return ""
            
        except Exception as e:
            await request_logger.log_error(f"从响应提取记忆内容失败: {str(e)}")
            return ""


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
你是一个专业的情景分析和总结助手。你的任务是基于对话历史和记忆闪回信息，更新情景描述文件。

工作原则：
1. 仔细分析用户提供的对话历史和记忆闪回信息
2. 提取关键的角色、情境、情节发展信息
3. 参考记忆闪回中的历史背景，确保情景连贯性
4. 生成200-500字的情景摘要
5. 摘要应该为下次对话提供有用的背景信息
6. 直接输出情景内容，不需要额外的格式说明
7. 使用中文输出
8. 将更新的情景内容保存到指定文件

可用工具：
- write_file: 将生成的情景内容写入文件
- read_target_file: 读取文件内容（如需参考现有情景文件）
- edit_file: 编辑文件的特定部分
- sequential_thinking: 进行结构化的深度思考分析（复杂情况时使用）

重要操作规则：
- 每次使用edit_file工具前，必须先使用read_target_file工具读取文件当前内容
- 这样可以确保编辑操作基于最新的文件状态，避免内容冲突
- 充分利用记忆闪回信息，确保情景更新的准确性和连贯性

请根据对话历史、记忆闪回信息分析并更新情景文件。如果情况较复杂，可以先使用sequential_thinking进行深度分析。
"""
        
        # 创建智能代理，使用所有可用工具
        self.agent = create_react_agent(
            model=self.model,
            tools=[write_file, read_target_file, edit_file, sequential_thinking],
            prompt=self.system_prompt,
            debug=agent_config.debug,
        )
        
        print("ScenarioUpdaterAgent 初始化完成!")
    
    def build_user_prompt(self, history: List[Dict[str, Any]], memory_flashback: str = "") -> str:
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
        memory_section = f"\n\n记忆闪回信息：\n{memory_flashback}" if memory_flashback else ""
        
        user_prompt = f"""请根据当前对话历史和记忆闪回信息，更新情景文件。

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
        
        return user_prompt

    async def generate_scenario(self, history: List[Dict[str, Any]]) -> str:
        """
        双节点工作流：记忆闪回 + 情景更新
        
        Args:
            history: 对话历史
            
        Returns:
            生成的情景内容
        """
        try:
            # 第一步：获取当前情景内容
            from src.scenario.manager import scenario_manager
            current_scenario = ""
            try:
                with open(scenario_manager.scenario_file_path, 'r', encoding='utf-8') as f:
                    current_scenario = f.read().strip()
            except FileNotFoundError:
                current_scenario = ""
            
            # 第二步：创建记忆闪回代理并执行搜索
            memory_agent = MemoryFlashbackAgent()
            memory_flashback = await memory_agent.search_memories(current_scenario, history)
            
            await request_logger.log_info(f"获得记忆闪回结果，长度: {len(memory_flashback)}")
            
            # 第三步：执行情景更新
            return await self._update_scenario_with_memory(history, memory_flashback)
            
        except Exception as e:
            await request_logger.log_error(f"双节点工作流执行失败: {str(e)}")
            # 降级到单节点模式
            return await self._update_scenario_with_memory(history, "")
    
    async def _update_scenario_with_memory(self, history: List[Dict[str, Any]], memory_flashback: str) -> str:
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
            user_message = self.build_user_prompt(history, memory_flashback)
            
            # 获取当前情景文件路径，直接更新这个文件
            from src.scenario.manager import scenario_manager
            scenario_file_path = os.path.abspath(scenario_manager.scenario_file_path)
            
            await request_logger.log_info(f"开始更新情景，历史消息数量: {len(history)}")
            
            # 直接异步调用agent
            response = await self._run_agent_async(user_message)
            
            # 记录工作流执行日志
            log_workflow_execution("scenario_updater", response)
            
            # 尝试从生成的文件中读取内容
            scenario_content = await self._read_generated_scenario(scenario_file_path)
            
            if scenario_content:
                await request_logger.log_info(f"情景更新成功，内容长度: {len(scenario_content)}")
                return scenario_content
            else:
                # 如果文件读取失败，尝试从agent响应中提取
                await request_logger.log_warning("从文件读取情景失败，尝试从响应中提取")
                return await self._extract_scenario_from_response(response)
                
        except Exception as e:
            await request_logger.log_error(f"情景更新失败: {str(e)}")
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
    """测试双节点情景更新器"""
    updater = ScenarioUpdaterAgent()
    
    # 模拟对话历史
    test_history = [
        {"role": "user", "content": "你好，我是小明，是一名程序员"},
        {"role": "assistant", "content": "你好小明！很高兴认识你这位程序员朋友。"},
        {"role": "user", "content": "最近在学习Python，有什么好的建议吗？"},
        {"role": "assistant", "content": "学习Python的话我建议你从基础语法开始..."}
    ]
    
    print("开始测试双节点情景更新...")
    scenario = await updater.generate_scenario(test_history)
    print(f"生成的情景内容:\n{scenario}")


async def test_memory_flashback():
    """测试记忆闪回代理"""
    memory_agent = MemoryFlashbackAgent()
    
    current_scenario = "这是一个关于哈利波特的对话场景"
    test_history = [
        {"role": "user", "content": "告诉我关于守护神咒语的故事"},
        {"role": "assistant", "content": "守护神咒语是一个强大的防御魔法..."}
    ]
    
    print("开始测试记忆闪回...")
    memory_result = await memory_agent.search_memories(current_scenario, test_history)
    print(f"记忆闪回结果:\n{memory_result}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "memory":
        asyncio.run(test_memory_flashback())
    else:
        asyncio.run(test_scenario_updater())