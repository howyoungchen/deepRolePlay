"""
事件格式化器：将LangGraph事件转换为用户友好的SSE格式
基于pretty_print的逻辑，但输出为OpenAI兼容的SSE流
"""
import json
import time
import uuid
from typing import Dict, Any, Optional


class EventFormatter:
    """LangGraph事件的SSE格式化器"""
    
    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.current_node = None
        self.message_buffer = ""
        self.ai_message_started = False
        
    def create_sse_chunk(self, content: str) -> str:
        """创建SSE格式的数据块"""
        chunk_data = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": content,
                    "role": "assistant"
                },
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
    
    def format_event_to_sse(self, event: Dict[str, Any]) -> Optional[str]:
        """
        将单个LangGraph事件格式化为SSE格式
        基于pretty_print_stream_events的逻辑
        """
        event_type = event.get("event", "unknown")
        name = event.get("name", "")
        data = event.get("data", {})
        
        # 检测节点开始
        if event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater", "llm_forwarding"]:
            self.current_node = name
            # 对llm_forwarding节点不显示开始信息
            if name != "llm_forwarding":
                content = f"\n🔄 Update from node {name}:\n\n"
                return self.create_sse_chunk(content)
            return None
        
        # 处理AI消息流输出
        if event_type == "on_chat_model_stream" and name == "ChatOpenAI" and self.current_node:
            chunk = data.get("chunk", {})
            if hasattr(chunk, 'content'):
                if not self.ai_message_started:
                    # 对llm_forwarding节点不显示AI消息标题
                    if self.current_node != "llm_forwarding":
                        header = "================================== Ai Message ==================================\n"
                        header += f"Name: {self.current_node}_agent\n\n"
                        self.ai_message_started = True
                        return self.create_sse_chunk(header)
                    else:
                        self.ai_message_started = True
                
                # 只有当content不为空时才输出和累积
                if chunk.content:
                    # 累积消息内容
                    self.message_buffer += chunk.content
                    return self.create_sse_chunk(chunk.content)
            return None
        
        # AI消息结束时的换行
        if event_type == "on_chat_model_end" and name == "ChatOpenAI" and self.current_node:
            if self.ai_message_started:
                self.ai_message_started = False
                self.message_buffer = ""
                if self.current_node != "llm_forwarding":
                    return self.create_sse_chunk("\n")
            return None
        
        # 检测工具调用开始
        if event_type == "on_tool_start" and self.current_node:
            tool_name = name
            tool_input = data.get("input", {})
            
            # 如果有AI消息缓冲区，先结束它
            if self.ai_message_started:
                self.ai_message_started = False
                
            content = "\nTool Calls:\n"
            content += f"  {tool_name}\n"
            if tool_input:
                content += "  Args:\n"
                for key, value in tool_input.items():
                    content += f"    {key}: {value}\n"
            content += "\n"
            return self.create_sse_chunk(content)
        
        # 检测工具调用结束
        if event_type == "on_tool_end" and self.current_node:
            tool_name = name
            tool_output = data.get("output", "")
            
            # 对sequential_thinking工具的输出进行特殊处理
            if tool_name == "sequential_thinking":
                try:
                    # 检查tool_output是否有content属性
                    if hasattr(tool_output, 'content'):
                        content_str = tool_output.content
                    elif isinstance(tool_output, str):
                        content_str = tool_output
                    else:
                        content_str = str(tool_output)
                    
                    result = json.loads(content_str)
                    success = result.get("success", False)
                    thought_num = result.get("thought_number", "?")
                    total_thoughts = result.get("total_thoughts", "?")
                    next_needed = result.get("next_thought_needed", False)
                    history_length = result.get("thought_history_length", "?")
                    
                    content = f"Tool Results:\n"
                    content += f"  sequential_thinking\n"
                    content += f"  Returns:\n"
                    content += f"    success: {str(success).lower()}\n"
                    content += f"    thought_number: {thought_num}\n"
                    content += f"    total_thoughts: {total_thoughts}\n"
                    content += f"    next_thought_needed: {str(next_needed).lower()}\n"
                    content += f"    thought_history_length: {history_length}\n"
                    
                    return self.create_sse_chunk(content)
                except Exception as e:
                    content = f"Tool Results:\n"
                    content += f"  sequential_thinking\n"
                    content += f"  Returns: {tool_output}\n"
                    content += f"  (Error parsing: {e})\n"
                    return self.create_sse_chunk(content)
            else:
                # 其他工具保持原有的详细显示
                content = f"\n🔧 Update from node tools:\n\n"
                content += "================================= Tool Message =================================\n"
                content += f"Name: {tool_name}\n\n"
                
                if isinstance(tool_output, str):
                    if len(tool_output) > 500:
                        content += f"{tool_output[:500]}... (truncated)\n"
                    else:
                        content += f"{tool_output}\n"
                else:
                    content += f"{tool_output}\n"
                content += "\n"
                return self.create_sse_chunk(content)
        
        # 检测节点完成
        if event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater", "llm_forwarding"]:
            node_output = data.get("output", {})
            
            # 如果有AI消息缓冲区，先结束它
            if self.ai_message_started:
                self.ai_message_started = False
                
            # 对llm_forwarding节点做特殊处理，不显示技术细节
            if name == "llm_forwarding":
                self.current_node = None
                return None
            
            content = f"✅ Node {name} completed:\n"
            for key, value in node_output.items():
                if isinstance(value, str) and len(value) > 100:
                    content += f"  {key}: {value[:100]}... (truncated)\n"
                else:
                    content += f"  {key}: {value}\n"
            content += "-" * 80 + "\n"
            self.current_node = None
            return self.create_sse_chunk(content)
        
        return None