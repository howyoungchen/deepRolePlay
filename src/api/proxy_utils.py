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
                    content = (f'Testing two images display:\n\nImage 1:\n'
                              f'<img src="data:image/png;base64,{img_data}" alt="Wizard 1" style="max-width: 300px;">'
                              f'<img src="data:image/png;base64,{img_data}" alt="Wizard 2" style="max-width: 300px;">')
            except FileNotFoundError:
                content = "🧙‍♂️ Wizard image not found, but the magic continues!"
        elif response_type == "backend_command":
            content = "Backend command executed."
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
            await LoggingUtils.log_response(
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
    def check_drp_trigger(messages: List) -> bool:
        """检查是否触发DRP后台模式（检查最新消息是否包含'$DRP'或'DRP'）"""
        if not messages:
            return False
        
        # 从后往前查找最近的两条用户消息
        recent_user_messages = []
        for message in reversed(messages):
            if hasattr(message, 'role') and message.role == "user":
                recent_user_messages.append(message)
                if len(recent_user_messages) >= 2:
                    break
        
        if not recent_user_messages:
            return False
        
        # 检查这两条用户消息中是否有任何一条包含$DRP或DRP
        import re
        for user_message in recent_user_messages:
            content = user_message.content.upper() if hasattr(user_message, 'content') else ""
            # 优先检查$DRP格式
            if re.search(r'\$DRP\b', content) or "$DRP" in content:
                return True
            # 向后兼容：检查原始DRP格式
            if "DRP" in content:
                return True
        
        return False

    @staticmethod
    def get_recent_user_messages_content(messages: List, count: int) -> List[str]:
        """从倒数count条用户消息中获取内容列表"""
        recent_user_messages = []
        for message in reversed(messages):
            if hasattr(message, 'role') and message.role == "user":
                recent_user_messages.append(message)
                if len(recent_user_messages) >= count:
                    break
        
        # 返回这些消息的content
        contents = []
        for msg in recent_user_messages:
            content = msg.content if hasattr(msg, 'content') else ""
            contents.append(content)
        return contents



class LoggingUtils:
    """日志记录工具类"""
    
    @staticmethod
    async def log_response(
        request: Request,
        response: Optional[Response],
        request_body: Dict[str, Any],
        response_body: Dict[str, Any],
        duration: float,
        request_id: str
    ):
        """记录请求响应日志"""
        pass
    
    @staticmethod
    async def save_full_messages(messages: List[Dict[str, Any]], request_id: str):
        """保存完整的请求messages"""
        if not settings.proxy.save_full_messages:
            return
        
        import json
        import os
        from datetime import datetime
        from pathlib import Path
        
        try:
            # 创建logs/full_messages目录
            log_dir = Path("logs/full_messages")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名：使用时间戳和request_id
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{request_id[:8]}.json"
            log_path = log_dir / filename
            
            # 保存数据
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id,
                "messages": messages
            }
            
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
                
            print(f"📝 Full messages saved: {log_path}")
            
        except Exception as e:
            print(f"❌ Failed to save full messages: {e}")


class BackendModeManager:
    """后台模式状态管理器"""
    _backend_mode = False
    
    @classmethod
    def enter_backend_mode(cls):
        """进入后台模式"""
        cls._backend_mode = True
    
    @classmethod
    def exit_backend_mode(cls):
        """退出后台模式"""
        cls._backend_mode = False
    
    @classmethod
    def is_in_backend_mode(cls) -> bool:
        """检查是否处于后台模式"""
        return cls._backend_mode


