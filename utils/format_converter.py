"""
Format conversion tool: Convert LangGraph messages to OpenAI format
"""
import json
import time
import uuid
from typing import Dict, Any, Optional
from langchain_core.messages import BaseMessage, AIMessage


def convert_to_openai_format(msg: BaseMessage, metadata: Optional[Dict] = None, model: str = "deepseek-chat") -> Dict[str, Any]:
    """
    Convert LangGraph messages to OpenAI SSE format
    
    Args:
        msg: LangChain message object
        metadata: Optional metadata
        model: Model name
    
    Returns:
        Dictionary in OpenAI format
    """
    # Extract content
    content = ""
    if hasattr(msg, 'content'):
        content = msg.content
    elif isinstance(msg, dict):
        content = msg.get('content', '')
    
    # Build OpenAI format response
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {
                "content": content,
                "role": "assistant" if isinstance(msg, AIMessage) else None
            },
            "finish_reason": None
        }],
        "usage": None
    }


def convert_to_openai_sse(msg: BaseMessage, metadata: Optional[Dict] = None, model: str = "deepseek-chat") -> str:
    """
    Convert LangGraph messages to OpenAI SSE format string
    
    Args:
        msg: LangChain message object
        metadata: Optional metadata
        model: Model name
    
    Returns:
        SSE format string
    """
    openai_chunk = convert_to_openai_format(msg, metadata, model)
    return f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"


def create_done_message() -> str:
    """
    Create SSE stream end message
    
    Returns:
        SSE format DONE message
    """
    return "data: [DONE]\n\n"


def convert_final_response(response: BaseMessage, model: str = "deepseek-chat", stream: bool = False) -> Dict[str, Any]:
    """
    Convert final LLM response to OpenAI format
    
    Args:
        response: LLM response
        model: Model name
        stream: Whether it's a streaming response
    
    Returns:
        Complete response in OpenAI format
    """
    content = ""
    if hasattr(response, 'content'):
        content = response.content
    elif isinstance(response, dict):
        content = response.get('content', '')
    elif isinstance(response, str):
        content = response
    
    if stream:
        # Streaming response format
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
    else:
        # Non-streaming response format
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,  # Can be calculated in actual use
                "completion_tokens": 0,  # Can be calculated in actual use
                "total_tokens": 0
            }
        }


