"""
流式事件转换工具
将LangGraph工作流事件转换为OpenAI兼容的SSE格式
"""
import json
import time
import uuid
from typing import Dict, Any, AsyncGenerator


class WorkflowStreamConverter:
    """工作流流式事件转换器"""
    
    def __init__(self, request_id: str = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.created_time = int(time.time())
        self.current_node = None
        self.message_buffer = ""
        self.ai_message_started = False
    
    def create_sse_data(self, content: str, event_type: str = "workflow") -> str:
        """创建SSE格式的数据"""
        chunk_data = {
            "id": f"chatcmpl-{self.request_id}",
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": "DeepRolePlay-workflow",
            "choices": [{
                "index": 0,
                "delta": {
                    "content": content,
                    "role": "assistant" if event_type == "workflow" else "system"
                },
                "finish_reason": None
            }],
            "workflow_event": True,
            "event_type": event_type
        }
        return f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
    
    def create_workflow_done_event(self) -> str:
        """创建工作流完成事件"""
        chunk_data = {
            "id": f"chatcmpl-{self.request_id}",
            "object": "chat.completion.chunk", 
            "created": self.created_time,
            "model": "DeepRolePlay-workflow",
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "workflow_complete"
            }],
            "workflow_event": True,
            "event_type": "workflow_complete"
        }
        return f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
    
    async def convert_workflow_events(
        self, 
        workflow_events: AsyncGenerator[Dict[str, Any], None]
    ) -> AsyncGenerator[str, None]:
        """
        转换工作流事件为SSE流
        
        Args:
            workflow_events: 工作流事件异步生成器
            
        Yields:
            SSE格式的字符串
        """
        try:
            # 发送工作流开始事件
            yield self.create_sse_data("🔄 开始更新情景...\n\n", "workflow_start")
            
            async for event in workflow_events:
                sse_chunk = self._process_event(event)
                if sse_chunk:
                    yield sse_chunk
            
            # 发送工作流完成事件
            yield self.create_sse_data("\n✅ 情景更新完成，开始生成回复...\n\n", "workflow_end")
            yield self.create_workflow_done_event()
            
        except Exception as e:
            error_msg = f"❌ 工作流执行出错: {str(e)}\n\n"
            yield self.create_sse_data(error_msg, "workflow_error")
            yield self.create_workflow_done_event()
    
    def _process_event(self, event: Dict[str, Any]) -> str:
        """处理单个工作流事件"""
        event_type = event.get("event", "unknown")
        name = event.get("name", "")
        data = event.get("data", {})
        
        # 节点开始
        if event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater"]:
            self.current_node = name
            node_name_map = {
                "memory_flashback": "记忆闪回",
                "scenario_updater": "情景更新"
            }
            content = f"🔄 开始执行 {node_name_map.get(name, name)} 节点...\n"
            return self.create_sse_data(content, "node_start")
        
        # AI消息流式输出
        if event_type == "on_chat_model_stream" and self.current_node:
            chunk = data.get("chunk", {})
            if hasattr(chunk, 'content') and chunk.content:
                if not self.ai_message_started:
                    self.ai_message_started = True
                    header = f"\n💭 {self.current_node} 思考中:\n"
                    return self.create_sse_data(header, "ai_thinking")
                
                # 返回AI思考内容
                return self.create_sse_data(chunk.content, "ai_content")
        
        # AI消息结束
        if event_type == "on_chat_model_end" and self.current_node and self.ai_message_started:
            self.ai_message_started = False
            return self.create_sse_data("\n", "ai_end")
        
        # 工具调用开始
        if event_type == "on_tool_start" and self.current_node:
            tool_name = name
            tool_input = data.get("input", {})
            
            content = f"\n🔧 调用工具: {tool_name}\n"
            if tool_input:
                content += "参数:\n"
                for key, value in tool_input.items():
                    # 截断长内容
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    content += f"  {key}: {value}\n"
            content += "\n"
            
            return self.create_sse_data(content, "tool_start")
        
        # 工具调用结束
        if event_type == "on_tool_end" and self.current_node:
            tool_name = name
            tool_output = data.get("output", "")
            
            content = f"✅ 工具 {tool_name} 执行完成\n"
            if isinstance(tool_output, str):
                if len(tool_output) > 200:
                    content += f"输出: {tool_output[:200]}...\n"
                else:
                    content += f"输出: {tool_output}\n"
            content += "\n"
            
            return self.create_sse_data(content, "tool_end")
        
        # 节点完成
        if event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater"]:
            node_output = data.get("output", {})
            
            node_name_map = {
                "memory_flashback": "记忆闪回",
                "scenario_updater": "情景更新"
            }
            
            content = f"✅ {node_name_map.get(name, name)} 节点完成\n"
            for key, value in node_output.items():
                if isinstance(value, str) and len(value) > 100:
                    content += f"  {key}: {value[:100]}...\n"
                else:
                    content += f"  {key}: {value}\n"
            content += "\n" + "-" * 50 + "\n"
            
            self.current_node = None
            return self.create_sse_data(content, "node_end")
        
        return None


async def create_unified_stream(
    workflow_events: AsyncGenerator[Dict[str, Any], None],
    llm_stream: AsyncGenerator[str, None],
    request_id: str = None
) -> AsyncGenerator[str, None]:
    """
    创建统一的流式输出，合并工作流事件和LLM响应
    
    Args:
        workflow_events: 工作流事件流
        llm_stream: LLM响应流  
        request_id: 请求ID
        
    Yields:
        统一的SSE格式流
    """
    converter = WorkflowStreamConverter(request_id)
    
    # 先输出工作流事件
    async for sse_chunk in converter.convert_workflow_events(workflow_events):
        yield sse_chunk
    
    # 再输出LLM响应
    async for llm_chunk in llm_stream:
        yield llm_chunk