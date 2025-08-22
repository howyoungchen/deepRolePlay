"""
图片生成工具 - 使用ComfyUI生成图片
"""
import os
import sys
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.manager import settings

# Import ComfyUI client from 3rd party
sys.path.insert(0, str(project_root / "3rd" / "comfyui"))
from comfyui_client import ComfyUIClient


@tool
def generate_one_img(positive_prompt: str, config: RunnableConfig) -> str:
    """
    使用该工具生成一张图片，并将生成的图片保存到本地文件系统。
    
    返回为生成的图片文件地址。

    工具使用注意：
    - 入参只需要正向提示词即可。
    
    Args:
        positive_prompt: 图片的正向提示词
    
    Returns:
        str: 返回的文件地址
    """
    try:
        # 获取配置
        comfyui_config = settings.comfyui
        
        # 创建客户端
        client = ComfyUIClient(
            base_url=comfyui_config.comfy_url,
            api_key=comfyui_config.api_key,
            workflow_path=comfyui_config.workflow_path,
            positive_prompt_node_id=comfyui_config.positive_prompt_node_id,
            latent_image_node_id=comfyui_config.latent_image_node_id
        )
        
        # 测试连接
        if not client.test_connection():
            return "错误：无法连接到ComfyUI服务器"
        
        # 添加提示词前缀
        full_prompt = comfyui_config.positive_prefix + positive_prompt
        
        # 确保输出目录存在
        output_dir = Path("logs/imgs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成图片
        saved_files = client.generate_image(
            positive_prompt=full_prompt,
            width=comfyui_config.width,
            height=comfyui_config.height,
            output_dir=str(output_dir),
            timeout=300
        )
        
        if saved_files:
            # 返回第一张图片的路径（相对于项目根目录）
            # 直接返回保存的文件路径，它已经是相对路径
            return saved_files[0]
        else:
            return "错误：图片生成失败"
            
    except Exception as e:
        return f"错误：图片生成过程中出现异常 - {str(e)}"