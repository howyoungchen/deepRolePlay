import os
import sys
import argparse
import yaml
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class ProxyConfig(BaseModel):
    target_url: str = "https://api.openai.com/v1/chat/completions"
    models_url: Optional[str] = None  # The URL for the models API. If not set, it's automatically constructed from target_url.
    api_key: Optional[str] = None  # API key for the proxy target service
    provider: Optional[str] = None  # Provider specification for extra_body (e.g., "Anthropic" for OpenRouter)
    timeout: int = 30
    debug_mode: bool = False
    allow_extra_params: bool = False  # 是否允许传递额外参数到目标LLM，默认false保持v3.2兼容性
    
    def get_models_url(self) -> str:
        """Get the models API URL. If not set, it's automatically constructed from target_url."""
        if self.models_url:
            return self.models_url
        # Extract base_url from target_url and construct the models API URL.
        if "/chat/completions" in self.target_url:
            base_url = self.target_url.replace("/chat/completions", "")
            return f"{base_url}/models"
        else:
            # If target_url does not contain a standard path, assume it is the base_url.
            return f"{self.target_url.rstrip('/')}/models"




class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


class ScenarioConfig(BaseModel):
    file_path: str = "./scenarios/current_scenario.txt"
    output_format: str = "table"  # 可选值: "table" | "json"
    clear_strategy: str = "auto"  # 可选值: "auto" | "always" | "manual"
    similarity_threshold: float = 0.9  # 消息相似度阈值（90%）



class LangGraphConfig(BaseModel):
    max_history_length: int = 20
    last_ai_messages_index: int = 1  # Index of the AI message to use as real response (1 = last, 2 = second-to-last, etc.). Set to -1 for auto-detection of first AI message with content > ai_message_min_length chars from tail.
    ai_message_min_length: int = 100  # Minimum content length for AI messages when auto-detecting last_ai_messages_index
    only_forward: bool = False  # 当为true时跳过记忆闪回和情景更新节点，直接转发到LLM
    stream_workflow_to_frontend: bool = True  # 控制是否将工作流推理过程推送到前端


class AgentConfig(BaseModel):
    """Agent Configuration"""
    # Model Configuration
    model: str = "google/gemini-2.5-flash"
    temperature: float = 0.7
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = "sk-your-api-key-here"
    provider: Optional[str] = None  # Provider specification for extra_body (e.g., "Anthropic" for OpenRouter)
    max_tokens: int = 8192
    top_p: float = 0.9
    
    # Debugging and Loop Control
    debug: bool = False
    max_iterations: int = 25
    stream_mode: bool = True  # 是否使用真流式（astream），false为伪流式（ainvoke）
    workflow_mode: str = "fast"  # 工作流模式：fast（快速经济）或 drp（灵活但昂贵）
    enable_wiki_search: bool = False  # 是否启用Wikipedia搜索工具
    external_knowledge_path: str = ""  # 外部知识库文件路径（txt格式），留空则不使用
    
    # Timeout Settings
    timeout: int = 120


class ComfyUIConfig(BaseModel):
    """ComfyUI Configuration"""
    enabled: bool = False
    comfy_url: str = "http://127.0.0.1:8188"
    api_key: Optional[str] = None
    workflow_path: str = "3rd/comfyui/wai.json"
    positive_prompt_node_id: str = "6"
    latent_image_node_id: str = "5"
    width: int = 960
    height: int = 1024
    num_images: int = 1
    positive_prefix: str = "masterpiece,best quality,amazing quality,"
    max_display_size: int = 512  # 前端显示图片的最大边长（像素）


class LogConfig(BaseModel):
    """日志配置"""
    base_log_path: str = "./logs"  # 日志根目录
    enable_agent_history: bool = True  # 是否启用智能体历史记录
    history_format: str = "json"  # 历史记录格式: "json" | "txt" | "none"
    save_request_origin_messages: bool = False  # 是否保存完整的原始请求消息
    
    def get_session_log_path(self, timestamp: str) -> str:
        """获取指定时间戳的会话日志目录"""
        return f"{self.base_log_path}/{timestamp}"




class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__"
    )
    
    proxy: ProxyConfig = ProxyConfig()
    server: ServerConfig = ServerConfig()
    scenario: ScenarioConfig = ScenarioConfig()
    langgraph: LangGraphConfig = LangGraphConfig()
    agent: AgentConfig = AgentConfig()
    comfyui: ComfyUIConfig = ComfyUIConfig()
    log: LogConfig = LogConfig()
    
    @classmethod
    def load_from_yaml(cls, yaml_path: Optional[str] = None) -> "Settings":
        """Load settings from a YAML file."""
        if yaml_path is None:
            # Prioritize getting the config path from command-line arguments.
            # add_help=False to avoid conflicts with -h argument from other libraries like uvicorn.
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument('--config_path', type=str, default=None, help="Specify the configuration file path.")
            # parse_known_args() parses only defined arguments and ignores other unknown ones.
            args, _ = parser.parse_known_args()

            if args.config_path:
                # If a path is provided via command-line arguments, use it.
                yaml_path = args.config_path
            else:
                # 1. First, check for config.yaml in the current working directory.
                current_dir_config = Path.cwd() / "config.yaml"
                if current_dir_config.exists():
                    yaml_path = current_dir_config
                else:
                    # 2. Fallback to config/config.yaml in the project directory.
                    # Check if it's a packaged environment.
                    if getattr(sys, 'frozen', False):
                        # The directory where the packaged .exe is located.
                        base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
                    else:
                        # Script execution environment.
                        base_path = Path(__file__).parent.parent
                    
                    yaml_path = base_path / "config" / "config.yaml"

        config_path = Path(yaml_path)
        if not config_path.exists():
            print(f"Configuration file {config_path} not found, using default settings.")
            return cls()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            if yaml_data is None:
                yaml_data = {}
            
            return cls(**yaml_data)
        except Exception as e:
            print(f"Failed to load configuration file: {e}")
            return cls()


# No longer pass a fixed path when calling.
settings = Settings.load_from_yaml()