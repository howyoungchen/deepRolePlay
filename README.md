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
- 📚 **智能联网**：集成 Wikipedia 百科，自动补全角色背景和故事设定
- 🗂️ **结构化管理**：JSON表格系统管理世界观、角色、道具等信息，支持动态增删改查
- ⚡ **即插即用**：5分钟集成，SillyTavern 等平台直接使用
- 🚀 **超高速响应**：采用 Gemini 2.5 Flash 智能代理，Fast模式下仅需2次AI调用，比正常回复多 10 秒

## 🎯 如何使用

### 💾 快速上手 - 下载即用版本

1. **📦 解压软件包**
   - 下载发布的软件包并解压到**非中文路径**下
   - 解压后文件夹包含：`config.yaml` 配置文件 + `DeepRolePlay.exe` 主程序

2. **⚙️ 修改配置文件**
   
   编辑 `config.yaml` 文件，**强烈推荐智能代理使用 Qwen3-235B（Fast模式下仅需2次AI调用，响应仅比正常多10秒）**：

   ```yaml
   # API代理配置 - 转发目标
   proxy:
     target_url: "https://api.deepseek.com/v1"                      # 你要转发的API地址，推荐deepseek
     timeout: 60                                                     # 建议设置60秒
   
   # 工作流控制配置
   langgraph:
     max_history_length: 7                                           # 传递给转发目标LLM的历史消息数量，控制context长度和token消耗
     stream_workflow_to_frontend: false                              # DRP工作流推送开关，默认不推送DRP内容到前端，如需推送请设置为true并在SillyTavern导入deeproleplay.json正则
   
   # 智能体配置 - Agent 使用的模型（推荐Qwen3-235B）
   agent:
     model: "qwen/qwen3-235b-a22b-2507"                             # 推荐: qwen3-235b
     base_url: "https://openrouter.ai/api/v1"                        # OpenRouter API地址
     api_key: "your-openrouter-api-key"                              # 填入你的 OpenRouter API Key
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
   - **更换角色时**：输入"deeproleplay"并发送可清除历史缓存，重新开始

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

### 🎯 实用场景

- **🔄 角色切换**：使用 `$rm` 快速清除上一个角色的所有设定
- **📊 数据管理**：使用 `$show` 检查角色记忆是否正确保存
- **🐛 故障排除**：当角色行为异常时，用 `$show` 查看内存状态
- **🧪 测试调试**：开发过程中快速重置环境状态

### 🔧 兼容性说明
- ✅ **完全兼容 OpenAI API 格式**：所有支持 OpenAI 的工具都能直接使用
- ✅ **支持主流模型**：Gemini、DeepSeek、Claude、本地 Ollama 等
- ✅ **双重配置**：Agent 和转发目标可使用不同模型，成本优化灵活

## Agent 工作原理

传统单一模型的问题：**角色遗忘** → **剧情断裂** → **体验崩坏**

DeepRolePlay 的 Agent 解决方案：
- 🔍 **记忆闪回智能体**：智能检索历史对话和外部知识
- 📝 **情景更新智能体**：实时维护角色状态和剧情连贯性，支持表格化数据管理
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
    执行相应操作              智能体        智能体
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

### 2. 配置服务

编辑 `config/config.yaml` 文件，**推荐使用 Qwen3-235B（Fast模式下仅需2次AI调用，仅比正常多10秒）**：

```yaml
# API代理配置 - 转发目标
proxy:
  target_url: "https://api.deepseek.com/v1"        # 你要转发的API地址
  timeout: 30                                       # 请求超时时间（秒）
  debug_mode: false                                 # 调试模式开关

# 情景管理
scenario:
  file_path: "./scenarios/scenario.json"           # 情景文件路径（支持JSON表格格式）

# 工作流控制配置
langgraph:
  max_history_length: 7                            # 传递给转发目标LLM的历史消息数量，控制context长度和token消耗
  last_ai_messages_index: 1                       # 指定真实AI回复的索引(1=最后一个,2=倒数第二个)
  only_forward: false                               # 快速模式开关
  stream_workflow_to_frontend: false               # DRP工作流推送开关，默认不推送DRP内容到前端，如需推送请设置为true并在SillyTavern导入deeproleplay.json正则

# 智能体配置 - Agent 使用的模型（推荐Qwen3-235B）
agent:
  model: "qwen/qwen3-235b-a22b-2507"               # 推荐使用 Qwen3-235B
  base_url: "https://openrouter.ai/api/v1"         # API服务地址（推荐OpenRouter）
  api_key: "your-api-key"                          # 填入你的 API Key
  temperature: 0.1                                 # 生成温度（0-1）
  max_tokens: 8192                                 # 最大输出token数
  top_p: 0.9                                       # Top-p采样参数
  debug: false                                     # 调试模式
  max_iterations: 40                               # 最大处理轮次
  timeout: 120                                     # 单次请求超时时间

# 服务器配置
server:
  host: "0.0.0.0"
  port: 6666
  reload: false                                    # 热重载开关
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
pyinstaller --name DeepRolePlay --onefile --clean --console --add-data "src;src" --add-data "utils;utils" --add-data "config;config" main.py
```

打包后在 `dist/` 目录下会生成 `DeepRolePlay.exe`，连同配置文件一起发布给用户。

## 支持的模型

### 🔌 全面兼容 OpenAI 格式 API
本项目采用标准 OpenAI API 格式，支持所有兼容的服务商：

#### 智能体推荐模型
- **🌟 Qwen3-235B**（强烈推荐）：仅增加20秒响应时间，角色扮演效果出色

#### 转发目标模型
- **💻 本地 Ollama**：完全私有化部署，数据安全
- **🔥 DeepSeek**：高质量对话，成本低廉
- **⚡ Claude**：逻辑清晰，推理能力强



## 参考文献

本项目的设计理念受到以下研究的启发：

- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) - Anthropic
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - LangChain

## 许可证

MIT License
