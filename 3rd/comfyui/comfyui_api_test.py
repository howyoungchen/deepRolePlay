#!/usr/bin/env python3
"""
ComfyUI API 实验脚本
用于测试ComfyUI的API调用，发送图像生成请求并保存结果
"""

import asyncio
import json
import uuid
import requests
import websockets
import base64
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComfyUIClient:
    """ComfyUI API 客户端"""
    
    def __init__(self, server_address: str = "127.0.0.1", port: int = 8188):
        self.server_address = server_address
        self.port = port
        self.client_id = str(uuid.uuid4())
        self.base_url = f"http://{server_address}:{port}"
        self.ws_url = f"ws://{server_address}:{port}/ws"
        
        # 创建输出目录
        self.output_dir = Path("images/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"初始化ComfyUI客户端: {self.base_url}")
        logger.info(f"客户端ID: {self.client_id}")
        logger.info(f"输出目录: {self.output_dir.absolute()}")

    def get_basic_workflow(self) -> Dict[str, Any]:
        """获取基本的文生图工作流模板"""
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 8,
                    "denoise": 1,
                    "seed": 156680208700286,
                    "steps": 20,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0]
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.ckpt"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 512,
                    "width": 512
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "beautiful scenery nature glass bottle landscape, purple galaxy bottle"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "text, watermark"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "images": ["8", 0]
                }
            }
        }

    def queue_prompt(self, prompt: Dict[str, Any]) -> str:
        """提交工作流到队列"""
        try:
            data = {
                "prompt": prompt,
                "client_id": self.client_id
            }
            
            response = requests.post(f"{self.base_url}/prompt", json=data)
            response.raise_for_status()
            
            result = response.json()
            prompt_id = result["prompt_id"]
            
            logger.info(f"工作流已提交，任务ID: {prompt_id}")
            return prompt_id
            
        except requests.RequestException as e:
            logger.error(f"提交工作流失败: {e}")
            raise

    async def monitor_progress(self, prompt_id: str) -> Dict[str, Any]:
        """通过WebSocket监控任务进度"""
        try:
            uri = f"{self.ws_url}?clientId={self.client_id}"
            logger.info(f"连接WebSocket: {uri}")
            
            async with websockets.connect(uri) as websocket:
                logger.info("WebSocket连接成功，开始监控任务进度...")
                
                while True:
                    try:
                        message = await websocket.recv()
                        
                        if isinstance(message, str):
                            data = json.loads(message)
                            
                            if data["type"] == "status":
                                status_data = data["data"]
                                logger.info(f"状态更新: 队列中任务数: {status_data.get('status', {}).get('exec_info', {}).get('queue_remaining', 'unknown')}")
                            
                            elif data["type"] == "progress":
                                progress_data = data["data"]
                                value = progress_data.get("value", 0)
                                max_value = progress_data.get("max", 0)
                                if max_value > 0:
                                    percentage = (value / max_value) * 100
                                    logger.info(f"进度: {value}/{max_value} ({percentage:.1f}%)")
                            
                            elif data["type"] == "executed":
                                node_id = data["data"]["node"]
                                logger.info(f"节点 {node_id} 执行完成")
                                
                                # 检查是否是我们的任务
                                if data["data"].get("prompt_id") == prompt_id:
                                    logger.info(f"任务 {prompt_id} 执行完成")
                                    return data["data"]
                        
                        else:
                            # 二进制数据可能是图像
                            logger.debug("收到二进制数据")
                            
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("WebSocket连接已关闭")
                        break
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析JSON消息失败: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"WebSocket监控失败: {e}")
            raise
    
    def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """获取任务历史记录"""
        try:
            response = requests.get(f"{self.base_url}/history/{prompt_id}")
            response.raise_for_status()
            
            history = response.json()
            logger.info(f"获取任务历史记录成功: {prompt_id}")
            return history
            
        except requests.RequestException as e:
            logger.error(f"获取历史记录失败: {e}")
            raise
    
    def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """获取生成的图像"""
        try:
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type
            }
            
            response = requests.get(f"{self.base_url}/view", params=params)
            response.raise_for_status()
            
            logger.info(f"获取图像成功: {filename}")
            return response.content
            
        except requests.RequestException as e:
            logger.error(f"获取图像失败: {e}")
            raise
    
    def save_images_from_history(self, history: Dict[str, Any], prompt_id: str) -> list:
        """从历史记录中保存图像"""
        saved_files = []
        
        try:
            if prompt_id not in history:
                logger.warning(f"历史记录中未找到任务: {prompt_id}")
                return saved_files
            
            outputs = history[prompt_id]["outputs"]
            
            for node_id, output_data in outputs.items():
                if "images" in output_data:
                    for image_info in output_data["images"]:
                        filename = image_info["filename"]
                        subfolder = image_info.get("subfolder", "")
                        
                        # 获取图像数据
                        image_data = self.get_image(filename, subfolder)
                        
                        # 保存到本地
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        local_filename = f"{timestamp}_{filename}"
                        local_path = self.output_dir / local_filename
                        
                        with open(local_path, "wb") as f:
                            f.write(image_data)
                        
                        saved_files.append(str(local_path))
                        logger.info(f"图像已保存: {local_path}")
            
            return saved_files
            
        except Exception as e:
            logger.error(f"保存图像失败: {e}")
            raise
    
    async def generate_image(self, prompt_text: str = None, negative_prompt: str = None, 
                           width: int = 512, height: int = 512, steps: int = 20) -> list:
        """生成图像的主要方法"""
        try:
            # 获取工作流模板
            workflow = self.get_basic_workflow()
            
            # 自定义参数
            if prompt_text:
                workflow["6"]["inputs"]["text"] = prompt_text
            if negative_prompt:
                workflow["7"]["inputs"]["text"] = negative_prompt
            if width or height:
                workflow["5"]["inputs"]["width"] = width
                workflow["5"]["inputs"]["height"] = height
            if steps:
                workflow["3"]["inputs"]["steps"] = steps
            
            # 随机种子
            import random
            workflow["3"]["inputs"]["seed"] = random.randint(1, 999999999999999)
            
            logger.info(f"开始生成图像...")
            logger.info(f"提示词: {workflow['6']['inputs']['text']}")
            logger.info(f"负面提示词: {workflow['7']['inputs']['text']}")
            logger.info(f"尺寸: {width}x{height}, 步数: {steps}")
            
            # 提交任务
            prompt_id = self.queue_prompt(workflow)
            
            # 监控进度
            await self.monitor_progress(prompt_id)
            
            # 获取结果
            history = self.get_history(prompt_id)
            
            # 保存图像
            saved_files = self.save_images_from_history(history, prompt_id)
            
            logger.info(f"图像生成完成，共保存 {len(saved_files)} 个文件")
            return saved_files
            
        except Exception as e:
            logger.error(f"图像生成失败: {e}")
            raise


async def main():
    """主函数"""
    try:
        # 创建客户端
        client = ComfyUIClient()
        
        # 测试生成图像
        saved_files = await client.generate_image(
            prompt_text="a beautiful landscape with mountains and lakes, sunset, cinematic lighting",
            negative_prompt="blurry, low quality, text, watermark",
            width=512,
            height=512,
            steps=20
        )
        
        print("\n=== 生成完成 ===")
        print(f"保存的文件:")
        for file_path in saved_files:
            print(f"  - {file_path}")
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)