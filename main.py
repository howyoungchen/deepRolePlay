import uvicorn
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from config.manager import settings
from src.api.proxy import router as proxy_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Execute on startup
    print("=== DeepRolePlay Proxy Server Starting ===")
    print(f"Target URL: {settings.proxy.target_url}")
    print(f"Server: {settings.server.host}:{settings.server.port}")
    print("=====================================")
    
    yield
    
    # Execute on shutdown
    print("DeepRolePlay Proxy Server has been shut down")


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="DeepRolePlay Proxy Server",
        description="AI Role-playing Proxy System - HTTP Proxy Server",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    app.include_router(proxy_router, prefix="", tags=["proxy"])
    
    
    return app


app = create_app()


if __name__ == "__main__":
    # In a packaged environment, pass the app object directly instead of a module string
    # This avoids the issue of uvicorn not being able to find the 'main' module after packaging
    
    import socket
    import asyncio
    
    # Port auto-increment feature
    max_attempts = 20
    base_port = settings.server.port
    port_found = False
    current_port = base_port
    
    # First, check if the port is available
    for i in range(max_attempts):
        current_port = base_port + i
        
        # Use a socket to check if the port is available
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Try to bind the port
            sock.bind((settings.server.host, current_port))
            sock.close()
            # Port is available
            port_found = True
            print(f"Found available port: {current_port}")
            break
        except OSError as e:
            # Port is in use
            if i < max_attempts - 1:
                print(f"Port {current_port} is already in use, trying the next one...")
                continue
            else:
                print(f"Error: Tried {max_attempts} ports ({base_port}-{base_port + max_attempts - 1}), all are in use")
                sys.exit(1)
        finally:
            try:
                sock.close()
            except:
                pass
    
    if port_found:
        # Update the port in settings
        settings.server.port = current_port
        
        try:
            # Start the server
            uvicorn.run(
                app,
                host=settings.server.host,
                port=current_port,
                reload=settings.server.reload,
                log_level="info"
            )
        except KeyboardInterrupt:
            print("\nServer has been interrupted by the user")
            sys.exit(0)
        except Exception as e:
            print(f"An error occurred while starting the server: {e}")
            raise
    else:
        print(f"Error: Could not find an available port")
        sys.exit(1)