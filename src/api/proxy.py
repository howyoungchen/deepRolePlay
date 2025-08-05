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
from utils.serialization_helper import make_response_serializable


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
            
            await LoggingUtils.log_workflow_request(
                request, response, chat_request, response_data, duration, request_id
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            error_data = ResponseBuilder.create_error_response(
                error_message=str(e),
                error_type="workflow_error",
                error_code="WORKFLOW_ERROR"
            )
            
            response = JSONResponse(content=error_data, status_code=500)
            
            await LoggingUtils.log_workflow_request(
                request, response, chat_request, error_data, duration, request_id
            )
            
            return response
    
    

    
    def forward_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """完全基于工作流的流式请求处理"""
        request_id = str(uuid.uuid4())
        
        from src.workflow.graph.scenario_workflow import create_scenario_workflow
        from utils.format_converter import create_done_message
        
        workflow = create_scenario_workflow()
        
        async def convert_to_sse():
            """将工作流事件转换为SSE格式"""
            try:
                workflow_input = WorkflowHelper.prepare_workflow_input(
                    request, chat_request, request_id, current_scenario=""
                )
                
                from utils.event_formatter import EventFormatter
                formatter = EventFormatter(chat_request.model)
                
                async for event in workflow.astream_events(workflow_input, version="v2"):
                    sse_chunk = formatter.format_event_to_sse(event)
                    if sse_chunk:
                        yield sse_chunk
                
                yield create_done_message()
                
            except Exception as e:
                error_data = ResponseBuilder.create_error_response(
                    error_message=str(e),
                    error_type="workflow_error",
                    error_code="WORKFLOW_ERROR"
                )
                error_chunk = f"data: {json.dumps(error_data)}\n\n"
                yield error_chunk
                yield create_done_message()
        
        return StreamingHandler.create_workflow_streaming_response(
            request, convert_to_sse, request_id
        )
    
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