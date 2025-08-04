import json
import time
import uuid
import httpx
import os
import glob
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncGenerator, Union

from config.manager import settings
from utils.logger import request_logger


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[List[str]] = None


router = APIRouter()


def _parse_upstream_error(response: httpx.Response) -> Dict[str, Any]:
    """Parse error response from the upstream service, maintaining the original format."""
    try:
        # Try to parse the JSON error response
        error_data = response.json()
        return error_data
    except (json.JSONDecodeError, ValueError):
        # If not in JSON format, construct a standard error format
        return {
            "error": {
                "message": response.text or f"HTTP {response.status_code} Error",
                "type": "upstream_error",
                "code": response.status_code
            }
        }



def _check_new_conversation_trigger(messages: List[ChatMessage]) -> bool:
    """Check if a new conversation is triggered (by checking if 'deeproleplay' is in the last two user messages)."""
    user_messages = [msg for msg in messages if msg.role == "user"]
    
    # Get the last two user messages
    last_two_user_messages = user_messages[-2:] if len(user_messages) >= 2 else user_messages
    
    # Check for the 'deeproleplay' keyword (case-insensitive)
    for msg in last_two_user_messages:
        if "deeproleplay" in msg.content.lower():
            return True
    
    return False


def _clear_scenarios_directory():
    """Clean up all files in the scenarios directory."""
    try:
        scenarios_path = os.path.join(os.getcwd(), "scenarios")
        if os.path.exists(scenarios_path):
            # Get all files in the directory
            files = glob.glob(os.path.join(scenarios_path, "*"))
            for file_path in files:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            return True
    except Exception as e:
        print(f"Failed to clear scenarios directory: {e}")
        return False
    return True


def _create_debug_response(request_id: str, model: str, stream: bool = False) -> Dict[str, Any]:
    """Create a debug response with test message."""
    # Convert image to base64 for SillyTavern compatibility
    import base64
    try:
        with open("/home/chiye/worklab/deepRolePlay/pics/generate.png", "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode('utf-8')
            
        # 发送两张相同的图片来测试前端显示效果
        response_content = f'Testing two images display:\n\n图片1:\n<img src="data:image/png;base64,{img_data}" alt="Wizard 1" style="max-width: 300px;"><img src="data:image/png;base64,{img_data}" alt="Wizard 2" style="max-width: 300px;">'
            
    except FileNotFoundError:
        response_content = "🧙‍♂️ Wizard image not found, but the magic continues!"
    
    if stream:
        # Streaming response format
        return {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }]
        }
    else:
        # Non-streaming response format
        return {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": len(response_content),
                "total_tokens": 10 + len(response_content)
            }
        }


def _create_new_conversation_response(request_id: str, model: str, stream: bool = False) -> Dict[str, Any]:
    """Create a success response for a new conversation."""
    response_content = "A new conversation has been successfully started."
    
    if stream:
        # Streaming response format
        return {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }]
        }
    else:
        # Non-streaming response format
        return {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": len(response_content),
                "total_tokens": 10 + len(response_content)
            }
        }


async def _handle_new_conversation_request(
    request: Request,
    chat_request: ChatCompletionRequest
) -> Union[StreamingResponse, JSONResponse]:
    """Handle the complete logic for a new conversation request."""
    # Clean up the scenarios directory
    _clear_scenarios_directory()
    
    # Generate a request ID for logging and response
    request_id = str(uuid.uuid4())
    
    # Generate the response first, then log it
    if chat_request.stream:
        # Create a streaming response
        response_data = _create_new_conversation_response(request_id, chat_request.model, stream=True)
        
        async def new_conversation_stream():
            # Send the complete message
            yield f"data: {json.dumps(response_data)}\n\n"
            # Send the end-of-stream marker
            yield "data: [DONE]\n\n"
        
        response = StreamingResponse(
            new_conversation_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
                "X-New-Conversation": "true"
            }
        )
        
        # Log the new conversation trigger event
        await request_logger.log_request_response(
            request=request,
            response=response,
            request_body={"trigger": "new_conversation", "model": chat_request.model},
            response_body={"message": "New conversation started", "scenarios_cleared": True, "stream": True},
            duration=0.001,
            request_id=request_id
        )
        
        return response
    else:
        # Create a non-streaming response
        response_data = _create_new_conversation_response(request_id, chat_request.model, stream=False)
        response = JSONResponse(
            content=response_data,
            status_code=200,
            headers={"X-Request-ID": request_id, "X-New-Conversation": "true"}
        )
        
        # Log the new conversation trigger event
        await request_logger.log_request_response(
            request=request,
            response=response,
            request_body={"trigger": "new_conversation", "model": chat_request.model},
            response_body={"message": "New conversation started", "scenarios_cleared": True, "stream": False},
            duration=0.001,
            request_id=request_id
        )
        
        return response


