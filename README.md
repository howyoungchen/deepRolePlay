# DeepRolePlay: 基于多智能体架构的深度角色扮演系统

[English](README_en.md) | 中文

## 项目概述

DeepRolePlay 是一个突破性的多智能体角色扮演系统，通过 Agent 协作机制彻底解决传统大语言模型的角色遗忘问题。

DeepRolePlay 采用多智能体分工架构：**记忆闪回智能体** + **情景更新智能体** + **主对话模型**，让 AI 告别角色遗忘，实现真正连贯的角色扮演。

## 🚀 解决角色扮演核心痛点

<img src="pics/generate.png" alt="DeepRolePlay演示" width="200">

### 😤 你是否遇到过这些问题？
- 🤖 **AI 突然忘记角色设定**：明明是法师却拿起了剑
- 📖 **剧情前后不一致**：昨天的重要情节今天完全不记得
- 💸 **Token 消耗巨大**：长对话费用飞涨，体验中断

### ✅ DeepRolePlay 的解决方案
- 🧠 **永不遗忘**：Agent 自动维护角色记忆，设定永久保持
- 🔄 **剧情连贯**：智能情景更新，千万轮对话依然逻辑清晰  
- 💰 **成本可控**：情景压缩技术，长对话费用降低 80%
- 📚 **智能联网**：集成 Wikipedia 百科，免费自动补全角色背景和故事设定
- ⚡ **即插即用**：5分钟集成，SillyTavern 等平台直接使用
- 🚀 **超高速响应**：采用 Gemini 2.5 Flash 智能代理，仅比正常回复多 20-30 秒

## 🎯 如何使用

### 💾 快速上手 - 下载即用版本

1. **📦 解压软件包**
   - 下载发布的软件包并解压到**非中文路径**下
   - 解压后文件夹包含：`config.yaml` 配置文件 + `DeepRolePlay.exe` 主程序

2. **⚙️ 修改配置文件**
   
   编辑 `config.yaml` 文件，**强烈推荐智能代理使用 Gemini 2.5 Flash（响应仅比正常多20秒）**：

   ```yaml
   # API代理配置 - 转发目标
   proxy:
     target_url: "https://api.deepseek.com/v1"                      # 你要转发的API地址，推荐deepseek
     timeout: 60                                                     # 建议设置60秒
   
   # 智能体配置 - Agent 使用的模型（必须是Gemini 2.5 Flash）
   agent:
     model: "gemini-2.5-flash"                                       # 强烈推荐 使用 Gemini 2.5 Flash
     base_url: "https://generativelanguage.googleapis.com/v1beta"   # Gemini API地址
     api_key: "your-gemini-api-key"                                  # 填入你的 Gemini API Key
     temperature: 0.7
     max_iterations: 25
   
   # 服务器配置
   server:
     host: "0.0.0.0"
     port: 6666                                                      # 记住这个端口号
   ```

3. **🚀 启动程序**
   - 双击 `DeepRolePlay.exe` 启动
   - 看到终端里项目正常运行即可
   - 🌟本项目会检查端口是否被占用。如果被占用会自动+1.所以最终真正的端口需要用户检查终端输出

4. **🔗 配置角色扮演前端**
   - 在 SillyTavern、OpenWebUI 等平台中
   - 将 `base_url` 改为：`http://localhost:6666/v1`
   - API Key 保持不变（会自动转发）
   - **重要**：关闭历史记录限制，务必发送全部历史记录给代理！（不用担心token爆炸，max_history_length会控制）

5. **🎭 开始角色扮演**
   - 立即享受无遗忘的角色扮演体验！

### 🔧 兼容性说明
- ✅ **完全兼容 OpenAI API 格式**：所有支持 OpenAI 的工具都能直接使用
- ✅ **支持主流模型**：Gemini、DeepSeek、Claude、本地 Ollama 等
- ✅ **双重配置**：Agent 和转发目标可使用不同模型，成本优化灵活

## Agent 工作原理

传统单一模型的问题：**角色遗忘** → **剧情断裂** → **体验崩坏**

DeepRolePlay 的 Agent 解决方案：
- 🔍 **记忆闪回智能体**：智能检索历史对话和外部知识
- 📝 **情景更新智能体**：实时维护角色状态和剧情连贯性  
- 🎭 **主对话模型**：基于完整上下文生成角色回应

## 工作流程

```
用户请求 -> HTTP代理服务
           |
           v
    触发工作流执行
           |
    +------+------+
    |             |
    v             v
记忆闪回      情景更新
智能体        智能体
    |             |
    +------+------+
           |
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

### 2. 配置服务

编辑 `config/config.yaml` 文件，**推荐使用 Gemini 2.5 Flash（响应快）**：

```yaml
# API代理配置 - 转发目标
proxy:
  target_url: "https://api.deepseek.com/v1"                      # 你要转发的API地址
  timeout: 60                                                     # 请求超时时间（秒）

# 智能体配置 - Agent 使用的模型（必须是Gemini 2.5 Flash）
agent:
  model: "gemini-2.5-flash"                                       # 必须使用 Gemini 2.5 Flash
  base_url: "https://generativelanguage.googleapis.com/v1beta"   # Gemini API地址
  api_key: "your-gemini-api-key"                                  # 填入你的 Gemini API Key
  temperature: 0.7                                                # 生成温度（0-1）
  max_iterations: 25                                              # 最大迭代次数

# 情景管理
scenario:
  file_path: "./scenarios/scenario.txt"      # 情景文件路径
  update_enabled: true                        # 是否启用自动更新

# 服务器配置
server:
  host: "0.0.0.0"
  port: 6666
```

### 3. 启动服务

```bash
uv run python main.py
```

### 4. 接入使用

将你的 AI 应用（SillyTavern、OpenWebUI 等）的 API 端点改为：
```
http://localhost:6666/v1
```


> 🌟本项目会检查端口是否被占用。如果被占用会自动+1.所以最终真正的端口需要用户检查终端输出

系统将自动：
1. 拦截对话请求
2. 执行智能体工作流
3. 更新情景状态
4. 将增强的上下文注入请求
5. 返回更准确的角色扮演响应

### 5. 打包发布

使用 PyInstaller 打包为可执行文件：

```bash
pyinstaller --name DeepRolePlay --onefile --clean --console --add-data "src;src" --add-data "utils;utils" main.py
```

打包后在 `dist/` 目录下会生成 `DeepRolePlay.exe`，连同配置文件一起发布给用户。

## 支持的模型

### 🔌 全面兼容 OpenAI 格式 API
本项目采用标准 OpenAI API 格式，支持所有兼容的服务商：

- **🌟 Gemini 2.5 Flash**（强烈推荐）：速度最快，仅增加20秒响应时间，角色扮演效果出色
- **💰 DeepSeek**：性价比最高，成本低廉
- **💻 本地 Ollama**：完全私有化部署，数据安全

### ⚠️ 不推荐 OpenAI 官方 API
虽然完全兼容 OpenAI 格式，但**不建议使用 OpenAI 官方服务**：
- 🔒 **过度安全策略**：对角色扮演内容限制严格，影响体验


## 参考文献

本项目的设计理念受到以下研究的启发：

- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) - Anthropic
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - LangChain

## 许可证

MIT License
