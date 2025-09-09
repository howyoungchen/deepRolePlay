"""
图片生成工具 - 使用ComfyUI生成图片
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.manager import settings

# Import ComfyUI client from 3rd party
sys.path.insert(0, str(project_root / "3rd" / "comfyui"))
from comfyui_client import ComfyUIClient


async def generate_image(
    positive_prompt: str,
    negative_prompt: str = "",
    width: Optional[int] = None,
    height: Optional[int] = None,
    num_images: Optional[int] = None
) -> str:
    """
    通用图片生成工具
    
    使用ComfyUI生成图片，并将生成的图片保存到本地文件系统。
    
    Args:
        positive_prompt: 图片的正向提示词
        negative_prompt: 图片的负向提示词（可选）
        width: 图片宽度（可选，默认使用配置值）
        height: 图片高度（可选，默认使用配置值）
        num_images: 生成图片数量（可选，默认使用配置值）
    
    Returns:
        str: JSON格式的结果，包含生成的图片信息
    """
    
    result = {
        "status": "success",
        "message": "",
        "generated_images": [],
        "error": None
    }
    
    try:
        # 获取配置
        comfyui_config = settings.comfyui
        
        # 使用传入参数或配置默认值
        actual_width = width or comfyui_config.width
        actual_height = height or comfyui_config.height
        actual_num_images = num_images or comfyui_config.num_images
        
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
            result["status"] = "error"
            result["error"] = "无法连接到ComfyUI服务器"
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        # 添加提示词前缀
        full_prompt = comfyui_config.positive_prefix + positive_prompt
        
        # 确保输出目录存在
        output_dir = Path("logs/imgs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成图片
        saved_files = client.generate_image(
            positive_prompt=full_prompt,
            width=actual_width,
            height=actual_height,
            output_dir=str(output_dir),
            timeout=300
        )
        
        if saved_files:
            result["generated_images"] = saved_files
            result["message"] = f"成功生成{len(saved_files)}张图片"
        else:
            result["status"] = "error"
            result["error"] = "图片生成失败，未返回文件路径"
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"图片生成过程中出现异常: {str(e)}"
    
    return json.dumps(result, ensure_ascii=False, indent=2)


def create_image_generation_tool() -> dict:
    """
    创建一个预配置的图片生成工具，用于OpenAI函数调用
    
    Returns:
        dict: 包含function和schema的工具配置字典
    """
    async def generate_image_wrapper(
        positive_prompt: str, 
        negative_prompt: str = "",
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_images: Optional[int] = None
    ) -> str:
        """图片生成包装函数"""
        return await generate_image(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_images=num_images
        )
    
    # OpenAI 函数调用 schema 定义
    generate_schema = {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": """使用ComfyUI生成图片工具。

使用场景：
- 根据场景描述生成角色立绘、场景图片
- 为对话内容生成配图
- 创建符合剧情的视觉内容

工具特性：
- 支持自定义图片尺寸和数量
- 自动添加质量提升前缀
- 异步处理，不阻塞对话流程

返回：生成的图片文件路径列表（JSON格式）""",
            "parameters": {
                "type": "object",
                "properties": {
                    "positive_prompt": {
                        "type": "string",
                        "description": """正向提示词，描述要生成的图片内容。

提示词技巧：
- 使用具体描述：人物外貌、服装、姿态、表情
- 包含环境描述：背景、光照、氛围
- 添加风格词汇：画风、质量、细节等

示例：
"beautiful anime girl, long black hair, red dress, standing in garden, soft lighting, masterpiece"
"medieval castle, sunset sky, dramatic clouds, fantasy art style, high detail"""
                    },
                    "negative_prompt": {
                        "type": "string",
                        "description": "负向提示词，描述不想要的内容（可选）",
                        "default": ""
                    },
                    "width": {
                        "type": "integer",
                        "description": "图片宽度（像素），不指定时使用配置默认值",
                        "minimum": 64,
                        "maximum": 2048
                    },
                    "height": {
                        "type": "integer",
                        "description": "图片高度（像素），不指定时使用配置默认值",
                        "minimum": 64,
                        "maximum": 2048
                    },
                    "num_images": {
                        "type": "integer",
                        "description": "生成图片数量，不指定时使用配置默认值",
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["positive_prompt"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
    
    return {
        "function": generate_image_wrapper,
        "schema": generate_schema
    }


# 为了保持向后兼容性，提供旧接口
def generate_one_img(positive_prompt: str, config = None) -> str:
    """
    向后兼容的图片生成函数（同步版本）
    
    Args:
        positive_prompt: 图片的正向提示词
        config: 配置参数（为了兼容性保留，实际不使用）
    
    Returns:
        str: 生成的第一张图片的文件路径，如果失败返回错误信息
    """
    import asyncio
    
    try:
        # 检查是否已经在事件循环中
        try:
            asyncio.get_running_loop()
            # 如果已在事件循环中，使用新的线程运行
            import concurrent.futures
            
            def run_async():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(generate_image(positive_prompt))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async)
                result_json = future.result(timeout=60)  # 60秒超时
                
        except RuntimeError:
            # 没有运行中的事件循环，可以直接使用asyncio.run
            result_json = asyncio.run(generate_image(positive_prompt))
        
        # 解析结果
        result = json.loads(result_json)
        
        if result["status"] == "success" and result["generated_images"]:
            return result["generated_images"][0]  # 返回第一张图片路径
        else:
            return result.get("error", "图片生成失败")
            
    except Exception as e:
        return f"错误：图片生成过程中出现异常 - {str(e)}"


# 导出接口
__all__ = ["generate_image", "create_image_generation_tool", "generate_one_img"]