"""
极简版思考工具
简化自原有的sequential_thinking，去除所有复杂功能，只保留核心思考能力
"""

import json
from typing import Dict, Any


async def simple_thinking(thought: str) -> str:
    """
    简单的思考工具，用于记录和输出思考过程
    
    Args:
        thought: 当前的思考内容、分析或推理过程
    
    Returns:
        返回格式化的思考内容
    """
    # 简单记录并返回，添加思考emoji标识
    formatted_thought = f"💭 思考: {thought}"
    
    # 可选：输出到控制台（用于调试）
    # print(formatted_thought)
    
    return formatted_thought


# OpenAI 函数调用 schema 定义
simple_thinking_schema = {
    "type": "function",
    "function": {
        "name": "simple_thinking",
        "description": "用于思考和推理的简单工具。输入你的思考内容，工具会记录并返回。适用于需要展示推理过程、分析问题或记录思考步骤的场景。",
        "parameters": {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "当前的思考内容、分析过程或推理步骤。应该清晰描述你正在思考的内容，比如：问题分析、解决方案考虑、信息整理、判断推理等。"
                }
            },
            "required": ["thought"],
            "additionalProperties": False
        },
        "strict": True
    }
}

# 导出工具配置（保持与原版本的兼容性）
thinking_tool = {
    "function": simple_thinking,
    "schema": simple_thinking_schema
}

# 为了方便直接使用，也可以单独导出
__all__ = ["simple_thinking", "simple_thinking_schema", "thinking_tool"]