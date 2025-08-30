import asyncio
import json
import uuid
import os
from typing import List, Dict, Any, AsyncGenerator, Optional
from openai import AsyncOpenAI


class ReActAgent:
    def __init__(self, model: AsyncOpenAI, max_iterations: int, system_prompt: str, user_input: str, tools_with_schemas: List[Dict[str, Any]], 
                 model_name: str = "gpt-3.5-turbo", temperature: float = 0.1, max_tokens: Optional[int] = None, 
                 top_p: Optional[float] = None, frequency_penalty: Optional[float] = None, presence_penalty: Optional[float] = None,
                 history_type: str = "txt", history_path: str = "."):
        self.model = model
        self.max_iterations = max_iterations
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.history_type = history_type
        self.history_path = history_path
        
        # 从 tools_with_schemas 提取工具函数和schema
        self.tools = {tool["schema"]["function"]["name"]: tool["function"] for tool in tools_with_schemas}
        self.tools_schemas = [tool["schema"] for tool in tools_with_schemas]
        
        # 生成工具描述并嵌入到系统提示词
        tool_descriptions = self._generate_tool_descriptions(self.tools_schemas)
        self.system_prompt = system_prompt + tool_descriptions
        self.user_input = user_input
    
    def _generate_tool_descriptions(self, tools_schemas: List[Dict[str, Any]]) -> str:
        """
        从 OpenAI schema 生成统一的工具描述
        
        Args:
            tools_schemas: OpenAI 工具 schema 列表
            
        Returns:
            str: 工具描述字符串
        """
        header = """

<工具说明>
如果你要调用工具，则必须在正文中以JSON格式输出工具调用，不可以输出JSON外的任何内容。支持并发调用多个工具。
格式要求示例：
```json
{
  "tool_calls": [
    {
      "tool_name": "工具名称1",
      "arguments": {"参数名": "参数值"}
    },
    {
      "tool_name": "工具名称2",
      "arguments": {"参数名": "参数值"}
    }
  ]
}
```

可用工具：
"""
        
        tool_descriptions = [header]
        
        for i, schema in enumerate(tools_schemas):
            function_schema = schema.get("function", {})
            tool_name = function_schema.get("name", "unknown")
            tool_description = function_schema.get("description", "无描述")
            parameters = function_schema.get("parameters", {})
            
            # 工具分隔线
            if i > 0:
                tool_descriptions.append("---")
            
            # 工具名称和描述
            tool_descriptions.append(f"工具: {tool_name}")
            tool_descriptions.append(f"描述: {tool_description.strip()}")
            
            # 解析参数
            properties = parameters.get("properties", {})
            required = parameters.get("required", [])
            
            if properties:
                tool_descriptions.append("参数:")
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    is_required = param_name in required
                    required_text = "必需" if is_required else "可选"
                    
                    if param_desc:
                        tool_descriptions.append(f"  - {param_name} ({param_type}, {required_text}): {param_desc}")
                    else:
                        tool_descriptions.append(f"  - {param_name} ({param_type}, {required_text})")
            else:
                tool_descriptions.append("参数: 无")
            
            tool_descriptions.append("")  # 空行
        
        tool_descriptions.append("</工具说明>")
        return "\n".join(tool_descriptions)
    
    async def ainvoke(self) -> AsyncGenerator[str, None]:
        """异步触发 ReAct Agent，伪流式返回结果（每次迭代输出完整响应）"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_input}
        ]
        current_messages = messages.copy()
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # LLM 非流式生成响应
            response = await self._get_llm_response(current_messages)
            
            # 将这次迭代的完整响应作为一个chunk输出
            yield response
            
            # 添加 assistant 消息到对话历史
            current_messages.append({"role": "assistant", "content": response})
            
            # 解析工具调用
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # 没有工具调用，结束循环
                break
            
            # 为工具调用添加 tool_call_id 并更新消息
            tool_calls_with_id = []
            for tool_call in tool_calls:
                tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
                tool_call_with_id = {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tool_call["tool_name"],
                        "arguments": json.dumps(tool_call["arguments"])
                    }
                }
                tool_calls_with_id.append(tool_call_with_id)
            
            # 更新最后一条 assistant 消息，添加 tool_calls
            current_messages[-1]["tool_calls"] = tool_calls_with_id
            
            # 并发执行工具
            tool_results = await self._execute_tools_concurrently(tool_calls_with_id)
            
            # 添加工具结果到消息历史
            for result in tool_results:
                tool_message = {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": result["content"]
                }
                # 添加 tool_name 字段用于调试和追踪
                if "tool_name" in result:
                    tool_message["name"] = result["tool_name"]
                current_messages.append(tool_message)
        
        # 保存最终的 messages 到 JSON 文件
        await self._save_messages(current_messages)
    
    async def astream(self) -> AsyncGenerator[str, None]:
        """异步触发 ReAct Agent，流式返回结果"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_input}
        ]
        current_messages = messages.copy()
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # LLM 流式生成响应
            full_response = ""
            async for chunk in self._stream_llm_response(current_messages):
                full_response += chunk
                yield chunk
            
            # 添加 assistant 消息到对话历史
            current_messages.append({"role": "assistant", "content": full_response})
            
            # 解析工具调用
            tool_calls = self._parse_tool_calls(full_response)
            
            if not tool_calls:
                # 没有工具调用，结束循环
                break
            
            # 为工具调用添加 tool_call_id 并更新消息
            tool_calls_with_id = []
            for tool_call in tool_calls:
                tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
                tool_call_with_id = {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tool_call["tool_name"],
                        "arguments": json.dumps(tool_call["arguments"])
                    }
                }
                tool_calls_with_id.append(tool_call_with_id)
            
            # 更新最后一条 assistant 消息，添加 tool_calls
            current_messages[-1]["tool_calls"] = tool_calls_with_id
            
            # 并发执行工具
            tool_results = await self._execute_tools_concurrently(tool_calls_with_id)
            
            # 添加工具结果到消息历史
            for result in tool_results:
                tool_message = {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": result["content"]
                }
                # 添加 tool_name 字段用于调试和追踪
                if "tool_name" in result:
                    tool_message["name"] = result["tool_name"]
                current_messages.append(tool_message)
        
        # 保存最终的 messages 到 JSON 文件
        await self._save_messages(current_messages)
    
    async def _stream_llm_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """流式获取 LLM 响应"""
        try:
            # 构建请求参数
            params = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "temperature": self.temperature
            }
            
            # 添加可选参数
            if self.max_tokens is not None:
                params["max_tokens"] = self.max_tokens
            if self.top_p is not None:
                params["top_p"] = self.top_p
            if self.frequency_penalty is not None:
                params["frequency_penalty"] = self.frequency_penalty
            if self.presence_penalty is not None:
                params["presence_penalty"] = self.presence_penalty
            
            stream = await self.model.chat.completions.create(**params)
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"错误: {str(e)}"
    
    async def _get_llm_response(self, messages: List[Dict[str, str]]) -> str:
        """非流式获取 LLM 响应"""
        try:
            # 构建请求参数
            params = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "temperature": self.temperature
            }
            
            # 添加可选参数
            if self.max_tokens is not None:
                params["max_tokens"] = self.max_tokens
            if self.top_p is not None:
                params["top_p"] = self.top_p
            if self.frequency_penalty is not None:
                params["frequency_penalty"] = self.frequency_penalty
            if self.presence_penalty is not None:
                params["presence_penalty"] = self.presence_penalty
            
            response = await self.model.chat.completions.create(**params)
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            else:
                return ""
        except Exception as e:
            return f"错误: {str(e)}"
    
    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """解析 LLM 响应中的工具调用"""
        try:
            import re
            
            # 首先尝试查找 JSON 代码块
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试查找直接的 JSON 对象（不在代码块中）
                json_match = re.search(r'(\{[^{}]*"tool_calls"[^{}]*\})', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # 最后尝试整个响应是否就是JSON
                    json_str = response.strip()
            
            parsed = json.loads(json_str)
            
            if "tool_calls" in parsed and isinstance(parsed["tool_calls"], list):
                return parsed["tool_calls"]
            
            return []
        except (json.JSONDecodeError, KeyError):
            return []
    
    async def _execute_tools_concurrently(self, tool_calls_with_id: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """并发执行工具调用"""
        async def execute_single_tool(tool_call):
            tool_call_id = tool_call["id"]
            tool_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])
            
            try:
                if tool_name in self.tools:
                    if asyncio.iscoroutinefunction(self.tools[tool_name]):
                        result = await self.tools[tool_name](**arguments)
                    else:
                        result = self.tools[tool_name](**arguments)
                    return {
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "content": str(result)
                    }
                else:
                    return {
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "content": f"错误: 未知工具 '{tool_name}'"
                    }
            except Exception as e:
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "content": f"错误: {str(e)}"
                }
        
        # 并发执行所有工具调用
        tasks = [execute_single_tool(tool_call) for tool_call in tool_calls_with_id]
        return await asyncio.gather(*tasks)
    
    async def _save_messages(self, messages: List[Dict[str, Any]]):
        """根据配置保存消息历史"""
        if self.history_type == "none":
            return
        
        # 确保目录存在
        os.makedirs(self.history_path, exist_ok=True)
        
        # 生成文件名
        file_id = uuid.uuid4().hex[:8]
        
        if self.history_type == "json":
            filename = f"messages_{file_id}.json"
            filepath = os.path.join(self.history_path, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            print(f"📁 对话记录已保存到: {filepath}")
        elif self.history_type == "txt":
            filename = f"messages_{file_id}.txt"
            filepath = os.path.join(self.history_path, filename)
            await self._save_messages_as_txt(messages, filepath)
            print(f"📁 对话记录已保存到: {filepath}")
        else:
            print(f"警告: 未知的 history_type '{self.history_type}'，跳过保存")
    
    def _format_json_content(self, content: str) -> str:
        """格式化 JSON 内容为层级递进的文本"""
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            return content
    
    async def _save_messages_as_txt(self, messages: List[Dict[str, Any]], filepath: str):
        """保存消息历史为美化的文本格式"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 34 + "    Start    " + "=" * 34 + "\n")
            
            for message in messages:
                role = message.get("role", "unknown")
                
                if role == "system":
                    f.write("=" * 33 + " System Message " + "=" * 33 + "\n")
                    f.write("content: \n")
                    f.write(message.get("content", "") + "\n\n")
                
                elif role == "user":
                    f.write("=" * 34 + " User Message " + "=" * 34 + "\n")
                    f.write("content: \n")
                    f.write(message.get("content", "") + "\n\n")
                
                elif role == "assistant":
                    f.write("=" * 34 + " AI Message " + "=" * 35 + "\n")
                    f.write("content: \n")
                    content = message.get("content", "")
                    formatted_content = self._format_json_content(content)
                    f.write(formatted_content + "\n\n")
                
                elif role == "tool":
                    f.write("=" * 33 + " Tool Message " + "=" * 33 + "\n")
                    f.write("\n\n")
                    
                    # tool_call_id
                    if "tool_call_id" in message:
                        f.write("tool_call_id\n")
                        f.write("    " + message["tool_call_id"] + "\n")
                    
                    # name (tool name)
                    if "name" in message:
                        f.write("name: \n")
                        f.write("    " + message["name"] + "\n")
                    
                    # content
                    f.write("content: \n")
                    f.write("    " + message.get("content", "") + "\n\n")
            
            f.write("=" * 34 + "    END    " + "=" * 35 + "\n")