def extract_content_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract content from workflow events
    
    Args:
        event: Workflow event
    
    Returns:
        Extracted content, None if not found
    """
    # Try to extract content from different event types
    if 'messages' in event:
        messages = event['messages']
        if messages and len(messages) > 0:
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                return last_msg.content
            elif isinstance(last_msg, dict):
                return last_msg.get('content')
    
    if 'chunk' in event:
        chunk = event['chunk']
        if hasattr(chunk, 'content'):
            return chunk.content
        elif isinstance(chunk, dict):
            return chunk.get('content')
    
    if 'data' in event:
        data = event['data']
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            return data.get('content') or data.get('output')
    
    return None
def convert_chunk_to_sse(chunk: Any, model: str, request_id: str) -> Optional[str]:
    """
    Convert streaming chunk from LLM directly to OpenAI SSE format
    
    Args:
        chunk: LLM streaming response chunk
        model: Model name
        request_id: Request ID
        
    Returns:
        SSE format string, None if chunk is invalid
    """
    if not hasattr(chunk, 'choices') or not chunk.choices:
        return None
        
    delta = chunk.choices[0].delta
    
    # Extract content
    content = ""
    if hasattr(delta, 'content') and delta.content:
        content = delta.content
    
    # Extract reasoning content
    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
        content = delta.reasoning_content

    if not content:
        return None

    sse_data = {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {
                "role": "assistant",
                "content": content
            },
            "finish_reason": None
        }]
    }
    
    return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"
def convert_chunk_to_sse_manual(content: str, model: str, request_id: str) -> str:
    """
    Manually create SSE chunk with specified content
    """
    sse_data = {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {
                "role": "assistant",
                "content": content
            },
            "finish_reason": None
        }]
    }
    return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"


def convert_langgraph_chunk_to_sse(chunk: Any, model: str, request_id: str) -> Optional[str]:
    """
    Convert LangGraph AIMessageChunk to OpenAI SSE format
    
    Args:
        chunk: LangGraph AIMessageChunk object
        model: Model name
        request_id: Request ID
        
    Returns:
        SSE format string, None if chunk is invalid or content is empty
    """
    # Check if it's AIMessageChunk and extract content
    content = ""
    if hasattr(chunk, 'content'):
        content = chunk.content or ""
    elif isinstance(chunk, dict) and 'content' in chunk:
        content = chunk['content'] or ""
    
    # Only send SSE when content has actual content
    # Skip empty content chunks to reduce unnecessary network transmission
    if not content or content.strip() == "":
        return None

    sse_data = {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {
                "role": "assistant",
                "content": content
            },
            "finish_reason": None
        }]
    }
    
    return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"


def convert_workflow_event_to_sse(event: Dict[str, Any], model: str, request_id: str) -> Optional[str]:
    """
    Convert workflow events to SSE format, supporting multiple event types
    Based on pretty_print.py logic, converts tool calls, tool outputs, LLM outputs, etc. to SSE format
    
    Args:
        event: Workflow event
        model: Model name
        request_id: Request ID
        
    Returns:
        SSE format string, None if event doesn't need output
    """
    event_type = event.get("event", "unknown")
    name = event.get("name", "")
    data = event.get("data", {})
    
    # 1. Handle LLM streaming output
    if event_type == "on_chat_model_stream" and name == "ChatOpenAI":
        chunk = data.get("chunk", {})
        if hasattr(chunk, 'content') and chunk.content and chunk.content.strip():
            sse_data = {
                "id": f"chatcmpl-{request_id}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": chunk.content
                    },
                    "finish_reason": None
                }]
            }
            return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"
    
    # 2. Handle node start
    elif event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater"]:
        content = f"\n{'='*50}\n🔄 Starting {name} node\n{'='*50}\n"
        sse_data = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk", 
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"
    
    # 3. Handle tool call start
    elif event_type == "on_tool_start":
        tool_name = name
        tool_input = data.get("input", {})
        
        content = f"🔧 Calling tool: {tool_name}\n"
        if tool_input:
            content += "Parameters:\n"
            for key, value in tool_input.items():
                # Limit parameter value length to avoid overly long output
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                content += f"  {key}: {value_str}\n"
        
        sse_data = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant", 
                    "content": content
                },
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"
    
    # 4. Handle tool call results
    elif event_type == "on_tool_end":
        tool_name = name
        tool_output = data.get("output", "")
        
        # Add separator line, then show tool results
        content = f"{'-'*30}\n"
        
        # Special handling for sequential_thinking tool
        if tool_name == "sequential_thinking":
            try:
                if hasattr(tool_output, 'content'):
                    output_content = tool_output.content
                elif isinstance(tool_output, str):
                    output_content = tool_output
                else:
                    output_content = str(tool_output)
                
                result = json.loads(output_content)
                thought_num = result.get("thought_number", "?")
                total_thoughts = result.get("total_thoughts", "?")
                
                content += f"💭 Thinking step {thought_num}/{total_thoughts} completed\n"
            except:
                content += f"💭 {tool_name} tool execution completed\n"
        else:
            # Other tools show output results
            output_str = str(tool_output)
            if len(output_str) > 200:
                output_str = output_str[:200] + "..."
            content += f"✅ {tool_name} result:\n{output_str}\n"
        
        content += "\n"
        
        sse_data = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"
    
    # 5. Handle node completion
    elif event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater"]:
        content = f"\n✅ {name} node execution completed\n{'='*50}\n\n"
        sse_data = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": None
            }]
        }
        return f"data: {json.dumps(sse_data, ensure_ascii=False)}\n\n"
    
    return None