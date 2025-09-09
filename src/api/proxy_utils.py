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
import difflib


class AuthUtils:
    """API密钥和认证工具类"""
    
    @staticmethod
    def extract_api_key(request: Request) -> str:
        """从配置文件中提取API密钥"""
        return settings.proxy.api_key or ""
    
    @staticmethod
    def get_request_headers(request: Request) -> dict:
        """获取转发请求所需的头部信息"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DeepRolePlay-Proxy/1.0"
        }
        
        # 使用配置文件中的API密钥
        api_key = AuthUtils.extract_api_key(request)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
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
                    content = (f'images display:\n'
                              f'<img src="data:image/png;base64,{img_data}" alt="Wizard 1" style="max-width: 300px;">'
                    )
            except FileNotFoundError:
                content = "IMG ERROR"
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
            "stream": chat_request.stream,
            "chat_request": chat_request  # 添加完整的请求对象以支持所有参数转发
        }
    

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
    
    @staticmethod
    def calculate_message_similarity(msg1: str, msg2: str, threshold: float = 0.9) -> tuple[bool, float]:
        """
        计算两条消息的相似度
        
        Args:
            msg1: 第一条消息
            msg2: 第二条消息
            threshold: 相似度阈值，默认0.9（90%）
            
        Returns:
            tuple: (是否相似（True表示相似，False表示差异较大）, 实际相似度值)
        """
        if not msg1 and not msg2:
            return True, 1.0
            
        if not msg1 or not msg2:
            return False, 0.0
        
        # 使用difflib计算序列相似度
        similarity = difflib.SequenceMatcher(None, msg1, msg2).ratio()
        
        return similarity >= threshold, similarity
    
    @staticmethod
    def handle_scenario_clear_strategy(messages: List, message_cache: List[str] = None) -> tuple[bool, List[str]]:
        """
        根据配置的策略处理情景文件清理
        
        Args:
            messages: 当前请求的消息列表
            message_cache: 当前缓存的消息列表
            
        Returns:
            tuple: (是否执行了清理, 新的消息缓存)
        """
        from config.manager import settings
        
        strategy = settings.scenario.clear_strategy
        
        # manual 策略：跳过清理
        if strategy == "manual":
            return False, message_cache or []
        
        # always 策略：总是清理
        if strategy == "always":
            WorkflowHelper._clear_scenario_file()
            return True, []
        
        # auto 策略：智能判断（只对比第一条消息）
        if strategy == "auto":
            # 获取第一条消息的内容
            current_first_message = ""
            if messages:
                first_msg = messages[0]
                current_first_message = first_msg.get("content", "") if hasattr(first_msg, 'get') else getattr(first_msg, 'content', "")
            
            # 获取缓存的第一条消息
            cached_first_message = message_cache[0] if message_cache else ""
            
            # 使用配置的相似度阈值进行对比
            threshold = settings.scenario.similarity_threshold
            is_similar, similarity_score = WorkflowHelper.calculate_message_similarity(
                cached_first_message, current_first_message, threshold
            )
            
            # 如果缓存不存在或与当前第一条消息相似度不够，则清理并更新缓存
            if not message_cache or not is_similar:
                if message_cache:  # 只有存在缓存时才打印相似度信息
                    print(f"[消息缓存] 检测到新对话，相似度: {similarity_score:.3f} < {threshold:.1f}, 清理scenario文件")
                WorkflowHelper._clear_scenario_file()
                return True, [current_first_message]
            
            # 缓存相似，跳过清理
            return False, message_cache
        
        # 未知策略，默认不清理
        return False, message_cache or []
    
    @staticmethod
    def _clear_scenario_file():
        """清理单个情景文件"""
        from config.manager import settings
        import os
        
        scenario_file_path = settings.scenario.file_path
        
        try:
            if os.path.exists(scenario_file_path):
                os.remove(scenario_file_path)
                print(f"Scenario file cleared: {scenario_file_path}")
        except Exception as e:
            print(f"Failed to clear scenario file: {e}")



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
    async def save_full_messages(chat_request: Any, request_id: str):
        """保存完整的请求参数"""
        if not settings.log.save_request_origin_messages:
            return
        
        import json
        from datetime import datetime
        from pathlib import Path
        
        try:
            # 使用 model_dump() 获取所有请求参数
            request_data = chat_request.model_dump()
            
            # 创建按时间戳命名的会话日志目录
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            session_log_dir = Path(settings.log.get_session_log_path(timestamp))
            session_log_dir.mkdir(parents=True, exist_ok=True)
            
            # 构建完整的日志数据
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id,
                **request_data  # 展开所有请求参数
            }
            
            # 保存到文件
            filename = f"request_messages_{request_id[:8]}.json"
            log_path = session_log_dir / filename
            
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
                
            print(f"\\ Full request saved: {log_path}")
            
        except Exception as e:
            print(f"❌ Failed to save full request: {e}")




class BackendCommandHandler:
    """DRP后台命令处理器"""
    
    @staticmethod
    def parse_command_from_messages(messages: List, count: int = 10) -> Optional[str]:
        """从最近的消息中解析后台命令（倒序检查）"""
        if not messages:
            return None
        
        # 从后往前检查最多count条消息
        check_count = min(count, len(messages))
        
        # 倒序逐条检查
        for i in range(1, check_count + 1):
            message = messages[-i]  # 从最后一条开始
            
            # 获取消息内容
            if hasattr(message, 'content'):
                content = message.content
            elif isinstance(message, dict) and 'content' in message:
                content = message['content']
            else:
                continue
            
            # 转换为小写进行检查
            content_lower = content.lower()
            
            # 按优先级检查命令（找到谁就先返回谁）
            if '$reset' in content_lower:
                return 'reset'
            elif '$rm' in content_lower:
                return 'rm'
            elif '$show' in content_lower:
                return 'show'
            elif '$fast' in content_lower:
                return 'workflow_switch_fast'
            elif '$drp' in content_lower:
                return 'workflow_switch_drp'
            elif '$help' in content_lower:
                return 'help'
        
        return None
    
    @staticmethod
    async def handle_backend_command(request: Request, chat_request, command: str) -> Response:
        """处理后台命令并返回响应"""
        from src.workflow.tools.scenario_table_tools import scenario_manager
        from config.manager import settings
        
        request_id = str(uuid.uuid4())
        
        try:
            if command == "reset":
                # 调用check_last_ai_response_index_workflow来智能判断合适的index
                from src.workflow.graph.check_last_ai_response_index_workflow import create_check_index_workflow
                
                # 获取原始消息数据
                original_messages = [msg.model_dump() for msg in chat_request.messages]
                
                # 创建并运行工作流
                workflow = create_check_index_workflow()
                recommended_index = await workflow.run(original_messages)
                
                if recommended_index > 0:
                    # 动态更新内存中的配置值
                    settings.langgraph.last_ai_messages_index = recommended_index
                    
                    message = f"""✅ 内存中的 last_ai_messages_index 已成功更新为: {recommended_index}

