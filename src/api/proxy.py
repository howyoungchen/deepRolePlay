import json
import time
import uuid
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union

from config.manager import settings
from .proxy_utils import (
    ResponseBuilder, 
    AuthUtils, 
    StreamingHandler, 
    WorkflowHelper, 
    LoggingUtils, 
    DirectoryUtils,
    SpecialRequestHandler
)


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
        error_data = response.json()
        return error_data
    except (json.JSONDecodeError, ValueError):
        return ResponseBuilder.create_error_response(
            error_message=response.text or f"HTTP {response.status_code} Error",
            error_type="upstream_error",
            error_code=str(response.status_code)
        )




class ProxyService:
    def __init__(self):
        self.target_url = f"{settings.proxy.target_url.rstrip('/')}/chat/completions"
        self.models_url = settings.proxy.get_models_url()
        self.timeout = settings.proxy.timeout
    
    
    async def forward_non_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """完全基于工作流的非流式请求处理"""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        from src.workflow.graph.scenario_workflow import create_scenario_workflow
        from utils.format_converter import convert_final_response
        
        workflow = create_scenario_workflow()
        
        try:
            workflow_input = WorkflowHelper.prepare_workflow_input(
                request, chat_request, request_id, current_scenario=""
            )
            workflow_input["stream"] = False
            
            result = await workflow.ainvoke(workflow_input)
            llm_response = result.get("llm_response")
            
            # 确保llm_response不是协程对象
            if hasattr(llm_response, '__await__'):
                llm_response = await llm_response
            
            response_data = convert_final_response(llm_response, chat_request.model, stream=False)
            
            duration = time.time() - start_time
            
            response = JSONResponse(content=response_data)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            error_data = ResponseBuilder.create_error_response(
                error_message=str(e),
                error_type="workflow_error",
                error_code="WORKFLOW_ERROR"
            )
            
            response = JSONResponse(content=error_data, status_code=500)
            
            return response
    
    

    
    def forward_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """完全基于工作流的流式请求处理（新版）"""
        request_id = str(uuid.uuid4())
        
        from src.workflow.graph.scenario_workflow import create_scenario_workflow
        from utils.format_converter import convert_chunk_to_sse, create_done_message, convert_chunk_to_sse_manual
        
        workflow = create_scenario_workflow()
        
        async def stream_generator():
            """生成器，用于处理工作流并流式传输LLM响应"""
            try:
                # 1. 准备并调用工作流
                workflow_input = WorkflowHelper.prepare_workflow_input(
                    request, chat_request, request_id, current_scenario=""
                )
                workflow_input["stream"] = True
                
                # 使用ainvoke获取最终结果，其中包含流对象
                result = await workflow.ainvoke(workflow_input)
                
                # 2. 从结果中提取流
                llm_stream = result.get("llm_response")
                
                if not llm_stream or not hasattr(llm_stream, '__aiter__'):
                    raise ValueError("Workflow did not return a valid stream object.")
                
                # 3. 迭代流并转换为SSE，同时处理<think>标签
                is_thinking = False
                async for chunk in llm_stream:
                    # 检查是否开始思考
                    if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                        if not is_thinking:
                            is_thinking = True
                            yield convert_chunk_to_sse_manual("<think>\n", chat_request.model, request_id)
                    
                    # 检查是否结束思考
                    if is_thinking and hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                        is_thinking = False
                        yield convert_chunk_to_sse_manual("\n</think>\n", chat_request.model, request_id)

                    sse_chunk = convert_chunk_to_sse(chunk, chat_request.model, request_id)
                    if sse_chunk:
                        yield sse_chunk
                
                # 确保think标签闭合
                if is_thinking:
                    yield convert_chunk_to_sse_manual("\n</think>\n", chat_request.model, request_id)
                
                # 4. 发送结束信号
                yield create_done_message()

            except Exception as e:
                import traceback
                print(f"Error during streaming: {traceback.format_exc()}")
                error_data = ResponseBuilder.create_error_response(
                    error_message=str(e),
                    error_type="workflow_error",
                    error_code="WORKFLOW_STREAM_ERROR"
                )
                error_chunk = f"data: {json.dumps(error_data)}\n\n"
                yield error_chunk
                yield create_done_message()

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    
    async def forward_models_request(self, request: Request):
        """Forward a models query request to the target LLM service."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.models_url,
                    headers=AuthUtils.get_request_headers(request)
                )
                
                duration = time.time() - start_time
                
                if response.status_code >= 400:
                    error_data = _parse_upstream_error(response)
                    json_response = JSONResponse(content=error_data, status_code=response.status_code)
                else:
                    response_data = response.json()
                    json_response = JSONResponse(content=response_data)
                    error_data = response_data
                
                await LoggingUtils.log_response(
                    request=request,
                    response=json_response,
                    request_body={},
                    response_body=error_data,
                    duration=duration,
                    request_id=request_id
                )
                
                return json_response
                    
        except httpx.RequestError as e:
            duration = time.time() - start_time
            error_data = {"error": f"Request error: {str(e)}"}
            
            await LoggingUtils.log_response(
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
    
    try:
        if settings.proxy.debug_mode:
            response = await SpecialRequestHandler.handle_special_request(request, chat_request, "debug")
        elif WorkflowHelper.check_new_conversation_trigger(chat_request.messages):
            response = await SpecialRequestHandler.handle_special_request(request, chat_request, "new_conversation")
        elif chat_request.stream:
            response = proxy_service.forward_streaming_request(request, chat_request)
        else:
            response = await proxy_service.forward_non_streaming_request(request, chat_request)
        
        return response
        
    except Exception as e:
        # 如果任何步骤失败，返回一个标准的错误响应
        print(f"💀 CRITICAL ERROR in chat_completions: {e}")
        error_data = ResponseBuilder.create_error_response(
            error_message=f"An unexpected error occurred: {str(e)}",
            error_type="internal_server_error",
            error_code="UNEXPECTED_ERROR"
        )
        return JSONResponse(content=error_data, status_code=500)


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@router.get("/v1/models")
async def list_models(request: Request):
    """OpenAI-compatible model listing endpoint."""
    return await proxy_service.forward_models_request(request)