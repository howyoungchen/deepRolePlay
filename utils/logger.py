import os
import json
import uuid
import asyncio
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import Request, Response


class RequestLogger:
    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
    async def log_request_response(
        self,
        request: Request,
        response: Response,
        request_body: Dict[str, Any],
        response_body: Any,
        duration: float,
        request_id: str = None
    ):
        """记录请求和响应到JSON文件"""
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        timestamp = datetime.now()
        
        log_data = {
            "request_id": request_id,
            "timestamp": timestamp.isoformat(),
            "request": {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": request_body
            },
            "response": {
                "status_code": response.status_code,
                "headers": dict(response.headers) if hasattr(response, 'headers') else {},
                "body": response_body
            },
            "duration_seconds": duration
        }
        
        log_filename = timestamp.strftime("%Y_%m_%d_%H_%M_%S.json")
        log_path = self.log_dir / log_filename
        
        try:
            async with aiofiles.open(log_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(log_data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"写入日志文件失败: {e}")
    
    async def log_streaming_request(
        self,
        request: Request,
        request_body: Dict[str, Any],
        status_code: int,
        chunks_count: int,
        final_response: Dict[str, Any],
        duration: float,
        request_id: str = None
    ):
        """记录流式请求"""
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        timestamp = datetime.now()
        
        log_data = {
            "request_id": request_id,
            "timestamp": timestamp.isoformat(),
            "request": {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": request_body
            },
            "response": {
                "status_code": status_code,
                "headers": {"content-type": "application/json"},
                "body": final_response,
                "is_streaming": True,
                "chunks_count": chunks_count
            },
            "duration_seconds": duration
        }
        
        log_filename = timestamp.strftime("%Y_%m_%d_%H_%M_%S.json")
        log_path = self.log_dir / log_filename
        
        try:
            async with aiofiles.open(log_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(log_data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"写入日志文件失败: {e}")


request_logger = RequestLogger()