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
    api_key: Optional[str] = None  # API key is obtained from the frontend request, no longer needs to be configured.
    timeout: int = 30
    debug_mode: bool = False
    
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


class SystemConfig(BaseModel):
    log_level: str = "INFO"
    log_dir: str = "./logs"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


class ScenarioConfig(BaseModel):
    file_path: str = "./scenarios/current_scenario.txt"



class LangGraphConfig(BaseModel):
    max_history_length: int = 20
    history_ai_message_offset: int = 1  # Start counting history from the Nth-to-last AI message.
    only_forward: bool = False  # 当为true时跳过记忆闪回和情景更新节点，直接转发到LLM


class AgentConfig(BaseModel):
    """Agent Configuration"""
    # Model Configuration
    model: str = "google/gemini-2.5-flash"
    temperature: float = 0.7
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = "sk-your-api-key-here"
    max_tokens: int = 8192
    top_p: float = 0.9
    
    # Debugging and Loop Control
    debug: bool = False
    max_iterations: int = 25
    
    # Timeout Settings
    timeout: int = 120


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__"
    )
    
    proxy: ProxyConfig = ProxyConfig()
    system: SystemConfig = SystemConfig()
    server: ServerConfig = ServerConfig()
    scenario: ScenarioConfig = ScenarioConfig()
    langgraph: LangGraphConfig = LangGraphConfig()
    agent: AgentConfig = AgentConfig()
    
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