"""
代理服务的统一工具类集合
包含认证、响应构建、流式处理、工作流辅助、日志记录和目录操作等功能
"""
import json
import time
import uuid
import base64
import os
import glob
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from fastapi import Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from config.manager import settings


class AuthUtils:
    """API密钥和认证工具类"""
    
    @staticmethod
    def extract_api_key(request: Request) -> str:
        """从请求中提取API密钥，优先使用请求头，否则使用配置文件"""
        auth_header = request.headers.get("Authorization", "")
        api_key = ""
        
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        
        if not api_key:
            api_key = settings.proxy.api_key
        
        return api_key
    
    @staticmethod
    def get_request_headers(request: Request) -> dict:
        """获取转发请求所需的头部信息"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DeepRolePlay-Proxy/1.0"
        }
        
        auth_header = request.headers.get("authorization")
        if auth_header:
            headers["Authorization"] = auth_header
        
        return headers


class ResponseBuilder:
    """统一的OpenAI兼容响应构建器"""
    
    @staticmethod
    def create_chat_completion_response(
        request_id: str,
        model: str,
        content: str,
        stream: bool = False,
        finish_reason: str = "stop",
        usage_tokens: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """创建聊天完成响应"""
        base_response = {
            "id": f"chatcmpl-{request_id}",
            "created": int(time.time()),
            "model": model,
        }
        
        if stream:
            base_response.update({
                "object": "chat.completion.chunk",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": finish_reason
                }]
            })
        else:
            base_response.update({
                "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": finish_reason
                }],
                "usage": usage_tokens or {
                    "prompt_tokens": 10,
                    "completion_tokens": len(content),
                    "total_tokens": 10 + len(content)
                }
            })
        
        return base_response
    
    @staticmethod
    def create_special_response(response_type: str, request_id: str, model: str, stream: bool = False) -> Dict[str, Any]:
        """创建特殊响应（调试模式、新对话等）"""
        if response_type == "debug":
            try:
                with open("/home/chiye/worklab/deepRolePlay/pics/generate.png", "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode('utf-8')
                    content = (f'Testing two images display:\n\n图片1:\n'
                              f'<img src="data:image/png;base64,{img_data}" alt="Wizard 1" style="max-width: 300px;">'
                              f'<img src="data:image/png;base64,{img_data}" alt="Wizard 2" style="max-width: 300px;">')
            except FileNotFoundError:
                content = "🧙‍♂️ Wizard image not found, but the magic continues!"
        elif response_type == "new_conversation":
            content = "A new conversation has been successfully started."
        else:
            content = f"Special response: {response_type}"
        
        return ResponseBuilder.create_chat_completion_response(
            request_id=request_id,
            model=model,
            content=content,
            stream=stream
        )
    
    @staticmethod
    def create_error_response(
        error_message: str,
        error_type: str = "server_error",
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500
    ) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "error": {
                "message": error_message,
                "type": error_type,
                "code": error_code
            }
        }


class StreamingHandler:
    """统一的流式响应处理器"""
    
    @staticmethod
    async def create_simple_streaming_response(
        request: Request,
        response_data: Dict[str, Any],
        request_id: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        log_data: Optional[Dict[str, Any]] = None
    ) -> StreamingResponse:
        """创建简单的流式响应（用于调试模式和新对话）"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        async def stream_generator():
            yield f"data: {json.dumps(response_data)}\n\n"
            yield "data: [DONE]\n\n"
        
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id
        }
        
        if extra_headers:
            headers.update(extra_headers)
        
        response = StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers=headers
        )
        
        # 记录日志
        if log_data:
            LoggingUtils.log_response(
                request=request,
                response=response,
                request_body=log_data.get("request_body", {}),
                response_body=log_data.get("response_body", {}),
                duration=log_data.get("duration", 0.001),
                request_id=request_id
            )
        
        return response
    
    @staticmethod
    def create_workflow_streaming_response(
        request: Request,
        workflow_generator: Callable,
        request_id: Optional[str] = None
    ) -> StreamingResponse:
        """创建工作流的流式响应"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        return StreamingResponse(
            workflow_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id
            }
        )


class WorkflowHelper:
    """工作流相关的辅助工具类"""
    
    @staticmethod
    def prepare_workflow_input(
        request,
        chat_request,
        request_id: str = None,
        current_scenario: str = ""
    ) -> Dict[str, Any]:
        """准备工作流输入数据"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        api_key = AuthUtils.extract_api_key(request)
        
        return {
            "request_id": request_id,
            "original_messages": [msg.model_dump() for msg in chat_request.messages],
            "messages": [msg.model_dump() for msg in chat_request.messages],
            "current_scenario": current_scenario,
            "api_key": api_key,
            "model": chat_request.model,
            "stream": chat_request.stream
        }
    
    @staticmethod
    def check_new_conversation_trigger(messages: List) -> bool:
        """检查是否触发新对话（检查最后两条用户消息中是否包含'deeproleplay'）"""
        user_messages = [msg for msg in messages if msg.role == "user"]
        
        # 获取最后两条用户消息
        last_two_user_messages = user_messages[-2:] if len(user_messages) >= 2 else user_messages
        
        # 检查'deeproleplay'关键字（不区分大小写）
        for msg in last_two_user_messages:
            if "deeproleplay" in msg.content.lower():
                return True
        
        return False


