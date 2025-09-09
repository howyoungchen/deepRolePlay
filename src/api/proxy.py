import json
import time
import uuid
import httpx
import asyncio
from pathlib import Path
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
    
    class Config:
        extra = "allow"  # 允许额外字段，如 thinking 等扩展参数


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
        self.message_cache = []  # 用于情景清理策略的消息缓存
    
    
    async def forward_non_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """使用ScenarioManager的非流式请求处理"""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 处理情景清理策略
        cleared, self.message_cache = WorkflowHelper.handle_scenario_clear_strategy(
            chat_request.messages, self.message_cache
        )
        
        from src.scenario.manager import scenario_manager
        from utils.format_converter import convert_final_response
        
        try:
            workflow_input = WorkflowHelper.prepare_workflow_input(
                request, chat_request, request_id, current_scenario=""
            )
            workflow_input["stream"] = False
            
            # 1. 先更新场景
            await scenario_manager.update_scenario(workflow_input)
            
            # 2. 图片生成处理（如果启用）
            image_generation_task = None
            if settings.comfyui.enabled:
                print(f"🖼️ Starting image generation workflow for non-streaming...", flush=True)
                from src.workflow.graph.image_generation_workflow import create_image_generation_workflow
                
                # 创建并启动图片生成工作流（异步后台任务）
                workflow = create_image_generation_workflow()
                image_generation_task = asyncio.create_task(workflow.ainvoke({}))
                print(f"🖼️ Image generation task created for non-streaming", flush=True)
            
            # 3. 调用独立的非流式LLM转发函数
            from src.workflow.graph.forward_workflow import forward_to_llm_non_streaming
            
            llm_response = await forward_to_llm_non_streaming(
                original_messages=workflow_input["original_messages"],
                api_key=workflow_input["api_key"],
                chat_request=chat_request
            )
            
            # 4. 等待图片生成完成并合并响应内容
            response_content = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            
            if image_generation_task:
                print(f"🖼️ Waiting for image generation to complete for non-streaming...", flush=True)
                try:
                    # 等待图片生成完成（设置超时）
                    result = await asyncio.wait_for(image_generation_task, timeout=120)
                    image_paths = result.get('generated_image_paths', [])
                    print(f"🖼️ Image generation completed for non-streaming. Paths: {image_paths}", flush=True)
                    
                    # 如果有生成的图片，添加到响应内容
                    if image_paths:
                        print(f"🖼️ Processing {len(image_paths)} generated images for non-streaming...", flush=True)
                        image_content_parts = []
                        
                        for i, image_path in enumerate(image_paths):
                            if image_path and not image_path.startswith("错误") and Path(image_path).exists():
                                try:
                                    print(f"🖼️ Processing image {i+1}: {image_path} for non-streaming", flush=True)
                                    # 使用图片优化器处理图片
                                    from utils.image_optimizer import optimize_and_format_image
                                    
                                    # 生成优化的Markdown格式图片
                                    image_markdown = optimize_and_format_image(
                                        image_path=image_path,
                                        alt_text=f"Generated Image {i+1}",
                                        collapsible=False
                                    )
                                    
                                    if image_markdown:
                                        image_content_parts.append(image_markdown)
                                        print(f"🖼️ Successfully processed image {i+1} for non-streaming", flush=True)
                                    
                                except Exception as img_error:
                                    print(f"🖼️ Error reading image {i+1} for non-streaming: {str(img_error)}", flush=True)
                                    image_content_parts.append(f"[图片读取失败: {str(img_error)}]")
                            elif image_path and image_path.startswith("错误"):
                                # 显示生成失败的图片错误信息
                                print(f"🖼️ Image generation error for non-streaming: {image_path}", flush=True)
                                image_content_parts.append(f"[{image_path}]")
                        
                        # 将图片内容添加到响应中
                        if image_content_parts:
                            response_content += "\n\n" + "\n\n".join(image_content_parts)
                    else:
                        print(f"🖼️ No valid image paths found for non-streaming", flush=True)
                        
                except asyncio.TimeoutError:
                    print(f"🖼️ Image generation timeout for non-streaming!", flush=True)
                    response_content += "\n\n[图片生成超时]"
                except Exception as e:
                    print(f"🖼️ Image generation error for non-streaming: {str(e)}", flush=True)
                    response_content += f"\n\n[图片生成失败: {str(e)}]"
            else:
                print(f"🖼️ No image generation task for non-streaming (comfyui.enabled: {settings.comfyui.enabled})", flush=True)
            
            # 5. 转换为OpenAI格式响应（使用更新后的内容）
            response_data = convert_final_response(response_content, chat_request.model, stream=False)
            
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
        
        # 处理情景清理策略
        cleared, self.message_cache = WorkflowHelper.handle_scenario_clear_strategy(
            chat_request.messages, self.message_cache
        )
        
        from src.scenario.manager import scenario_manager
        from utils.format_converter import convert_chunk_to_sse, convert_workflow_event_to_sse, convert_chunk_to_sse_manual, create_done_message, create_reasoning_start_chunk, create_reasoning_end_chunk
        
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
                    agent_start_chunk = create_reasoning_start_chunk(chat_request.model, request_id)
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
                    agent_end_chunk = create_reasoning_end_chunk(chat_request.model, request_id)
                    yield agent_end_chunk
                
                # 5. 图片生成处理（如果启用）
                image_generation_task = None
                if settings.comfyui.enabled:
                    print(f"🖼️ Starting image generation workflow...", flush=True)
                    from src.workflow.graph.image_generation_workflow import create_image_generation_workflow
                    
                    # 创建并启动图片生成工作流（异步后台任务）
                    workflow = create_image_generation_workflow()
                    image_generation_task = asyncio.create_task(workflow.ainvoke({}))
                    print(f"🖼️ Image generation task created", flush=True)
                
                # 6. 调用独立的LLM转发函数进行流式输出
                from src.workflow.graph.forward_workflow import forward_to_llm_streaming
                
                async for chunk in forward_to_llm_streaming(
                    original_messages=workflow_input["original_messages"],
                    api_key=workflow_input["api_key"], 
                    chat_request=chat_request
                ):
                    sse_chunk = convert_chunk_to_sse(chunk, chat_request.model, request_id)
                    if sse_chunk:
                        yield sse_chunk
                
                # # 测试用：构造模拟的 image_generation_task
                # async def mock_image_generation():
                #     """模拟图片生成任务，返回测试图片路径"""
                #     await asyncio.sleep(0.1)  # 模拟短暂延迟
                #     return {
                #         'generated_image_paths': ['logs/imgs/ComfyUI_00618_.png']
                #     }

                # # 创建模拟任务
                # image_generation_task = asyncio.create_task(mock_image_generation())
                # print(f"🖼️ Mock image generation task created for testing", flush=True)
                
                # 6.5 检查图片生成是否完成并发送图片
                if image_generation_task:
                    print(f"🖼️ Checking image generation task...", flush=True)
                    try:
                        # 等待图片生成完成（设置超时）
                        print(f"🖼️ Waiting for image generation to complete (timeout=120s)...", flush=True)
                        result = await asyncio.wait_for(image_generation_task, timeout=120)
                        image_paths = result.get('generated_image_paths', [])
                        print(f"🖼️ Image generation completed. Paths: {image_paths}", flush=True)
                        
                        # 如果有生成的图片，发送到前端
                        if image_paths:
                            print(f"🖼️ Processing {len(image_paths)} generated images...", flush=True)
                            for i, image_path in enumerate(image_paths):
                                if image_path and not image_path.startswith("错误") and Path(image_path).exists():
                                    try:
                                        print(f"🖼️ Processing image {i+1}: {image_path}", flush=True)
                                        # 使用图片优化器处理图片
                                        from utils.image_optimizer import optimize_and_format_image
                                        
                                        # 生成优化的Markdown格式图片（直接调整到512px尺寸）
                                        image_markdown = optimize_and_format_image(
                                            image_path=image_path,
                                            alt_text=f"Generated Image {i+1}",
                                            collapsible=False
                                        )
                                        
                                        # 创建包含优化图片的消息块（单个消息发送）
                                        image_chunk = convert_chunk_to_sse_manual(f"\n{image_markdown}\n", chat_request.model, request_id)
                                        print(f"🖼️ Sending optimized image {i+1} via SSE (Markdown format)...", flush=True)
                                        yield image_chunk
                                        
                                    except Exception as img_error:
                                        print(f"🖼️ Error reading image {i+1}: {str(img_error)}", flush=True)
                                        error_chunk = convert_chunk_to_sse_manual(f"\n[图片读取失败: {str(img_error)}]\n", chat_request.model, request_id)
                                        yield error_chunk
                                elif image_path and image_path.startswith("错误"):
                                    # 显示生成失败的图片错误信息
                                    print(f"🖼️ Image generation error: {image_path}", flush=True)
                                    error_chunk = convert_chunk_to_sse_manual(f"\n[{image_path}]\n", chat_request.model, request_id)
                                    yield error_chunk
                        else:
                            print(f"🖼️ No valid image paths found", flush=True)
                                    
                    except asyncio.TimeoutError:
                        # 如果超时，发送错误信息
                        print(f"🖼️ Image generation timeout!", flush=True)
                        error_chunk = convert_chunk_to_sse_manual("\n[图片生成超时]\n", chat_request.model, request_id)
                        yield error_chunk
                    except Exception as e:
                        # 其他错误
                        print(f"🖼️ Image generation error: {str(e)}", flush=True)
                        error_chunk = convert_chunk_to_sse_manual(f"\n[图片生成失败: {str(e)}]\n", chat_request.model, request_id)
                        yield error_chunk
                else:
                    print(f"🖼️ No image generation task (comfyui.enabled: {settings.comfyui.enabled})", flush=True)
                
                # 7. 发送结束信号
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
        # 保存完整的请求参数（如果配置启用）
        request_id = str(uuid.uuid4())
        await LoggingUtils.save_full_messages(chat_request, request_id)
        
        # 检查是否有后台命令需要处理
        command = BackendCommandHandler.parse_command_from_messages(chat_request.messages, 10)
        if command:
            print(f"🔍 Parsed command: {command}")
            response = await BackendCommandHandler.handle_backend_command(request, chat_request, command)
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