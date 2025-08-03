import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from config.manager import settings
from src.api.proxy import router as proxy_router
from utils.logger import request_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    print("=== NarratorAI Proxy Server 启动 ===")
    print(f"目标URL: {settings.proxy.target_url}")
    print(f"日志目录: {settings.system.log_dir}")
    print(f"服务器: {settings.server.host}:{settings.server.port}")
    print("=====================================")
    
    yield
    
    # 关闭时执行
    print("NarratorAI Proxy Server 已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="NarratorAI Proxy Server",
        description="AI角色扮演代理系统 - HTTP代理服务器",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(proxy_router, prefix="", tags=["proxy"])
    
    # 确保日志目录存在
    Path(settings.system.log_dir).mkdir(exist_ok=True)
    
    return app


app = create_app()


if __name__ == "__main__":
    # 在打包环境下，直接传递app对象，而不是模块字符串
    # 这样可以避免uvicorn在打包后找不到'main'模块的问题
    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        log_level=settings.system.log_level.lower()
    )