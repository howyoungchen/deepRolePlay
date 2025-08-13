"""
结构化工具调用辅助函数
用于将原生工具调用转换为JSON结构化输出
"""

import json
import re
from typing import Dict, List, Any, Optional, Callable, Tuple
from langchain_core.tools import BaseTool
from pydantic import BaseModel


def generate_tool_prompts(tools: List[BaseTool], language: str = "zh") -> Tuple[str, str]:
    """
    生成工具描述的系统提示词和用户提示词
    
    Args:
        tools: 工具列表
        language: 语言，zh为中文，en为英文
        
    Returns:
        Tuple[str, str]: (system_prompt, user_prompt)
    """
    if language == "zh":
        system_header = """

可用工具调用格式：
你必须在正文中以JSON格式输出工具调用，不可以输出JSON外的任何内容。
格式要求：
```json
{
  "tool_calls": [
    {
      "tool_name": "工具名称",
      "arguments": {"参数名": "参数值"}
    }
  ]
}
```

可用工具：
"""
        user_header = """

工具使用说明：
"""
    else:
        system_header = """

Available tool calling format:
You must output tool calls in JSON format in the main text, and cannot output anything other than JSON.
Format requirements:
```json
{
  "tool_calls": [
    {
      "tool_name": "tool_name",
      "arguments": {"param_name": "param_value"}
    }
  ]
}
```

Available tools:
"""
        user_header = """

Tool usage instructions:
"""
    
    system_parts = [system_header]
    user_parts = [user_header]
    
    for tool in tools:
        tool_name = tool.name
        tool_description = tool.description
        
        # 获取工具参数信息
        if hasattr(tool, 'args_schema') and tool.args_schema:
            schema = tool.args_schema.model_json_schema()
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            # 系统提示词部分（简洁版本）
            system_parts.append(f"- {tool_name}: {tool_description}")
            
            # 用户提示词部分（详细版本）
            user_parts.append(f"\n**{tool_name}**:")
            user_parts.append(f"描述: {tool_description}")
            user_parts.append("参数:")
            
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
                is_required = param_name in required
                required_text = " (必需)" if is_required else " (可选)"
                user_parts.append(f"  - {param_name} ({param_type}){required_text}: {param_desc}")
        else:
            # 如果没有参数schema，只显示基本信息
            system_parts.append(f"- {tool_name}: {tool_description}")
            user_parts.append(f"\n**{tool_name}**: {tool_description}")
    
    system_prompt = "\n".join(system_parts)
    user_prompt = "\n".join(user_parts)
    
    return system_prompt, user_prompt


def parse_tool_calls(response_text: str) -> List[Dict[str, Any]]:
    """
    解析模型响应中的JSON工具调用
    
    Args:
        response_text: 模型的响应文本
        
    Returns:
        List[Dict[str, Any]]: 解析出的工具调用列表
    """
    tool_calls = []
    
    # 尝试直接解析整个响应为JSON
    try:
        data = json.loads(response_text.strip())
        if "tool_calls" in data and isinstance(data["tool_calls"], list):
            return data["tool_calls"]
    except json.JSONDecodeError:
        pass
    
    # 尝试提取JSON代码块
    json_pattern = r'```json\s*\n(.*?)\n\s*```'
    json_matches = re.findall(json_pattern, response_text, re.DOTALL)
    
    for json_text in json_matches:
        try:
            data = json.loads(json_text.strip())
            if "tool_calls" in data and isinstance(data["tool_calls"], list):
                return data["tool_calls"]
        except json.JSONDecodeError:
            continue
    
    # 尝试提取花括号包围的JSON
    brace_pattern = r'\{[^{}]*"tool_calls"[^{}]*\[[^\]]*\][^{}]*\}'
    brace_matches = re.findall(brace_pattern, response_text, re.DOTALL)
    
    for json_text in brace_matches:
        try:
            data = json.loads(json_text.strip())
            if "tool_calls" in data and isinstance(data["tool_calls"], list):
                return data["tool_calls"]
        except json.JSONDecodeError:
            continue
    
    # 如果以上都失败，尝试寻找独立的工具调用对象
    tool_call_pattern = r'\{\s*"tool_name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}\s*\}'
    individual_matches = re.findall(tool_call_pattern, response_text, re.DOTALL)
    
    for match in individual_matches:
        try:
            tool_call = json.loads(match.strip())
            if "tool_name" in tool_call and "arguments" in tool_call:
                tool_calls.append(tool_call)
        except json.JSONDecodeError:
            continue
    
    return tool_calls


