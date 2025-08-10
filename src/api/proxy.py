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
    SpecialRequestHandler,
    BackendModeManager,
    BackendCommandHandler
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
        """使用ScenarioManager的非流式请求处理"""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        from src.scenario.manager import scenario_manager
        from utils.format_converter import convert_final_response
        
        try:
            workflow_input = WorkflowHelper.prepare_workflow_input(
                request, chat_request, request_id, current_scenario=""
            )
            workflow_input["stream"] = False
            
            # 1. 先更新场景
            await scenario_manager.update_scenario(workflow_input)
            
            # 2. 调用独立的非流式LLM转发函数
            from src.workflow.graph.forward_workflow import forward_to_llm_non_streaming
            
            llm_response = await forward_to_llm_non_streaming(
                original_messages=workflow_input["original_messages"],
                api_key=workflow_input["api_key"],
                model=chat_request.model
            )
            
            # 3. 转换为OpenAI格式响应
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
        """使用ScenarioManager的流式请求处理"""
        request_id = str(uuid.uuid4())
        
        from src.scenario.manager import scenario_manager
        from utils.format_converter import convert_chunk_to_sse, convert_workflow_event_to_sse, convert_chunk_to_sse_manual, create_done_message
        
        async def stream_generator():
            """生成器，用于处理工作流并流式传输LLM响应"""
            try:
                # 1. 准备工作流输入
                workflow_input = WorkflowHelper.prepare_workflow_input(
                    request, chat_request, request_id, current_scenario=""
                )
                workflow_input["stream"] = True
                
                # 2. 智能体推理开始标记
                if settings.langgraph.stream_workflow_to_frontend:
                    agent_start_chunk = convert_chunk_to_sse_manual("<deepRolePlay>\n", chat_request.model, request_id)
                    yield agent_start_chunk
                
                # 3. 使用ScenarioManager的流式方法
                async for event in scenario_manager.update_scenario_streaming(workflow_input):
                    # 使用综合的工作流事件转换函数，支持多种事件类型
                    if settings.langgraph.stream_workflow_to_frontend:
                        sse_chunk = convert_workflow_event_to_sse(event, chat_request.model, request_id)
                        if sse_chunk:
                            yield sse_chunk
                
                # 4. 智能体推理结束标记
                if settings.langgraph.stream_workflow_to_frontend:
                    agent_end_chunk = convert_chunk_to_sse_manual("\n</deepRolePlay>", chat_request.model, request_id)
                    yield agent_end_chunk
                
                # 5. 调用独立的LLM转发函数进行流式输出
                from src.workflow.graph.forward_workflow import forward_to_llm_streaming
                
                async for chunk in forward_to_llm_streaming(
                    original_messages=workflow_input["original_messages"],
                    api_key=workflow_input["api_key"], 
                    model=chat_request.model
                ):
                    sse_chunk = convert_chunk_to_sse(chunk, chat_request.model, request_id)
                    if sse_chunk:
                        yield sse_chunk
                
                # 6. 发送结束信号
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
        # 保存完整的请求messages（如果配置启用）
        request_id = str(uuid.uuid4())
        messages_data = [msg.model_dump() for msg in chat_request.messages]
        await LoggingUtils.save_full_messages(messages_data, request_id)
        # 优先检查是否已在后台模式中处理命令
        if BackendModeManager.is_in_backend_mode():
            print(f"🎯 Already in backend mode")
            command = BackendCommandHandler.parse_command_from_messages(chat_request.messages, 1)  # 只解析当前消息
            print(f"🔍 Parsed command: {command}")
            if command:
                response = await BackendCommandHandler.handle_backend_command(request, chat_request, command)
            else:
                response = await BackendCommandHandler.handle_backend_command(request, chat_request, "unknown")
        # 检查是否触发DRP后台模式（只在未进入后台模式时检查）
        elif WorkflowHelper.check_drp_trigger(chat_request.messages):
            print(f"🔄 Triggering DRP backend mode")
            BackendModeManager.enter_backend_mode()
            # 首次触发DRP模式时，直接显示欢迎信息，不解析历史命令避免误触发
            print(f"🔍 First time entering backend mode, showing welcome message")
            response = await BackendCommandHandler.handle_backend_command(request, chat_request, "welcome")
        # 调试模式
        elif settings.proxy.debug_mode:
            response = await SpecialRequestHandler.handle_special_request(request, chat_request, "debug")
        # 正常流式/非流式请求处理
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