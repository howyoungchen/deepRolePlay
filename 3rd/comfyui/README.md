# ComfyUI API 实验脚本

这个脚本用于测试和演示如何通过API调用ComfyUI进行图像生成。

## 功能特性

- 🔗 WebSocket连接监控任务进度
- 🎨 可自定义提示词和生成参数
- 💾 自动保存生成的图像到本地
- 📊 详细的日志记录和错误处理
- ⚙️ 基于JSON的工作流配置

## 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 或使用uv
uv pip install -r requirements.txt
```

## 使用方法

### 基本使用

```bash
# 运行脚本（确保ComfyUI服务已启动）
python comfyui_api_test.py
```

### 自定义参数

```python
from comfyui_api_test import ComfyUIClient
import asyncio

async def custom_generation():
    client = ComfyUIClient(server_address="127.0.0.1", port=8188)
    
    saved_files = await client.generate_image(
        prompt_text="a futuristic city at night, neon lights, cyberpunk style",
        negative_prompt="blurry, low quality, text",
        width=768,
        height=512,
        steps=25
    )
    
    print(f"生成的文件: {saved_files}")

asyncio.run(custom_generation())
```

## 配置要求

### ComfyUI服务

确保ComfyUI服务正在运行：
- 默认地址: `127.0.0.1:8188`
- WebSocket端点: `ws://127.0.0.1:8188/ws`
- REST API端点: `http://127.0.0.1:8188`

### 模型要求

脚本使用的默认工作流需要以下模型：
- Checkpoint模型: `v1-5-pruned-emaonly.ckpt`
  
如果没有该模型，请：
1. 修改脚本中的`ckpt_name`参数
2. 或下载对应的模型文件到ComfyUI的models目录

## 输出目录

生成的图像将保存到：
- 默认目录: `images/output/`
- 文件命名格式: `YYYYMMDD_HHMMSS_原始文件名.png`

## API端点说明

### 主要端点
- `POST /prompt` - 提交工作流
- `GET /history/{prompt_id}` - 获取任务历史
- `GET /view` - 获取生成的图像
- `WS /ws` - WebSocket状态监控

### 工作流结构
脚本使用标准的文生图工作流，包含以下节点：
- CheckpointLoaderSimple: 加载模型
- CLIPTextEncode: 处理提示词
- EmptyLatentImage: 创建潜在图像
- KSampler: 采样器
- VAEDecode: 解码
- SaveImage: 保存图像

## 错误处理

脚本包含完整的错误处理：
- 网络连接异常
- WebSocket断连重试
- JSON解析错误
- 文件保存失败

## 日志记录

脚本提供详细的日志输出：
- 任务提交状态
- 进度监控信息
- 文件保存路径
- 错误信息和堆栈

## 扩展功能

可以通过修改`get_basic_workflow()`方法来：
- 添加更多节点
- 支持不同的采样器
- 实现图像到图像生成
- 添加ControlNet支持
- 支持批量生成

## 注意事项

1. 确保ComfyUI服务已正确启动
2. 检查模型文件是否存在
3. 确保有足够的磁盘空间保存图像
4. 网络连接稳定（用于WebSocket监控）