class BackendCommandHandler:
    """DRP后台命令处理器"""
    
    @staticmethod
    def parse_command(message_content: str) -> Optional[str]:
        """从消息中解析后台命令，仅支持$前缀格式"""
        if not message_content:
            return None
        content = message_content.strip().lower()
        
        # 精确匹配（仅支持$前缀的命令格式）
        if content == "$rm":
            return "rm"
        elif content == "$show":
            return "show"  
        elif content == "$exit":
            return "exit"
        elif content == "$drp":
            return "drp"
        
        # 如果精确匹配失败，尝试从复杂文本中提取命令（用于AI prompt包装的情况）
        import re
        # 查找带$前缀的命令词（支持中英文环境）
        if re.search(r'\$exit(?:\b|(?=[^a-zA-Z]))', content):
            return "exit"
        elif re.search(r'\$show(?:\b|(?=[^a-zA-Z]))', content):
            return "show"
        elif re.search(r'\$rm(?:\b|(?=[^a-zA-Z]))', content):
            return "rm"
        elif re.search(r'\$drp(?:\b|(?=[^a-zA-Z]))', content):
            return "drp"
        
        return None

    @staticmethod
    def parse_command_from_messages(messages: List, count: int = 2) -> Optional[str]:
        """从倒数count条用户消息中解析后台命令"""
        contents = WorkflowHelper.get_recent_user_messages_content(messages, count)
        
        # 检查每条消息内容中是否有命令
        for content in contents:
            command = BackendCommandHandler.parse_command(content)
            if command:
                return command
        return None
    
    @staticmethod
    async def handle_backend_command(request: Request, chat_request, command: str) -> Response:
        """处理后台命令并返回响应"""
        from src.workflow.tools.scenario_table_tools import scenario_manager
        from config.manager import settings
        
        request_id = str(uuid.uuid4())
        
        try:
            if command == "rm":
                # 清空表格数据
                scenario_manager.init(settings.scenario.file_path)
                table_reset = scenario_manager.reset()
                
                # 清空scenarios目录
                directory_clear = DirectoryUtils.clear_scenarios_directory()
                
                if table_reset and directory_clear:
                    message = "Memory tables and scenarios directory have been reset successfully."
                else:
                    message = "Reset operation completed with some warnings."
                    
            elif command == "show":
                # 显示表格数据
                scenario_manager.init(settings.scenario.file_path)
                tables_content = scenario_manager.get_all_pretty_tables(description=True, operation_guide=True)
                message = f"Current Memory Tables:\\n\\n{tables_content}"
                    
            elif command == "exit":
                # 退出后台模式
                BackendModeManager.exit_backend_mode()
                message = "Exited backend mode successfully."
            
            elif command == "drp":
                # 进入后台模式的确认信息
                BackendModeManager.enter_backend_mode()
                message = "Entered DeepRolePlay backend mode! Available commands:\n- $rm: Clear all memory tables and scenarios\n- $show: Display current memory tables\n- $exit: Exit backend mode"
            
            elif command == "welcome":
                # 首次进入DRP后台模式的欢迎信息
                message = "Welcome to DeepRolePlay backend mode! Available commands:\n- $rm: Clear all memory tables and scenarios\n- $show: Display current memory tables\n- $exit: Exit backend mode"
            
            else:
                message = "Unknown command. Available commands: $drp, $rm, $show, $exit"
            
            # 创建响应
            response_data = ResponseBuilder.create_special_response(
                "backend_command", request_id, chat_request.model, chat_request.stream
            )
            
            # 更新响应消息
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                if "message" in choice:
                    choice["message"]["content"] = message
                elif "delta" in choice:
                    choice["delta"]["content"] = message
            
            if chat_request.stream:
                return await StreamingHandler.create_simple_streaming_response(
                    request, response_data, request_id
                )
            else:
                return JSONResponse(content=response_data)
                
        except Exception as e:
            print(f"Backend command error: {e}")
            error_response = ResponseBuilder.create_error_response(
                error_message=f"Backend command failed: {str(e)}",
                error_type="backend_error"
            )
            return JSONResponse(content=error_response, status_code=500)


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
        
        # 特殊操作处理
        # 目前只支持debug模式，new_conversation已移至DRP后台模式
        
        # 创建响应
        response_data = ResponseBuilder.create_special_response(
            request_type, request_id, chat_request.model, chat_request.stream
        )
        
        # 准备头部信息和日志数据
        extra_headers = {f"X-{request_type.replace('_', '-').title()}": "true"}
        log_data = {
            "request_body": {
                f"{request_type}_mode": True,
                "model": chat_request.model
            },
            "response_body": {
                "message": f"{request_type} message",
                f"{request_type}": True,
                "stream": chat_request.stream
            }
        }
        
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
            await LoggingUtils.log_response(
                request=request,
                response=response,
                request_body=log_data["request_body"],
                response_body=log_data["response_body"],
                duration=0.001,
                request_id=request_id
            )
            
            return response