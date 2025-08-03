"""
Streaming Event Conversion Tool
Converts LangGraph workflow events to OpenAI-compatible SSE format
"""
import json
import time
import uuid
from typing import Dict, Any, AsyncGenerator


class WorkflowStreamConverter:
    """Workflow Streaming Event Converter"""
    
    def __init__(self, request_id: str = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.created_time = int(time.time())
        self.current_node = None
        self.ai_message_started = False
    
    def create_sse_data(self, content: str, event_type: str = "workflow") -> str:
        """Create SSE formatted data"""
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
        """Create workflow completion event"""
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
        Convert workflow events to an SSE stream
        
        Args:
            workflow_events: Asynchronous generator for workflow events
            
        Yields:
            SSE formatted string
        """
        try:
            # Send workflow start event
            yield self.create_sse_data("🔄 Starting to update scenario...\n\n", "workflow_start")
            
            async for event in workflow_events:
                sse_chunk = self._process_event(event)
                if sse_chunk:
                    yield sse_chunk
            
            # Send workflow completion event
            yield self.create_sse_data("\n✅ Scenario update complete, starting to generate response...\n\n", "workflow_end")
            yield self.create_workflow_done_event()
            
        except Exception as e:
            error_msg = f"❌ Error executing workflow: {str(e)}\n\n"
            yield self.create_sse_data(error_msg, "workflow_error")
            yield self.create_workflow_done_event()
    
    def _process_event(self, event: Dict[str, Any]) -> str:
        """Process a single workflow event"""
        event_type = event.get("event", "unknown")
        name = event.get("name", "")
        data = event.get("data", {})
        
        # Node start
        if event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater"]:
            self.current_node = name
            node_name_map = {
                "memory_flashback": "Memory Flashback",
                "scenario_updater": "Scenario Updater"
            }
            content = f"🔄 Starting node {node_name_map.get(name, name)}...\n"
            return self.create_sse_data(content, "node_start")
        
        # AI message stream output
        if event_type == "on_chat_model_stream" and self.current_node:
            chunk = data.get("chunk", {})
            if hasattr(chunk, 'content') and chunk.content:
                if not self.ai_message_started:
                    self.ai_message_started = True
                    header = f"\n💭 {self.current_node} thinking:\n"
                    return self.create_sse_data(header, "ai_thinking")
                
                # Forward directly, no buffering
                return self.create_sse_data(chunk.content, "ai_content")
        
        # AI message end
        if event_type == "on_chat_model_end" and self.current_node and self.ai_message_started:
            self.ai_message_started = False
            return self.create_sse_data("\n", "ai_end")
        
        # Tool call start
        if event_type == "on_tool_start" and self.current_node:
            tool_name = name
            tool_input = data.get("input", {})
            
            content = f"\n🔧 Calling tool: {tool_name}\n"
            if tool_input:
                content += "Arguments:\n"
                for key, value in tool_input.items():
                    # Truncate long content
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    content += f"  {key}: {value}\n"
            content += "\n"
            
            return self.create_sse_data(content, "tool_start")
        
        # Tool call end
        if event_type == "on_tool_end" and self.current_node:
            tool_name = name
            tool_output = data.get("output", "")
            
            content = f"✅ Tool {tool_name} execution complete\n"
            if isinstance(tool_output, str):
                if len(tool_output) > 200:
                    content += f"Output: {tool_output[:200]}...\n"
                else:
                    content += f"Output: {tool_output}\n"
            content += "\n"
            
            return self.create_sse_data(content, "tool_end")
        
        # Node complete
        if event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater"]:
            node_output = data.get("output", {})
            
            node_name_map = {
                "memory_flashback": "Memory Flashback",
                "scenario_updater": "Scenario Updater"
            }
            
            content = f"✅ Node {node_name_map.get(name, name)} complete\n"
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
    Create a unified stream, merging workflow events and LLM response
    
    Args:
        workflow_events: Workflow event stream
        llm_stream: LLM response stream
        request_id: Request ID
        
    Yields:
        Unified SSE formatted stream
    """
    converter = WorkflowStreamConverter(request_id)
    
    # First, output workflow events
    async for sse_chunk in converter.convert_workflow_events(workflow_events):
        yield sse_chunk
    
    # Then, output the LLM response
    async for llm_chunk in llm_stream:
        yield llm_chunk