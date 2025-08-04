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
from utils.messages_process import inject_scenario
from src.scenario.manager import scenario_manager


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


def _create_sse_error_chunk(error_data: Dict[str, Any]) -> str:
    """Create an SSE-formatted error chunk."""
    return f"data: {json.dumps(error_data)}\n\n"


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
    
    async def _forward_non_streaming(
        self,
        request: Request,
        request_data: Dict[str, Any]
    ) -> Union[Dict[str, Any], tuple]:
        """Forward a non-streaming request."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.target_url,
                headers=self._get_headers(request),
                json=request_data
            )
            
            if response.status_code >= 400:
                # Return error data and status code
                error_data = _parse_upstream_error(response)
                return error_data, response.status_code
            
            return response.json()
    
    async def _forward_streaming(
        self,
        request: Request,
        request_data: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Forward a streaming request."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self.target_url,
                headers=self._get_headers(request),
                json=request_data
            ) as response:
                if response.status_code >= 400:
                    # Read the error response content
                    error_content = await response.aread()
                    # Try to parse as JSON
                    try:
                        error_data = json.loads(error_content.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        error_data = {
                            "error": {
                                "message": error_content.decode('utf-8') or f"HTTP {response.status_code} Error",
                                "type": "upstream_error",
                                "code": response.status_code
                            }
                        }
                    yield {"error": True, "status_code": response.status_code, "data": error_data}
                    return
                
                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk
    
    async def forward_non_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """Forward a non-streaming request to the target LLM service."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 1. Extract original messages
        original_messages = [msg.model_dump() for msg in chat_request.messages]
        
        # 2. Check if the workflow is enabled
        if settings.workflow.enabled:
            # Workflow enabled: execute the full scenario processing flow
            # 2a. Synchronously update the scenario and get the latest content
            await scenario_manager.update_scenario(original_messages)
            
            # 3. Read the current scenario content
            from utils.scenario_utils import read_scenario
            current_scenario = await read_scenario()
            
            # 4. Inject the scenario into the messages
            injected_messages = inject_scenario(original_messages, current_scenario)
        else:
            # Workflow disabled: use the original messages directly
            injected_messages = original_messages
        
        # 5. Create the request data
        request_data = chat_request.model_dump(exclude_none=True)
        request_data["messages"] = injected_messages
        
        try:
            if chat_request.stream:
                return await self._handle_streaming_request(
                    request, request_data, request_id, start_time
                )
            else:
                return await self._handle_non_streaming_request(
                    request, request_data, request_id, start_time
                )
        except httpx.RequestError as e:
            duration = time.time() - start_time
            await request_logger.log_request_response(
                request=request,
                response=None,
                request_body=request_data,
                response_body={"error": f"Request error: {str(e)}"},
                duration=duration,
                request_id=request_id
            )
            raise HTTPException(
                status_code=502,
                detail=f"Could not connect to the upstream service: {str(e)}"
            )
    
    async def _handle_non_streaming_request(
        self,
        request: Request,
        request_data: Dict[str, Any],
        request_id: str,
        start_time: float
    ):
        """Handle a non-streaming request."""
        result = await self._forward_non_streaming(request, request_data)
        duration = time.time() - start_time
        
        # Check if it is an error response
        if isinstance(result, tuple):
            error_data, status_code = result
            response = JSONResponse(content=error_data, status_code=status_code)
            
            await request_logger.log_request_response(
                request=request,
                response=response,
                request_body=request_data,
                response_body=error_data,
                duration=duration,
                request_id=request_id
            )
            
            return response
        else:
            # Normal response
            response_data = result
            response = JSONResponse(content=response_data)
            
            await request_logger.log_request_response(
                request=request,
                response=response,
                request_body=request_data,
                response_body=response_data,
                duration=duration,
                request_id=request_id
            )
            
            return response
    
    def _parse_streaming_response(self, raw_chunks: List[str]) -> Dict[str, Any]:
        """Parse the streaming response to extract the final result."""
        content_parts = []
        reasoning_parts = []
        final_data = None
        
        for chunk in raw_chunks:
            lines = chunk.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove the 'data: ' prefix
                    if data_str == '[DONE]':
                        continue
                    try:
                        data = json.loads(data_str)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta and delta['content']:
                                content_parts.append(delta['content'])
                            if 'reasoning_content' in delta and delta['reasoning_content']:
                                reasoning_parts.append(delta['reasoning_content'])
                            final_data = data  # Save the last valid data structure
                    except json.JSONDecodeError:
                        continue
        
        # Construct the final response
        final_response = {
            "id": final_data.get('id', '') if final_data else '',
            "object": "chat.completion",
            "created": final_data.get('created', 0) if final_data else 0,
            "model": final_data.get('model', '') if final_data else '',
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "".join(content_parts)
                },
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": len(content_parts), "total_tokens": len(content_parts)}
        }
        
        # If there is reasoning content, add it to the response
        if reasoning_parts:
            final_response["reasoning_content"] = "".join(reasoning_parts)
        
        return final_response

    async def _handle_streaming_request(
        self,
        request: Request,
        request_data: Dict[str, Any],
        request_id: str,
        start_time: float
    ):
        """Handle a streaming request."""
        chunks_count = 0
        collected_chunks = []  # Used only for logging
        
        async def stream_generator():
            nonlocal chunks_count, collected_chunks
            try:
                async for chunk in self._forward_streaming(request, request_data):
                    # Check for an error response
                    if isinstance(chunk, dict) and chunk.get("error"):
                        error_data = chunk["data"]
                        error_chunk = _create_sse_error_chunk(error_data)
                        yield error_chunk
                        # Log the error
                        await request_logger.log_streaming_request(
                            request=request,
                            request_body=request_data,
                            status_code=chunk["status_code"],
                            chunks_count=0,
                            final_response=error_data,
                            duration=time.time() - start_time,
                            request_id=request_id
                        )
                        return
                    
                    chunks_count += 1
                    # Collect chunks only when needed for logging, forward immediately
                    if chunks_count <= 1000:  # Limit collection to avoid memory issues
                        collected_chunks.append(chunk)
                    yield chunk
            except Exception as e:
                error_data = {
                    "error": {
                        "message": str(e),
                        "type": "streaming_error",
                        "code": "STREAM_ERROR"
                    }
                }
                error_chunk = _create_sse_error_chunk(error_data)
                yield error_chunk
            finally:
                duration = time.time() - start_time
                # Parse the streaming response to get the final result (for logging)
                final_response = self._parse_streaming_response(collected_chunks)
                await request_logger.log_streaming_request(
                    request=request,
                    request_body=request_data,
                    status_code=200,
                    chunks_count=chunks_count,
                    final_response=final_response,
                    duration=duration,
                    request_id=request_id
                )
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id
            }
        )
    
    async def forward_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """Forward a streaming request (including workflow streaming output)."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 1. Extract original messages
        original_messages = [msg.model_dump() for msg in chat_request.messages]
        
        chunks_count = 0
        collected_chunks = []
        
        # Initialize request_data early so it can be accessed in the finally block
        request_data = chat_request.model_dump(exclude_none=True)
        # Pre-fill with original messages to log the original request if subsequent steps fail
        request_data["messages"] = original_messages
        
        async def workflow_streaming_generator():
            nonlocal chunks_count, collected_chunks, request_data
            
            try:
                # 2. Check if the workflow is enabled
                if settings.workflow.enabled:
                    # Workflow enabled: execute workflow
                    workflow_events = scenario_manager.update_scenario_streaming(original_messages)
                    
                    if settings.workflow.stream_output:
                        # Push workflow details to frontend
                        from utils.stream_converter import WorkflowStreamConverter
                        converter = WorkflowStreamConverter(request_id)
                        
                        async for sse_chunk in converter.convert_workflow_events(workflow_events):
                            yield sse_chunk
                    else:
                        # Execute workflow silently without pushing details
                        async for event in workflow_events:
                            pass  # Consume events but don't output
                    
                    # 3. After the workflow completes, read the updated scenario content
                    from utils.scenario_utils import read_scenario
                    current_scenario = await read_scenario()
                    
                    # 4. Inject the scenario into the messages
                    injected_messages = inject_scenario(original_messages, current_scenario)
                else:
                    # Workflow disabled: use the original messages directly
                    injected_messages = original_messages
                
                # 5. Update messages in request_data
                request_data["messages"] = injected_messages
                
                # 6. Stream the LLM response
                async for llm_chunk in self._forward_streaming(request, request_data):
                    # Check for an error response
                    if isinstance(llm_chunk, dict) and llm_chunk.get("error"):
                        error_data = llm_chunk["data"]
                        error_chunk = _create_sse_error_chunk(error_data)
                        yield error_chunk
                        # Log the error
                        await request_logger.log_streaming_request(
                            request=request,
                            request_body=request_data,
                            status_code=llm_chunk["status_code"],
                            chunks_count=chunks_count,
                            final_response=error_data,
                            duration=time.time() - start_time,
                            request_id=request_id
                        )
                        return
                    
                    chunks_count += 1
                    # Collect chunks only when needed for logging, forward immediately
                    if chunks_count <= 1000:  # Limit collection to avoid memory issues
                        collected_chunks.append(llm_chunk)
                    yield llm_chunk
                    
            except Exception as e:
                # Differentiate between workflow errors and LLM forwarding errors
                error_message = f"Workflow execution failed: {str(e)}" if "workflow" in str(e).lower() else f"LLM service error: {str(e)}"
                error_data = {
                    "error": {
                        "message": error_message,
                        "type": "workflow_streaming_error",
                        "code": "WORKFLOW_ERROR"
                    }
                }
                error_chunk = _create_sse_error_chunk(error_data)
                yield error_chunk
            finally:
                duration = time.time() - start_time
                # Parse the streaming response to get the final result (for logging)
                final_response = self._parse_streaming_response(collected_chunks)
                
                # Log using the updated request_data
                await request_logger.log_streaming_request(
                    request=request,
                    request_body=request_data,
                    status_code=200,
                    chunks_count=chunks_count,
                    final_response=final_response,
                    duration=duration,
                    request_id=request_id
                )
        
        return StreamingResponse(
            workflow_streaming_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
                "X-Workflow-Streaming": "true"
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