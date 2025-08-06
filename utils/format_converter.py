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
def convert_chunk_to_sse(chunk: Any, model: str, request_id: str) -> Optional[str]:
    """
    将从LLM直接获取的流式chunk转换为OpenAI SSE格式
    
    Args:
        chunk: LLM的流式响应块
        model: 模型名称
        request_id: 请求ID
        
    Returns:
        SSE格式的字符串，如果chunk无效则返回None
    """
    if not hasattr(chunk, 'choices') or not chunk.choices:
        return None
        
    delta = chunk.choices[0].delta
    
    # 提取内容
    content = ""
    if hasattr(delta, 'content') and delta.content:
        content = delta.content
    
    # 提取推理内容
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
    手动创建包含指定内容的SSE块
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
    将LangGraph的AIMessageChunk转换为OpenAI SSE格式
    
    Args:
        chunk: LangGraph的AIMessageChunk对象
        model: 模型名称
        request_id: 请求ID
        
    Returns:
        SSE格式的字符串，如果chunk无效或内容为空则返回None
    """
    # 检查是否为AIMessageChunk并提取内容
    content = ""
    if hasattr(chunk, 'content'):
        content = chunk.content or ""
    elif isinstance(chunk, dict) and 'content' in chunk:
        content = chunk['content'] or ""
    
    # 只有当content有实际内容时才发送SSE
    # 跳过空内容的chunk以减少无用的网络传输
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
    将工作流事件转换为SSE格式，支持多种事件类型
    基于pretty_print.py的逻辑，将工具调用、工具输出、LLM输出等都转为SSE格式
    
    Args:
        event: 工作流事件
        model: 模型名称
        request_id: 请求ID
        
    Returns:
        SSE格式的字符串，如果事件不需要输出则返回None
    """
    event_type = event.get("event", "unknown")
    name = event.get("name", "")
    data = event.get("data", {})
    
    # 1. 处理LLM流式输出
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
    
    # 2. 处理节点开始
    elif event_type == "on_chain_start" and name in ["memory_flashback", "scenario_updater"]:
        content = f"\n{'='*50}\n🔄 开始执行 {name} 节点\n{'='*50}\n"
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
    
    # 3. 处理工具调用开始
    elif event_type == "on_tool_start":
        tool_name = name
        tool_input = data.get("input", {})
        
        content = f"🔧 调用工具: {tool_name}\n"
        if tool_input:
            content += "参数:\n"
            for key, value in tool_input.items():
                # 限制参数值的长度以避免过长的输出
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
    
    # 4. 处理工具调用结果
    elif event_type == "on_tool_end":
        tool_name = name
        tool_output = data.get("output", "")
        
        # 添加分割线，然后显示工具结果
        content = f"{'-'*30}\n"
        
        # 特殊处理sequential_thinking工具
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
                
                content += f"💭 思考步骤 {thought_num}/{total_thoughts} 完成\n"
            except:
                content += f"💭 {tool_name} 工具执行完成\n"
        else:
            # 其他工具显示输出结果
            output_str = str(tool_output)
            if len(output_str) > 200:
                output_str = output_str[:200] + "..."
            content += f"✅ {tool_name} 结果:\n{output_str}\n"
        
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
    
    # 5. 处理节点完成
    elif event_type == "on_chain_end" and name in ["memory_flashback", "scenario_updater"]:
        content = f"\n✅ {name} 节点执行完成\n{'='*50}\n\n"
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