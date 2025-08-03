import json
import time
import uuid
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncGenerator

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


class ProxyService:
    def __init__(self):
        self.target_url = f"{settings.proxy.target_url.rstrip('/')}/chat/completions"
        self.api_key = settings.proxy.api_key
        self.timeout = settings.proxy.timeout
        
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "NarratorAI-Proxy/1.0"
        }
    
    async def _forward_non_streaming(
        self, 
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """转发非流式请求"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.target_url,
                headers=self._get_headers(),
                json=request_data
            )
            response.raise_for_status()
            return response.json()
    
    async def _forward_streaming(
        self, 
        request_data: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """转发流式请求"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self.target_url,
                headers=self._get_headers(),
                json=request_data
            ) as response:
                response.raise_for_status()
                
                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk
    
    async def forward_non_streaming_request(
        self,
        request: Request,
        chat_request: ChatCompletionRequest
    ):
        """转发非流式请求到目标LLM服务"""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 1. 提取原始消息
        original_messages = [msg.model_dump() for msg in chat_request.messages]
        
        # 2. 同步更新情景并获取最新内容
        await scenario_manager.update_scenario(original_messages)
        
        # 3.读取当前情景内容
        from utils.scenario_utils import read_scenario
        current_scenario = await read_scenario()
        
        # 4. 将情景注入到消息中
        injected_messages = inject_scenario(original_messages, current_scenario)
        
        # 5. 创建注入情景后的请求数据
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
        except httpx.HTTPStatusError as e:
            duration = time.time() - start_time
            await request_logger.log_request_response(
                request=request,
                response=None,
                request_body=request_data,
                response_body={"error": f"HTTP {e.response.status_code}: {e.response.text}"},
                duration=duration,
                request_id=request_id
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"上游服务错误: {e.response.text}"
            )
        except httpx.RequestError as e:
            duration = time.time() - start_time
            await request_logger.log_request_response(
                request=request,
                response=None,
                request_body=request_data,
                response_body={"error": f"请求错误: {str(e)}"},
                duration=duration,
                request_id=request_id
            )
            raise HTTPException(
                status_code=502,
                detail=f"无法连接到上游服务: {str(e)}"
            )
    
    async def _handle_non_streaming_request(
        self,
        request: Request,
        request_data: Dict[str, Any],
        request_id: str,
        start_time: float
    ):
        """处理非流式请求"""
        response_data = await self._forward_non_streaming(request_data)
        duration = time.time() - start_time
        
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
        """解析流式响应，提取最终结果"""
        content_parts = []
        reasoning_parts = []
        final_data = None
        
        for chunk in raw_chunks:
            lines = chunk.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    data_str = line[6:]  # 去掉 'data: ' 前缀
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
                            final_data = data  # 保存最后一个有效的数据结构
                    except json.JSONDecodeError:
                        continue
        
        # 构造最终响应
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
        
        # 如果有推理内容，添加到响应中
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
        """处理流式请求"""
        chunks_count = 0
        collected_chunks = []
        
        async def stream_generator():
            nonlocal chunks_count, collected_chunks
            try:
                async for chunk in self._forward_streaming(request_data):
                    chunks_count += 1
                    collected_chunks.append(chunk)
                    yield chunk
            finally:
                duration = time.time() - start_time
                # 解析流式响应得到最终结果
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
        """转发流式请求（包含工作流流式输出）"""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 1. 提取原始消息
        original_messages = [msg.model_dump() for msg in chat_request.messages]
        
        chunks_count = 0
        collected_chunks = []
        
        # 将 request_data 初始化提前，以便在 finally 中访问
        request_data = chat_request.model_dump(exclude_none=True)
        # 先用原始消息填充，如果后续步骤失败，也能记录原始请求
        request_data["messages"] = original_messages
        
        async def workflow_streaming_generator():
            nonlocal chunks_count, collected_chunks, request_data
            
            try:
                # 2. 先流式输出工作流事件
                from utils.stream_converter import WorkflowStreamConverter
                converter = WorkflowStreamConverter(request_id)
                
                workflow_events = scenario_manager.update_scenario_streaming(original_messages)
                
                async for sse_chunk in converter.convert_workflow_events(workflow_events):
                    yield sse_chunk
                
                # 3. 工作流完成后，读取更新的情景内容
                from utils.scenario_utils import read_scenario
                current_scenario = await read_scenario()
                
                # 4. 将情景注入到消息中
                injected_messages = inject_scenario(original_messages, current_scenario)
                
                # 5. 更新 request_data 中的 messages
                request_data["messages"] = injected_messages
                
                # 6. 流式输出LLM响应
                async for llm_chunk in self._forward_streaming(request_data):
                    chunks_count += 1
                    collected_chunks.append(llm_chunk)
                    yield llm_chunk
                    
            except Exception as e:
                error_chunk = f"data: {{\"error\": \"工作流执行失败: {str(e)}\"}}\n\n"
                yield error_chunk
            finally:
                duration = time.time() - start_time
                # 解析流式响应得到最终结果
                final_response = self._parse_streaming_response(collected_chunks)
                
                # 使用更新后的 request_data 记录日志
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


proxy_service = ProxyService()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, chat_request: ChatCompletionRequest):
    """OpenAI兼容的聊天完成接口"""
    if chat_request.stream:
        # 流式请求：包含工作流流式输出
        return await proxy_service.forward_streaming_request(request, chat_request)
    else:
        # 非流式请求：传统的同步工作流处理
        return await proxy_service.forward_non_streaming_request(request, chat_request)


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "version": "1.0.0"}