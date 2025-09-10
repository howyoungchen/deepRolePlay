"""
Streaming Event Conversion Tool
Converts LangGraph workflow events to OpenAI-compatible SSE format
"""
import json
import time
import uuid
from typing import Dict, Any, AsyncGenerator
from .format_converter import (
    convert_reasoning_chunk_to_sse_manual, 
    create_reasoning_start_chunk, 
    create_reasoning_end_chunk,
    convert_chunk_to_sse_manual
)


class WorkflowStreamConverter:
    """Workflow Streaming Event Converter"""
    
    def __init__(self, request_id: str = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.created_time = int(time.time())
        self.current_node = None
        self.ai_message_started = False
    
    def create_sse_data(self, content: str, event_type: str = "workflow", use_reasoning: bool = False) -> str:
        """Create SSE formatted data with optional reasoning content support"""
        if use_reasoning:
            # Use reasoning_content field for thinking content
            delta = {
                "role": "assistant",
                "reasoning_content": content
            }
        else:
            # Use regular content field for workflow events
            delta = {
                "content": content,
                "role": "assistant" if event_type == "workflow" else "system"
            }
        
        chunk_data = {
            "id": f"chatcmpl-{self.request_id}",
            "object": "chat.completion.chunk",
            "created": self.created_time,
            "model": "DeepRolePlay-workflow",
            "choices": [{
                "index": 0,
                "delta": delta,
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
            # Signal start of reasoning process
            yield create_reasoning_start_chunk("DeepRolePlay-workflow", self.request_id)
            
            # Send workflow start event as reasoning content
            yield self.create_sse_data("🔄 Starting to update scenario...\n\n", "workflow_start", use_reasoning=True)
            
            async for event in workflow_events:
                sse_chunk = self._process_event(event)
                if sse_chunk:
                    yield sse_chunk
            
            # Send workflow completion event as reasoning content
            yield self.create_sse_data("\n✅ Scenario update complete, starting to generate response...\n\n", "workflow_end", use_reasoning=True)
            
            # Signal end of reasoning process
            yield create_reasoning_end_chunk("DeepRolePlay-workflow", self.request_id)
            
            yield self.create_workflow_done_event()
            
        except Exception as e:
            error_msg = f"❌ Error executing workflow: {str(e)}\n\n"
            yield self.create_sse_data(error_msg, "workflow_error", use_reasoning=True)
            
            # Signal end of reasoning process even in error cases
            yield create_reasoning_end_chunk("DeepRolePlay-workflow", self.request_id)
            
            yield self.create_workflow_done_event()
    
    def _process_event(self, event: Dict[str, Any]) -> str:
        """Process a single workflow event"""
        event_type = event.get("event", "unknown")
        name = event.get("name", "")
        data = event.get("data", {})
        
        # Node start
        if event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater", "llm_forwarding"]:
            self.current_node = name
            node_name_map = {
                "memory_flashback": "Memory Flashback",
                "scenario_updater": "Scenario Updater",
                "llm_forwarding": "LLM Forwarding"
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
                    return self.create_sse_data(header, "ai_thinking", use_reasoning=True)
                
                # Forward AI thinking content as reasoning content
                return self.create_sse_data(chunk.content, "ai_content", use_reasoning=True)
        
        # AI message end
        if event_type == "on_chat_model_end" and self.current_node and self.ai_message_started:
            self.ai_message_started = False
            return self.create_sse_data("\n", "ai_end", use_reasoning=True)
        
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
            
            return self.create_sse_data(content, "tool_start", use_reasoning=True)
        
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
            
            return self.create_sse_data(content, "tool_end", use_reasoning=True)
        
        # Node complete
        if event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater", "llm_forwarding"]:
            node_output = data.get("output", {})
            
            node_name_map = {
                "memory_flashback": "Memory Flashback",
                "scenario_updater": "Scenario Updater",
                "llm_forwarding": "LLM Forwarding"
            }
            
            content = f"✅ Node {node_name_map.get(name, name)} complete\n"
            
            # 对于llm_forwarding节点，特殊处理输出格式
            if name == "llm_forwarding":
                llm_response = node_output.get("llm_response")
                if llm_response and hasattr(llm_response, 'content'):
                    response_preview = llm_response.content[:200] + "..." if len(llm_response.content) > 200 else llm_response.content
                    content += f"  Response: {response_preview}\n"
                if hasattr(llm_response, 'reasoning_content') and llm_response.reasoning_content:
                    content += f"  Has reasoning content: Yes\n"
            else:
                for key, value in node_output.items():
                    if isinstance(value, str) and len(value) > 100:
                        content += f"  {key}: {value[:100]}...\n"
                    else:
                        content += f"  {key}: {value}\n"
            
            content += "\n" + "-" * 50 + "\n"
            
            self.current_node = None
            return self.create_sse_data(content, "node_end", use_reasoning=True)
        
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