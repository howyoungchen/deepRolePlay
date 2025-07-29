import os
import yaml
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class ProxyConfig(BaseModel):
    target_url: str = "https://api.openai.com/v1/chat/completions"
    api_key: str = "sk-your-api-key-here"
    timeout: int = 30


class SystemConfig(BaseModel):
    log_level: str = "INFO"
    log_dir: str = "./logs"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


class ScenarioConfig(BaseModel):
    file_path: str = "./scenarios/current_scenario.txt"
    update_enabled: bool = True


class LangGraphConfig(BaseModel):
    model: str = "deepseek-chat"
    max_history_length: int = 20


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
    
    @classmethod
    def load_from_yaml(cls, yaml_path: str = "config/config.yaml") -> "Settings":
        """从YAML文件加载配置"""
        config_path = Path(yaml_path)
        if not config_path.exists():
            print(f"配置文件 {yaml_path} 不存在，使用默认配置")
            return cls()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            if yaml_data is None:
                yaml_data = {}
            
            return cls(**yaml_data)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return cls()


settings = Settings.load_from_yaml()