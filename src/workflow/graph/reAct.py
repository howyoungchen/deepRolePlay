import asyncio
import json
import uuid
import inspect
import os
from typing import List, Dict, Any, AsyncGenerator, Optional, Tuple, Callable
from openai import AsyncOpenAI


class ReActAgent:
    def __init__(self, model: AsyncOpenAI, max_iterations: int, system_prompt: str, user_input: str, tools_list: List[Callable], 
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
        self.tools = {func.__name__: func for func in tools_list}
        
        # 生成工具提示词
        tool_system_prompt, tool_user_prompt = self.generate_tool_prompts(tools_list)
        
        # 嵌入提示词
        self.system_prompt = system_prompt + tool_system_prompt
        self.user_input = tool_user_prompt + user_input
    
    def generate_tool_prompts(self, tools: List[Callable], language: str = "zh") -> Tuple[str, str]:
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

<工具使用说明系统提示词>
可用工具调用格式：
你必须在正文中以JSON格式输出工具调用，不可以输出JSON外的任何内容。
支持一次调用多个工具
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
            user_header = """

<工具使用说明用户提示词>
工具使用说明：
"""
        else:
            system_header = """

<工具使用说明系统提示词>
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

<工具使用说明用户提示词>
Tool usage instructions:
"""
        
        system_parts = [system_header]
        user_parts = [user_header]
        
        for tool in tools:
            tool_name = tool.__name__
            tool_description = tool.__doc__ or "无描述"
            
            # 获取函数签名
            sig = inspect.signature(tool)
            
            # 系统提示词部分（简洁版本）
            system_parts.append(f"- {tool_name}: {tool_description.strip()}")
            
            # 用户提示词部分（详细版本）
            user_parts.append(f"\n**{tool_name}**:")
            user_parts.append(f"描述: {tool_description.strip()}")
            user_parts.append("参数:")
            
            for param_name, param in sig.parameters.items():
                param_type = param.annotation.__name__ if param.annotation != inspect.Parameter.empty else "Any"
                default_text = f" (默认: {param.default})" if param.default != inspect.Parameter.empty else ""
                is_required = param.default == inspect.Parameter.empty
                required_text = " (必需)" if is_required else " (可选)"
                user_parts.append(f"  - {param_name} ({param_type}){required_text}{default_text}")
        
        system_prompt = "\n".join(system_parts) + "\n</工具使用说明系统提示词>"
        user_prompt = "\n".join(user_parts) + "\n</工具使用说明用户提示词>"
        
        return system_prompt, user_prompt
    
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
                if chunk.choices[0].delta.content:
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
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"错误: {str(e)}"
    
    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """解析 LLM 响应中的工具调用"""
        try:
            # 查找 JSON 代码块
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if not json_match:
                return []
            
            json_str = json_match.group(1)
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
            print(f"对话记录已保存到: {filepath}")
        elif self.history_type == "txt":
            filename = f"messages_{file_id}.txt"
            filepath = os.path.join(self.history_path, filename)
            await self._save_messages_as_txt(messages, filepath)
            print(f"对话记录已保存到: {filepath}")
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