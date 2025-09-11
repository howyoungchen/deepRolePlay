"""
检查最后AI回复索引的工作流
基于 ReAct 架构，分析对话历史中的assistant消息，智能判断last_ai_response_index
"""

import asyncio
import sys
import os
import json
from typing import Dict, Any, List
from openai import AsyncOpenAI

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.manager import settings
from src.workflow.graph.reAct import ReActAgent


class CheckLastAIResponseIndexWorkflow:
    """检查最后AI回复索引的工作流"""
    
    def __init__(self):
        """初始化工作流"""
        # 初始化OpenAI客户端
        agent_config = settings.agent
        self.client = AsyncOpenAI(
            api_key=agent_config.api_key,
            base_url=agent_config.base_url
        )
        
        # 存储判断结果
        self.selected_index = None
    
    def _extract_assistant_messages(self, messages: List[Dict[str, Any]], max_count: int = 8) -> Dict[str, str]:
        """倒序提取assistant消息
        
        Args:
            messages: 对话消息列表
            max_count: 最多提取的消息数量（默认8条）
            
        Returns:
            Dict[str, str]: 格式化的assistant消息字典 {"1": content, "2": content, ...}
        """
        # 倒序提取assistant消息
        assistant_messages = []
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and len(assistant_messages) < max_count:
                content = msg.get("content", "").strip()
                if content:  # 只保留非空内容
                    assistant_messages.append(content)
        
        # 保持倒序排列（最新的消息索引为1）
        
        # 格式化为字典
        result = {}
        for i, content in enumerate(assistant_messages, 1):
            result[str(i)] = content
        
        return result
    
    def _wrap_set_index_tool(self):
        """包装设置索引工具，返回完整的工具格式"""
        def set_last_ai_response_index(index: int) -> str:
            """设置最后AI回复的索引
            
            Args:
                index: 选择的assistant消息索引（1表示最新，2表示倒数第二个，以此类推）
                
            Returns:
                确认信息
            """
            try:
                self.selected_index = index
                return f"设置last_ai_response_index为: {index}"
            except Exception as e:
                return f"设置索引失败: {str(e)}"
        
        set_last_ai_response_index.__name__ = "set_last_ai_response_index"
        
        # 返回包含function和schema的完整工具格式
        return {
            "function": set_last_ai_response_index,
            "schema": {
                "type": "function",
                "function": {
                    "name": "set_last_ai_response_index",
                    "description": "设置最后AI回复的索引",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "index": {
                                "type": "integer",
                                "description": "选择的assistant消息索引（1表示最新，2表示倒数第二个，以此类推）"
                            }
                        },
                        "required": ["index"]
                    }
                }
            }
        }
    
    def _build_system_prompt(self, assistant_messages: Dict[str, str]) -> str:
        """构建系统提示词"""
        messages_text = json.dumps(assistant_messages, ensure_ascii=False, indent=2)
        
        return f"""你是一个专门分析角色扮演对话的智能助手。你的任务是从assistant消息中识别出最后一条真正在进行角色扮演的AI回复。

重要说明：在角色扮演对话中，assistant消息可能包含两种类型：
1. 预设消息：SillyTavern等工具为引导写作而人为构建的消息，包含写作注意事项、风格指导、角色设定说明、系统提示等
2. 角色扮演消息：AI真正扮演角色、推进剧情、进行角色互动的实质性内容

以下是需要分析的assistant消息（按倒序排列，1是最新的）：

{messages_text}

判断标准（按优先级排序）：
1. 角色扮演性质：必须是AI真正在扮演角色，而非系统指导或预设说明
2. 剧情推进价值：包含角色对话、动作描述、场景描绘、情感表达、故事发展等
3. 内容完整性：优先选择内容丰富、描述完整的角色扮演回复（通常>100字符）
4. 时序合理性：在多个符合条件的消息中，选择最新的一条

必须排除的内容：
- 写作指导和技巧说明（如"请注意保持角色一致性"）
- 系统性提示或元信息（如"记住你的角色设定"）
- 纯粹的设定说明而非角色扮演
- 过于简短或无实质内容的回复（如"好的"、"明白了"）
- 明显的预设模板或示例消息

你需要找出最新的一条真正在角色扮演、推进故事的AI回复。

请使用set_last_ai_response_index工具来设置你选择的索引。"""

    def _build_user_input(self) -> str:
        """构建用户输入"""
        return """请分析上述assistant消息，找出最新的一条真正在进行角色扮演的AI回复。
        
重点关注：
1. 这条消息是否在真正扮演角色（而非给出指导或说明）
2. 是否包含推进剧情的实质性内容
3. 排除所有预设、写作指导和系统提示类消息

如果所有消息都不是标准的角色扮演内容，请选择最接近角色扮演性质的一条。"""
    
    async def run(self, messages: List[Dict[str, Any]]) -> int:
        """运行检查工作流
        
        Args:
            messages: 对话消息列表
            
        Returns:
            int: 选择的assistant消息索引，如果失败返回-1
        """
        try:
            print("Check Last AI Response Index Workflow starting...", flush=True)
            
            # 重置结果
            self.selected_index = None
            
            # 提取assistant消息
            assistant_messages = self._extract_assistant_messages(messages)
            
            if not assistant_messages:
                error_msg = "未找到任何assistant消息"
                print(error_msg, flush=True)
                return -1
            
            print(f"提取到 {len(assistant_messages)} 条assistant消息", flush=True)
            
            # 构建工具列表
            tools_with_schemas = [self._wrap_set_index_tool()]
            
            # 构建提示词
            system_prompt = self._build_system_prompt(assistant_messages)
            user_input = self._build_user_input()
            
            # 获取配置
            agent_config = settings.agent
            
            # 创建ReAct智能体（硬编码最大迭代次数为1）
            agent = ReActAgent(
                model=self.client,
                max_iterations=1,  # 硬编码为1次迭代
                system_prompt=system_prompt,
                user_input=user_input,
                tools_with_schemas=tools_with_schemas,
                model_name=agent_config.model,
                temperature=agent_config.temperature,
                max_tokens=agent_config.max_tokens if hasattr(agent_config, 'max_tokens') else None,
                history_type="txt",  # 不需要历史记录
                history_path="./logs"
            )
            
            # 执行智能体（不输出流式内容）
            if agent_config.stream_mode:
                # 真流式：实时字符输出，但不输出到外部
                async for chunk in agent.astream():
                    pass  # 只执行，不输出
            else:
                # 伪流式：每次迭代输出完整响应，但不输出到外部
                async for chunk in agent.ainvoke():
                    pass  # 只执行，不输出
            
            # 输出最终结果并返回索引
            if self.selected_index is not None:
                print(f"判断完成！推荐的last_ai_response_index: {self.selected_index}", flush=True)
                return self.selected_index
            else:
                print("未能确定合适的索引", flush=True)
                return -1
                
        except Exception as e:
            error_msg = f"Check Index Workflow 执行失败: {str(e)}"
            print(error_msg, flush=True)
            return -1
    
    def get_selected_index(self) -> int:
        """获取选择的索引"""
        return self.selected_index


# 创建工作流实例的工厂函数
def create_check_index_workflow() -> CheckLastAIResponseIndexWorkflow:
    """创建检查索引工作流实例"""
    return CheckLastAIResponseIndexWorkflow()