def execute_tool_calls(
    tool_calls: List[Dict[str, Any]], 
    tools_dict: Dict[str, BaseTool],
    context: Optional[Any] = None
) -> List[Any]:
    """
    执行解析出的工具调用
    
    Args:
        tool_calls: 解析出的工具调用列表
        tools_dict: 工具名称到工具对象的映射
        context: 工具执行需要的上下文（如config）
        
    Returns:
        List[Any]: 工具执行结果列表
    """
    results = []
    
    for tool_call in tool_calls:
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})
        
        if tool_name not in tools_dict:
            results.append(f"错误: 未知工具 {tool_name}")
            continue
            
        tool = tools_dict[tool_name]
        
        try:
            # 根据工具类型调用
            if context is not None:
                result = tool.invoke(arguments, context)
            else:
                result = tool.invoke(arguments)
            results.append(result)
        except Exception as e:
            results.append(f"工具执行错误 {tool_name}: {str(e)}")
    
    return results


def create_pydantic_tool_dict(pydantic_models: List[BaseModel]) -> Dict[str, Dict[str, Any]]:
    """
    将Pydantic模型转换为工具字典格式，用于生成提示词
    
    Args:
        pydantic_models: Pydantic模型类列表
        
    Returns:
        Dict[str, Dict[str, Any]]: 工具名称到工具信息的映射
    """
    tool_dict = {}
    
    for model_class in pydantic_models:
        tool_name = model_class.__name__
        schema = model_class.model_json_schema()
        
        tool_info = {
            "name": tool_name,
            "description": model_class.__doc__ or schema.get("description", ""),
            "properties": schema.get("properties", {}),
            "required": schema.get("required", [])
        }
        
        tool_dict[tool_name] = tool_info
    
    return tool_dict


def generate_pydantic_tool_prompts(pydantic_models: List[BaseModel], language: str = "zh") -> Tuple[str, str]:
    """
    为Pydantic模型生成工具提示词
    
    Args:
        pydantic_models: Pydantic模型类列表
        language: 语言，zh为中文，en为英文
        
    Returns:
        Tuple[str, str]: (system_prompt, user_prompt)
    """
    if language == "zh":
        system_header = """

可用工具调用格式：
你必须在正文中以JSON格式输出工具调用，不可以输出JSON外的任何内容。
格式要求：
```json
{
  "tool_calls": [
    {
      "tool_name": "工具名称",
      "arguments": {"参数名": "参数值"}
    }
  ]
}
```

可用工具：
"""
        user_header = """

工具使用说明：
"""
    else:
        system_header = """

Available tool calling format:
You must output tool calls in JSON format in the main text, and cannot output anything other than JSON.
Format requirements:
```json
{
  "tool_calls": [
    {
      "tool_name": "tool_name",
      "arguments": {"param_name": "param_value"}
    }
  ]
}
```

Available tools:
"""
        user_header = """

Tool usage instructions:
"""
    
    system_parts = [system_header]
    user_parts = [user_header]
    
    for model_class in pydantic_models:
        tool_name = model_class.__name__
        tool_description = model_class.__doc__ or ""
        schema = model_class.model_json_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # 系统提示词部分（简洁版本）
        system_parts.append(f"- {tool_name}: {tool_description}")
        
        # 用户提示词部分（详细版本）
        user_parts.append(f"\n**{tool_name}**:")
        user_parts.append(f"描述: {tool_description}")
        user_parts.append("参数:")
        
        for param_name, param_info in properties.items():
            param_type = param_info.get('type', 'string')
            param_desc = param_info.get('description', '')
            is_required = param_name in required
            required_text = " (必需)" if is_required else " (可选)"
            user_parts.append(f"  - {param_name} ({param_type}){required_text}: {param_desc}")
    
    system_prompt = "\n".join(system_parts)
    user_prompt = "\n".join(user_parts)
    
    return system_prompt, user_prompt


def execute_pydantic_tool_calls(
    tool_calls: List[Dict[str, Any]], 
    tool_functions: Dict[str, Callable],
    context: Optional[Any] = None
) -> List[Any]:
    """
    执行基于Pydantic模型的工具调用
    
    Args:
        tool_calls: 解析出的工具调用列表
        tool_functions: 工具名称到执行函数的映射
        context: 工具执行需要的上下文
        
    Returns:
        List[Any]: 工具执行结果列表
    """
    results = []
    
    for tool_call in tool_calls:
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})
        
        if tool_name not in tool_functions:
            results.append(f"错误: 未知工具 {tool_name}")
            continue
            
        tool_function = tool_functions[tool_name]
        
        try:
            # 调用工具函数
            if context is not None:
                result = tool_function(arguments, context)
            else:
                result = tool_function(arguments)
            results.append(result)
        except Exception as e:
            results.append(f"工具执行错误 {tool_name}: {str(e)}")
    
    return results