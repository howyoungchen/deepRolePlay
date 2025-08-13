# DeepRolePlay: 从Deep research到Deep RolePlay的角色扮演系统

[English](README_en.md) | 中文

## 项目概述

DeepRolePlay 是一个基于LangGraph工作流的深度角色扮演系统，通过自动化记忆管理彻底解决传统大语言模型的角色遗忘问题，**记忆闪回处理** + **情景更新管理** + **主对话模型**，让 AI 告别角色遗忘，实现真正连贯的角色扮演。

## 🚀 解决角色扮演核心痛点

<img src="pics/generate.png" alt="DeepRolePlay演示" width="200">

### 😤 你是否遇到过这些问题？
- 🤖 **AI 突然忘记角色设定**：明明是法师却拿起了剑
- 📖 **剧情前后不一致**：昨天的重要情节今天完全不记得
- 💸 **Token 消耗巨大**：长对话费用飞涨，体验中断

### ✅ DeepRolePlay 的解决方案
- 🧠 **永不遗忘**：自动化记忆管理系统，角色设定永久保持
- 🔄 **剧情连贯**：智能情景更新，千万轮对话依然逻辑清晰  
- 💰 **成本可控**：情景压缩技术，长对话费用降低 80%
- 📚 **智能联网**：集成 Wikipedia 百科，自动补全角色背景和故事设定
- 🗂️ **结构化管理**：JSON表格系统管理世界观、角色、道具等信息，支持动态增删改查
- ⚡ **即插即用**：5分钟集成，SillyTavern 等平台直接使用
- 🚀 **超高速响应**：支持任何OpenAI style的模型，除了首次构建情景，正常对话时仅多10秒

## 🎯 如何使用

### 💾 快速上手 - 下载即用版本

1. **📦 解压软件包**
   - 下载发布的软件包并解压到**非中文路径**下
   - 解压后文件夹包含：`config.yaml` 配置文件 + `DeepRolePlay.exe` 主程序

2. **⚙️ 修改配置文件**
   
   编辑 `config.yaml` 文件：

   配置文件已包含详细的初学者指南，主要需要修改以下配置：

   ```yaml
   # API代理配置 - 转发目标（你的主要聊天LLM）
   proxy:
     target_url: "https://api.your-provider.com/v1"    # 修改为你的API地址
     api_key: "Your-Main-LLM-API-key"                  # 修改为你的API密钥
   
   # Agent配置 - 后台处理模型
   agent:
     model: "deepseek-chat"                            # 任何OpenAI格式模型
     base_url: "https://api.deepseek.com/v1"             # API地址
     api_key: "Your-Agent-API-Key"                     # 修改为你的API密钥
   ```

3. **🚀 启动程序**
   - 双击 `DeepRolePlay.exe` 启动
   - 看到终端里项目正常运行即可
   - 🌟本项目会检查端口是否被占用。如果被占用会自动+1.所以最终真正的端口需要用户检查终端输出

4. **🔗 配置角色扮演前端**
   - 在 SillyTavern、OpenWebUI 等平台中
   - 将 `base_url` 改为：`http://localhost:6666/v1`
   - **重要**：关闭历史记录限制，务必发送全部历史记录给代理！（不用担心token爆炸，max_history_length会控制）

5. **🎭 开始角色扮演**
   - 立即享受无遗忘的角色扮演体验！
   - **更换角色时**：输入"$drp"并发送"$rm"可清除历史缓存，重新开始

## 🎛️ 后台控制台功能

DeepRolePlay 内置了强大的后台管理控制台，可通过聊天界面直接管理系统状态和数据。

### 📋 控制台命令

| 命令 | 功能 | 说明 |
|------|------|------|
| `$drp` | 进入后台模式 | 激活控制台管理功能 |
| `$show` | 显示数据表格 | 查看当前所有内存表格（世界观、角色、道具等） |
| `$rm` | 清空数据 | 重置所有内存表格和场景文件 |
| `$exit` | 退出后台模式 | 返回正常角色扮演模式 |

### 🔧 使用方法

1. **进入控制台**：在任何聊天界面中发送 `$drp`
   ```
   用户: $drp
   系统: Welcome to DeepRolePlay backend mode! Available commands:
         - $rm: Clear all memory tables and scenarios
         - $show: Display current memory tables  
         - $exit: Exit backend mode
   ```

2. **查看数据表格**：发送 `$show` 查看当前存储的所有角色信息
   ```
   用户: $show
   系统: Current Memory Tables:
         
         [世界观表] (2 rows)
         [角色表] (1 rows)
         [道具表] (0 rows)
         ...
   ```

3. **清空角色数据**：发送 `$rm` 完全重置角色扮演状态
   ```
   用户: $rm
   系统: Memory tables and scenarios directory have been reset successfully.
   ```