async def _handle_debug_mode_request(
    request: Request,
    chat_request: ChatCompletionRequest
) -> Union[StreamingResponse, JSONResponse]:
    """Handle debug mode requests with test message."""
    request_id = str(uuid.uuid4())
    
    if chat_request.stream:
        # Create streaming response with one big chunk
        response_data = _create_debug_response(request_id, chat_request.model, stream=True)
        
        async def debug_stream():
            # Send the complete message in one chunk
            yield f"data: {json.dumps(response_data)}\n\n"
            # Send the end-of-stream marker
            yield "data: [DONE]\n\n"
        
        response = StreamingResponse(
            debug_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
                "X-Debug-Mode": "true"
            }
        )
        
        # Log the debug mode request
        await request_logger.log_request_response(
            request=request,
            response=response,
            request_body={"debug_mode": True, "model": chat_request.model},
            response_body={"message": "Test message", "debug_mode": True, "stream": True},
            duration=0.001,
            request_id=request_id
        )
        
        return response
    else:
        # Create non-streaming response
        response_data = _create_debug_response(request_id, chat_request.model, stream=False)
        response = JSONResponse(
            content=response_data,
            status_code=200,
            headers={"X-Request-ID": request_id, "X-Debug-Mode": "true"}
        )
        
        # Log the debug mode request
        await request_logger.log_request_response(
            request=request,
            response=response,
            request_body={"debug_mode": True, "model": chat_request.model},
            response_body={"message": "Test message", "debug_mode": True, "stream": False},
            duration=0.001,
            request_id=request_id
        )
        
        return response