class LoggingUtils:
    """日志记录工具类"""
    
    @staticmethod
    def log_response(
        request: Request,
        response: Optional[Response],
        request_body: Dict[str, Any],
        response_body: Dict[str, Any],
        duration: float,
        request_id: str
    ):
        """记录请求响应日志"""
        pass


class DirectoryUtils:
    """目录操作工具类"""
    
    @staticmethod
    def clear_scenarios_directory() -> bool:
        """清空scenarios目录中的所有文件"""
        try:
            scenarios_path = os.path.join(os.getcwd(), "scenarios")
            if os.path.exists(scenarios_path):
                files = glob.glob(os.path.join(scenarios_path, "*"))
                for file_path in files:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            return True
        except Exception as e:
            print(f"Failed to clear scenarios directory: {e}")
            return False


class SpecialRequestHandler:
    """统一的特殊请求处理器"""
    
    @staticmethod
    async def handle_special_request(
        request: Request,
        chat_request,
        request_type: str
    ):
        """统一处理特殊请求（调试模式、新对话等）"""
        request_id = str(uuid.uuid4())
        
        # 特殊操作
        if request_type == "new_conversation":
            DirectoryUtils.clear_scenarios_directory()
        
        # 创建响应
        response_data = ResponseBuilder.create_special_response(
            request_type, request_id, chat_request.model, chat_request.stream
        )
        
        # 准备头部信息和日志数据
        extra_headers = {f"X-{request_type.replace('_', '-').title()}": "true"}
        log_data = {
            "request_body": {
                "trigger" if request_type == "new_conversation" else f"{request_type}_mode": True,
                "model": chat_request.model
            },
            "response_body": {
                "message": "New conversation started" if request_type == "new_conversation" else f"{request_type} message",
                f"{request_type}": True,
                "stream": chat_request.stream
            }
        }
        
        if request_type == "new_conversation":
            log_data["response_body"]["scenarios_cleared"] = True
        
        if chat_request.stream:
            return await StreamingHandler.create_simple_streaming_response(
                request=request,
                response_data=response_data,
                request_id=request_id,
                extra_headers=extra_headers,
                log_data=log_data
            )
        else:
            response = JSONResponse(
                content=response_data,
                status_code=200,
                headers={**extra_headers, "X-Request-ID": request_id}
            )
            
            # 记录日志
            LoggingUtils.log_response(
                request=request,
                response=response,
                request_body=log_data["request_body"],
                response_body=log_data["response_body"],
                duration=0.001,
                request_id=request_id
            )
            
            return response