4. **退出控制台**：发送 `$exit` 返回正常聊天模式
   ```
   用户: $exit
   系统: Exited backend mode successfully.
   ```

### 🎨 ComfyUI 图片生成支持

DeepRolePlay 集成了 ComfyUI 后端，支持在角色扮演过程中自动生成符合场景的图片：

- **🖼️ 智能图片生成**：基于对话内容和场景描述自动生成相关图片
- **🔧 自定义工作流**：支持导入自定义的 ComfyUI 工作流 JSON 文件
- **⚡ 异步处理**：图片生成与对话并行处理，不影响响应速度
- **📱 前端优化**：自动调整图片尺寸，优化传输效率

配置示例：
```yaml
comfyui:
  enabled: true                           # 启用图片生成
  ip: "127.0.0.1"                        # ComfyUI 服务器地址
  port: 8188                              # ComfyUI 端口
  workflow_path: "3rd/comfyui/wai.json"  # 工作流文件路径
```

## 工作流原理

传统单一模型的问题：**角色遗忘** → **剧情断裂** → **体验崩坏**

DeepRolePlay 的工作流解决方案：
- 🔍 **记忆闪回处理**：智能检索历史对话和外部知识，基于LangGraph自动化执行
- 📝 **情景更新管理**：实时维护角色状态和剧情连贯性，支持表格化数据管理
- 🗂️ **表格管理系统**：结构化存储世界观、角色、道具等信息，支持动态增删改查
- 🎭 **主对话模型**：基于完整上下文生成角色回应

## 工作流程

```
         用户请求 -> HTTP代理服务
                      |
                      v
            [检查是否为控制台命令]
                /              \
            是 /                \ 否
              v                  v
     后台控制台处理          触发工作流执行
         |                        |
    命令解析                +------+------+
   ($drp/$show/               |             |
    $rm/$exit)                v             v
         |                记忆闪回      情景更新
    执行相应操作              处理节点      处理节点
    - 显示表格                |             |
    - 重置数据                |        表格管理
    - 模式切换                |        (增删改查)
         |                    |             |
         v                    +------+------+
    返回命令结果                       |
                                      v
                               注入更新的情景
                                      |
                                      v
                               转发至目标LLM
                                      |
                                      v
                               返回增强响应
```

## 开发者帮助

### 环境要求

- Python 3.12
- UV 虚拟环境管理器（推荐）

### 1. 安装项目

```bash
git clone https://github.com/yourusername/deepRolePlay.git
cd deepRolePlay
uv venv --python 3.12
uv pip install -r requirements.txt
```


### 2. 启动服务

```bash
uv run python main.py
```

### 3. 接入使用

将你的 AI 应用（SillyTavern、OpenWebUI 等）的 API 端点改为：
```
http://localhost:6666/v1
```


> 🌟本项目会检查端口是否被占用。如果被占用会自动+1.所以最终真正的端口需要用户检查终端输出

系统将自动：
1. 拦截对话请求
2. 执行工作流
3. 更新情景状态
4. 将增强的上下文注入请求
5. 返回更准确的角色扮演响应

### 4. 打包发布

使用 PyInstaller 打包为可执行文件：

```bash
pyinstaller --name DeepRolePlay --onefile --clean --console --add-data "src;src" --add-data "utils;utils" --add-data "config;config" main.py
```

打包后在 `dist/` 目录下会生成 `DeepRolePlay.exe`，连同配置文件一起发布给用户。

## 支持的模型

### 🔌 全面兼容 OpenAI 格式 API
本项目采用标准 OpenAI API 格式，**无论是后台处理模型（Agent）还是转发目标模型（Proxy）都支持任何 OpenAI Style 格式的模型**：

#### 支持的服务商
- **🌟 OpenAI Style**：所有支持OpenAI Style 的api
- **🔥 OpenRouter**：聚合多家服务商，模型选择丰富
- **💻 本地 Ollama**：完全私有化部署，数据安全
- **🚀 DeepSeek**：高质量对话，成本低廉
- **⚡ Claude**：通过 OpenRouter 或其他兼容服务使用
- **🧠 Gemini**：通过兼容接口使用
- **🔧 自建模型**：任何遵循 OpenAI API 格式的自部署模型

#### 配置说明
- **Agent模型**：用于后台记忆处理和情景更新，推荐使用成本较低的模型
- **Proxy模型**：用户实际对话的目标模型，可选择高质量对话模型
- **双重配置**：两者可使用不同服务商，灵活优化成本和效果



## 参考文献

本项目的设计理念受到以下研究的启发：

- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) - Anthropic
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - LangChain
- [st-memory-enhancement](https://github.com/muyoou/st-memory-enhancement) - muyoou

## 许可证

MIT License