🔧 适配完成！系统已根据当前对话历史智能判断并设置了合适的AI消息索引。

⚠️  重要提醒：
• 此修改仅在当前程序运行期间有效
• 程序重启后将恢复为配置文件中的默认值
• 如果您不经常更换角色预设，建议手动将配置文件 config/config.yaml 中的 langgraph.last_ai_messages_index 修改为: {recommended_index}

📖 说明：last_ai_messages_index={recommended_index} 表示使用倒数第{recommended_index}条AI消息作为真实的角色扮演回复。"""
                else:
                    message = "❌ 自动判断失败，未能找到合适的AI消息索引。请检查对话历史中是否包含有效的assistant消息。"
                    
            elif command == "rm":
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
                    
            elif command == "workflow_switch_fast":
                # 切换到快速工作流模式
                current_mode = settings.agent.workflow_mode
                settings.agent.workflow_mode = "fast"
                message = f"✅ 已经将情景工作流从 {current_mode} 转换为 fast\n\n🚀 快速模式特点：\n• 使用快速经济的工作流\n• 2次LLM调用实现记忆搜索和情景更新\n• 响应速度更快，成本更低\n\n⚠️  重要提醒：\n• 此修改仅在当前程序运行期间有效\n• 程序重启后将恢复为配置文件中的默认值"
                
            elif command == "workflow_switch_drp":
                # 切换到深度角色扮演工作流模式
                current_mode = settings.agent.workflow_mode
                settings.agent.workflow_mode = "drp"
                message = f"✅ 已经将情景工作流从 {current_mode} 转换为 drp\n\n🧠 深度角色扮演模式特点：\n• 使用灵活但昂贵的ReAct工作流\n• 多轮推理和工具调用\n• 角色扮演深度更高，但成本较高\n\n⚠️  重要提醒：\n• 此修改仅在当前程序运行期间有效\n• 程序重启后将恢复为配置文件中的默认值"
                
            elif command == "help":
                # 显示帮助信息
                message = """📚 DeepRolePlay 命令帮助

当前版本支持直接在对话中输入命令，无需进入特殊模式。

🔧 可用命令：
• $help - 显示此帮助信息
• $fast - 切换到快速工作流模式（快速经济）
• $drp - 切换到深度角色扮演工作流模式（灵活但昂贵）
• $reset - 智能适配AI消息索引，自动判断真实的角色扮演回复
• $rm - 清空所有表格数据和scenario文件  
• $show - 显示当前所有表格数据"""
                    
            else:
                message = "Unknown command. Available commands: $help, $fast, $drp, $reset, $rm, $show"
            
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