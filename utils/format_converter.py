"""
格式转换工具：将LangGraph消息转换为OpenAI格式
"""
import json
import time
import uuid
from typing import Dict, Any, Optional
from langchain_core.messages import BaseMessage, AIMessage


def convert_to_openai_format(msg: BaseMessage, metadata: Optional[Dict] = None, model: str = "deepseek-chat") -> Dict[str, Any]:
    """
    将LangGraph消息转换为OpenAI SSE格式
    
    Args:
        msg: LangChain消息对象
        metadata: 可选的元数据
        model: 模型名称
    
    Returns:
        OpenAI格式的字典
    """
    # 提取内容
    content = ""
    if hasattr(msg, 'content'):
        content = msg.content
    elif isinstance(msg, dict):
        content = msg.get('content', '')
    
    # 构建OpenAI格式响应
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
    将LangGraph消息转换为OpenAI SSE格式的字符串
    
    Args:
        msg: LangChain消息对象
        metadata: 可选的元数据
        model: 模型名称
    
    Returns:
        SSE格式的字符串
    """
    openai_chunk = convert_to_openai_format(msg, metadata, model)
    return f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"


def create_done_message() -> str:
    """
    创建SSE流结束消息
    
    Returns:
        SSE格式的DONE消息
    """
    return "data: [DONE]\n\n"


def convert_final_response(response: BaseMessage, model: str = "deepseek-chat", stream: bool = False) -> Dict[str, Any]:
    """
    将最终的LLM响应转换为OpenAI格式
    
    Args:
        response: LLM响应
        model: 模型名称
        stream: 是否为流式响应
    
    Returns:
        OpenAI格式的完整响应
    """
    content = ""
    if hasattr(response, 'content'):
        content = response.content
    elif isinstance(response, dict):
        content = response.get('content', '')
    elif isinstance(response, str):
        content = response
    
    if stream:
        # 流式响应格式
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
        # 非流式响应格式
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
                "prompt_tokens": 0,  # 可以在实际使用时计算
                "completion_tokens": 0,  # 可以在实际使用时计算
                "total_tokens": 0
            }
        }


def extract_content_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    从工作流事件中提取内容
    
    Args:
        event: 工作流事件
    
    Returns:
        提取的内容，如果没有则返回None
    """
    # 尝试从不同的事件类型中提取内容
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