class ProxyService:
    def __init__(self):
        self.target_url = f"{settings.proxy.target_url.rstrip('/')}/chat/completions"
        self.models_url = settings.proxy.get_models_url()
        self.timeout = settings.proxy.timeout
        
    def _get_headers(self, request: Request) -> Dict[str, str]:
        """Get request headers, extracting the Authorization header from the original request."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DeepRolePlay-Proxy/1.0"
        }
        
        # Extract the Authorization header from the original request
        auth_header = request.headers.get("authorization")
        if auth_header:
            headers["Authorization"] = auth_header
        
        return headers
    
    
    async def forward_non_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """完全基于工作流的非流式请求处理"""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 获取API密钥（优先从请求头获取，否则使用配置）
        auth_header = request.headers.get("Authorization", "")
        api_key = ""
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        if not api_key:
            api_key = settings.proxy.api_key
        
        # 导入工作流和格式转换工具
        from src.workflow.graph.scenario_workflow import create_scenario_workflow
        from utils.format_converter import convert_final_response
        
        # 创建工作流
        workflow = create_scenario_workflow()
        
        try:
            # 准备工作流输入
            workflow_input = {
                "request_id": request_id,
                "original_messages": [msg.model_dump() for msg in chat_request.messages],
                "messages": [msg.model_dump() for msg in chat_request.messages],
                "current_scenario": "",  # 将由工作流读取
                "api_key": api_key,
                "model": chat_request.model,
                "stream": False
            }
            
            # 同步执行工作流
            result = await workflow.ainvoke(workflow_input)
            
            # 从结果中提取LLM响应
            llm_response = result.get("llm_response")
            
            # 转换为OpenAI格式
            response_data = convert_final_response(llm_response, chat_request.model, stream=False)
            
            duration = time.time() - start_time
            
            # 创建响应
            response = JSONResponse(content=response_data)
            
            # 记录日志
            await request_logger.log_request_response(
                request=request,
                response=response,
                request_body=chat_request.model_dump(exclude_none=True),
                response_body=response_data,
                duration=duration,
                request_id=request_id
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            error_data = {
                "error": {
                    "message": str(e),
                    "type": "workflow_error",
                    "code": "WORKFLOW_ERROR"
                }
            }
            
            response = JSONResponse(content=error_data, status_code=500)
            
            await request_logger.log_request_response(
                request=request,
                response=response,
                request_body=chat_request.model_dump(exclude_none=True),
                response_body=error_data,
                duration=duration,
                request_id=request_id
            )
            
            return response
    
    

    
    async def forward_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """完全基于工作流的流式请求处理"""
        request_id = str(uuid.uuid4())
        
        # 获取API密钥（优先从请求头获取，否则使用配置）
        auth_header = request.headers.get("Authorization", "")
        api_key = ""
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        if not api_key:
            api_key = settings.proxy.api_key
        
        # 导入工作流和格式转换工具
        from src.workflow.graph.scenario_workflow import create_scenario_workflow
        from utils.format_converter import convert_to_openai_sse, create_done_message, extract_content_from_event
        
        # 创建工作流
        workflow = create_scenario_workflow()
        
        async def convert_to_sse():
            """将工作流消息转换为SSE格式"""
            try:
                # 准备工作流输入
                workflow_input = {
                    "request_id": request_id,
                    "original_messages": [msg.model_dump() for msg in chat_request.messages],
                    "messages": [msg.model_dump() for msg in chat_request.messages],
                    "current_scenario": "",  # 将由工作流读取
                    "api_key": api_key,
                    "model": chat_request.model,
                    "stream": chat_request.stream
                }
                
                # 使用stream_mode="messages"来获取所有LLM节点的token流
                async for msg, metadata in workflow.astream(
                    workflow_input,
                    stream_mode="messages"
                ):
                    # 不过滤！用户希望看到完整的AI思考过程
                    # 包括记忆闪回、情景更新和最终的角色回复
                    if hasattr(msg, 'content') and msg.content:
                        # 转换为OpenAI SSE格式
                        sse_chunk = convert_to_openai_sse(msg, metadata, chat_request.model)
                        yield sse_chunk
                    elif isinstance(msg, dict):
                        # 处理字典格式的消息
                        content = extract_content_from_event(msg)
                        if content:
                            from langchain_core.messages import AIMessage
                            ai_msg = AIMessage(content=content)
                            sse_chunk = convert_to_openai_sse(ai_msg, metadata, chat_request.model)
                            yield sse_chunk
                
                # 发送结束标记
                yield create_done_message()
                
            except Exception as e:
                # 错误处理
                error_data = {
                    "error": {
                        "message": str(e),
                        "type": "workflow_error",
                        "code": "WORKFLOW_ERROR"
                    }
                }
                error_chunk = f"data: {json.dumps(error_data)}\n\n"
                yield error_chunk
                yield create_done_message()
        
        return StreamingResponse(
            convert_to_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id
            }
        )
    
    async def forward_models_request(self, request: Request):
        """Forward a models query request to the target LLM service."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.models_url,
                    headers=self._get_headers(request)
                )
                
                duration = time.time() - start_time
                
                if response.status_code >= 400:
                    # Handle error response
                    error_data = _parse_upstream_error(response)
                    json_response = JSONResponse(content=error_data, status_code=response.status_code)
                    
                    await request_logger.log_request_response(
                        request=request,
                        response=json_response,
                        request_body={},
                        response_body=error_data,
                        duration=duration,
                        request_id=request_id
                    )
                    
                    return json_response
                else:
                    # Normal response
                    response_data = response.json()
                    json_response = JSONResponse(content=response_data)
                    
                    await request_logger.log_request_response(
                        request=request,
                        response=json_response,
                        request_body={},
                        response_body=response_data,
                        duration=duration,
                        request_id=request_id
                    )
                    
                    return json_response
                    
        except httpx.RequestError as e:
            duration = time.time() - start_time
            error_data = {"error": f"Request error: {str(e)}"}
            
            await request_logger.log_request_response(
                request=request,
                response=None,
                request_body={},
                response_body=error_data,
                duration=duration,
                request_id=request_id
            )
            
            raise HTTPException(
                status_code=502,
                detail=f"Could not connect to the upstream service: {str(e)}"
            )


proxy_service = ProxyService()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, chat_request: ChatCompletionRequest):
    """OpenAI-compatible chat completion endpoint."""
    
    # Check if debug mode is enabled
    if settings.proxy.debug_mode:
        return await _handle_debug_mode_request(request, chat_request)
    
    # Check if a new conversation is triggered
    if _check_new_conversation_trigger(chat_request.messages):
        return await _handle_new_conversation_request(request, chat_request)
    
    # Normal processing flow
    if chat_request.stream:
        # Streaming request: includes workflow streaming output
        return await proxy_service.forward_streaming_request(request, chat_request)
    else:
        # Non-streaming request: traditional synchronous workflow processing
        return await proxy_service.forward_non_streaming_request(request, chat_request)


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@router.get("/v1/models")
async def list_models(request: Request):
    """OpenAI-compatible model listing endpoint."""
    return await proxy_service.forward_models_request(request)