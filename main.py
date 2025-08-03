import uvicorn
import sys
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
    print("=== DeepRolePlay Proxy Server 启动 ===")
    print(f"目标URL: {settings.proxy.target_url}")
    print(f"日志目录: {settings.system.log_dir}")
    print(f"服务器: {settings.server.host}:{settings.server.port}")
    print("=====================================")
    
    yield
    
    # 关闭时执行
    print("DeepRolePlay Proxy Server 已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="DeepRolePlay Proxy Server",
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
    
    import socket
    import asyncio
    
    # 端口自动递增功能
    max_attempts = 20
    base_port = settings.server.port
    port_found = False
    current_port = base_port
    
    # 先检查端口是否可用
    for i in range(max_attempts):
        current_port = base_port + i
        
        # 使用 socket 检查端口是否可用
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # 尝试绑定端口
            sock.bind((settings.server.host, current_port))
            sock.close()
            # 端口可用
            port_found = True
            print(f"找到可用端口: {current_port}")
            break
        except OSError as e:
            # 端口被占用
            if i < max_attempts - 1:
                print(f"端口 {current_port} 已被占用，尝试下一个端口...")
                continue
            else:
                print(f"错误：已尝试 {max_attempts} 个端口（{base_port}-{base_port + max_attempts - 1}），全部被占用")
                sys.exit(1)
        finally:
            try:
                sock.close()
            except:
                pass
    
    if port_found:
        # 更新设置中的端口
        settings.server.port = current_port
        
        try:
            # 启动服务器
            uvicorn.run(
                app,
                host=settings.server.host,
                port=current_port,
                reload=settings.server.reload,
                log_level=settings.system.log_level.lower()
            )
        except KeyboardInterrupt:
            print("\n服务器已被用户中断")
            sys.exit(0)
        except Exception as e:
            print(f"启动服务器时发生错误: {e}")
            raise
    else:
        print(f"错误：无法找到可用端口")
        sys.exit(1)