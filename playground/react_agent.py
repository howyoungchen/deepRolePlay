#!/usr/bin/env python3
"""
LangGraph ReAct 单Agent工作流
使用create_react_agent预构建函数，集成DeepSeek API和自定义工具
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, Generator
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# 导入配置管理器
from config.manager import settings

# 导入现有工具
from tools.edit_tool import edit_file
from tools.read_tool import read_target_file  
from tools.write_tool import write_file
from tools.sequential_thinking import sequential_thinking
from pretty_print_tool import pretty_print_messages

# 自定义系统提示
SYSTEM_PROMPT = """
你是一个智能的文件操作和思考助手。你可以帮助用户进行文件读写、编辑操作，并进行深度思考分析。

可用工具：
1. read_target_file - 读取文件内容，如果文件不存在会自动创建空文件
2. write_file - 写入文件内容，会覆盖现有文件  
3. edit_file - 编辑文件的特定部分，进行精确的字符串替换
4. sequential_thinking - 进行结构化的深度思考分析

工作原则：
- 优先理解用户需求，复杂问题使用sequential_thinking分析
- 操作前先用read_target_file了解文件现状
- 编辑时优先使用edit_file进行精确修改，避免全文重写
- 遇到错误时要暴露具体问题，便于调试
- 始终使用中文与用户交流
- 操作完成后简要说明结果

请根据用户请求智能选择合适的工具组合并按逻辑顺序执行。
"""

# 工具列表
tools = [edit_file, read_target_file, write_file, sequential_thinking]


class ReactAgent:
    """基于LangGraph create_react_agent的ReAct工作流代理"""
    
    def __init__(self):
        """初始化ReactAgent"""
        # 使用agent配置
        agent_config = settings.agent
        
        # 初始化模型
        self.model = ChatOpenAI(
            base_url=agent_config.base_url,
            model=agent_config.model,
            api_key=agent_config.api_key,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            top_p=agent_config.top_p
        )
        
        # 使用create_react_agent创建智能代理
        self.agent = create_react_agent(
            model=self.model,
            tools=tools,
            prompt=SYSTEM_PROMPT,
            debug=agent_config.debug,
        )
        
        print("ReactAgent 初始化完成!")
        print(f"模型: {agent_config.model}")
        print(f"工具数量: {len(tools)}")
        print(f"调试模式: {agent_config.debug}")
        print(f"温度: {agent_config.temperature}")
    
    def run(self, message: str) -> Dict[str, Any]:
        """执行单轮对话
        
        Args:
            message: 用户输入消息
            
        Returns:
            包含messages的响应字典
        """
        try:
            response = self.agent.invoke({
                "messages": [{"role": "user", "content": message}]
            })
            return response
        except Exception as e:
            print(f"执行出错: {e}")
            raise
    
    def stream(self, message: str) -> Generator[Dict[str, Any], None, None]:
        """流式执行，实时查看agent思考和执行过程
        
        Args:
            message: 用户输入消息
            
        Yields:
            流式响应数据块
        """
        try:
            for chunk in self.agent.stream({
                "messages": [{"role": "user", "content": message}]
            }):
                yield chunk
        except Exception as e:
            print(f"流式执行出错: {e}")
            raise


if __name__ == "__main__":
    agent = ReactAgent()
    
    print("流式输出测试:")
    for chunk in agent.stream("使用sequential_thinking分析一下机器学习和深度学习的区别，然后将分析结果写入 /home/chiye/worklab/narratorAI/ml_analysis.txt 文件"):
        pretty_print_messages(chunk)
