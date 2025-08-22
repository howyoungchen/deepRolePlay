# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

DeepRolePlay是一个基于LangGraph工作流的深度角色扮演系统，通过自动化记忆管理彻底解决传统大语言模型的角色遗忘问题。系统采用**记忆闪回处理** + **情景更新管理** + **主对话模型**的三层架构，让AI告别角色遗忘，实现真正连贯的角色扮演。

### 核心解决方案
- 🧠 **永不遗忘**：自动化记忆管理系统，角色设定永久保持
- 🔄 **剧情连贯**：智能情景更新，千万轮对话依然逻辑清晰  
- 💰 **成本可控**：情景压缩技术，长对话费用降低80%
- 📚 **智能联网**：集成Wikipedia百科，自动补全角色背景和故事设定
- 🗂️ **结构化管理**：JSON表格系统管理世界观、角色、道具等信息，支持动态增删改查
- ⚡ **即插即用**：5分钟集成，SillyTavern等平台直接使用
- 🚀 **超高速响应**：支持任何OpenAI style的模型，除了首次构建情景，正常对话时仅多10秒

## 核心架构

### 技术栈
- **Web框架**: FastAPI + uvicorn
- **AI工作流**: LangGraph + LangChain
- **HTTP客户端**: httpx + OpenAI SDK (用于LLM转发)
- **配置管理**: Pydantic + PyYAML
- **外部知识**: Wikipedia API
- **图片生成**: ComfyUI集成 + Pillow图像处理
- **依赖管理**: UV (推荐) 或 pip
- **Python版本**: 3.12

### 关键执行流程

1. **请求代理流程**: HTTP请求 → 情景注入 (`utils/messages_process.py`) → 工作流执行 → 目标API调用 → 响应返回
2. **工作流执行**: 记忆闪回节点 → 情景更新节点 → 文件写入
3. **配置加载**: 支持命令行参数 `--config_path` 指定配置文件路径
4. **端口管理**: 自动检测端口占用，从配置端口开始递增查找可用端口（最多尝试20个）

### 主要组件

1. **HTTP代理服务** (`src/api/proxy.py`)
   - OpenAI兼容的 `/v1/chat/completions` 接口
   - ProxyService类处理转发逻辑，支持流式和非流式响应
   - 自动调用scenario_manager执行工作流
   - 处理API密钥转发和请求头管理
   - 后台控制台模式处理（$drp命令）

2. **工作流系统** (`src/workflow/graph/`)
   - **快速工作流** (`fast_scenario_workflow.py`): 2次LLM调用的优化版本，记忆搜索+情景编辑
   - **转发工作流** (`forward_workflow.py`): 独立的LLM转发工作流，支持直通模式
   - **图片生成工作流** (`image_generation_workflow.py`): ComfyUI集成，异步图片生成
   - ParentState/FastState状态管理，包含messages、current_scenario、memory_flashback
   - 使用LangGraph创建有向无环图工作流

3. **情景管理** (`src/scenario/manager.py`)
   - ScenarioManager协调工作流执行
   - 支持流式事件输出到前端
   - 管理scenario文件的读写操作
   - 处理后台命令（$drp, $reset, $rm, $show, $exit）

4. **配置系统** (`config/manager.py`)
   - 基于Pydantic的配置管理
   - 支持YAML文件和命令行参数
   - ProxyConfig、AgentConfig、LangGraphConfig、ComfyUIConfig等结构化配置
   - 支持从当前目录或指定路径加载配置
   - 双重配置：Agent模型配置 + 转发目标LLM配置分离

5. **表格管理系统** (`src/workflow/tools/scenario_table_tools.py`)
   - ScenarioManager类管理JSON表格结构的CRUD操作
   - 支持多表格管理（世界观表、角色表、道具表等）
   - 提供create_row、read_table、update_cell、delete_row等LangGraph工具
   - 自动验证字段定义，防止错误操作
   - 支持表格重置和初始化功能

6. **ComfyUI集成** (`3rd/comfyui/comfyui_client.py`)
   - ComfyUIAPI类处理与ComfyUI服务器的交互
   - 支持自定义工作流JSON配置
   - 异步图片生成和下载
   - 图片尺寸优化（`utils/image_optimizer.py`）

## 常用命令

### 启动生产服务器
```bash
python main.py
# 或使用uv（推荐）
uv run python main.py
```

### 启动开发服务器（带热重载）
```bash
uvicorn main:app --host 0.0.0.0 --port 6666 --reload
```

### 环境要求
- Python 3.12
- UV 包管理器（推荐）

### 安装依赖
```bash
# 使用uv安装（推荐）
uv pip install -r requirements.txt

# 验证关键依赖是否正确安装
PYTHONPATH=. uv run python -c "import langgraph; print('langgraph imported successfully')"
```

### 测试工作流
```bash
# 测试快速工作流（2次LLM调用版本）
PYTHONPATH=. uv run python src/workflow/graph/fast_scenario_workflow.py

# 测试转发工作流
PYTHONPATH=. uv run python src/workflow/graph/forward_workflow.py

# 测试重构后的工作流
PYTHONPATH=. uv run python unit_test_script/test_refactored_workflow.py

# 测试LLM转发和流式功能
PYTHONPATH=. uv run python unit_test_script/test_forward_llm_streaming.py

# 使用timeout避免长时间阻塞（推荐）
PYTHONPATH=. timeout 60 uv run python src/workflow/graph/fast_scenario_workflow.py
```

### 测试单个Agent功能
```bash
# 测试记忆闪回Agent（需要先配置API密钥）
PYTHONPATH=. uv run python -c "
from src.workflow.graph.scenario_updater import MemoryFlashbackAgent
import asyncio

async def test_memory_only():
    agent = MemoryFlashbackAgent()
    
    history = [
        {'role': 'user', 'content': '我想了解embedding和向量检索的技术。'},
        {'role': 'assistant', 'content': '这些是现代AI系统的重要组件。'}
    ]
    
    current_scenario = '张三是数据科学家，正在研究向量数据库'
    result = await agent.search_memories(current_scenario, history)
    print('记忆闪回结果:')
    print(result)

asyncio.run(test_memory_only())
"
```

### 测试表格管理工具
```bash
# 测试表格工具（初始化、创建、读取、更新、删除）
PYTHONPATH=. uv run python -c "
from src.workflow.tools.scenario_table_tools import scenario_manager
from config.manager import settings

# 初始化
scenario_manager.init(settings.scenario.file_path)

# 测试正确的字段创建
result1 = scenario_manager.create_row('世界观表', {'世界知识': '这是一个测试'})
print('正确字段测试结果:', result1)

# 读取表格内容
result2 = scenario_manager.read_table('世界观表')
print('读取表格结果:', result2)
"
```

### 单独测试HTTP代理服务
```bash
# 测试代理服务（需要已启动服务）
curl -X POST http://localhost:6666/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### 指定配置文件启动
```bash
python main.py --config_path /path/to/config.yaml
```

### 打包为可执行文件
```bash
# 使用PyInstaller打包 (解决中文编码问题的完整命令)
pyinstaller --name DeepRolePlay --onefile --clean --console \
  --add-data "src;src" --add-data "utils;utils" --add-data "config;config" \
  --hidden-import=locale --hidden-import=codecs \
  main.py
```

**重要说明**：
- main.py已包含UTF-8编码强制设置，解决终端中文乱码问题
- 打包后的exe可直接双击运行，无需额外配置

## 配置文件结构

`config/config.yaml` 主配置文件包含：
- `proxy`: 转发目标LLM的API配置（target_url、timeout、debug_mode）
- `agent`: Agent模型配置（base_url、api_key、model、temperature等）
- `langgraph`: 工作流参数（max_history_length、stream_workflow_to_frontend等）
- `scenario`: 情景文件路径配置（支持JSON表格格式）
- `server`: 服务器配置（host、port、reload）

### 重要配置说明
- **双重LLM配置**: Agent LLM（后台处理） + 转发目标LLM（用户对话）
- **工作流优化**: 使用快速工作流模式，2次LLM调用实现完整功能
- **历史长度控制**: `max_history_length` 控制转发给目标LLM的消息数量

## 文件结构重点

- `scenarios/`: 动态生成的情景文件存储（支持JSON表格格式）
- `logs/workflow/`: 结构化JSON日志输出（工作流执行日志）
- `src/prompts/`: 记忆闪回和情景更新的提示词模板
- `src/workflow/tools/`: LangGraph工具集（思考、搜索、文件操作、表格管理）
- `utils/`: 消息处理、日志、流转换等工具

## 开发注意事项

- 系统在端口6666提供服务，可通过config.yaml修改
- 工作流使用异步执行，所有节点支持流式事件输出
- 情景文件路径动态获取，由`utils/scenario_utils.py`管理
- 配置系统支持运行时通过命令行参数覆盖
- 记忆闪回使用Wikipedia API（可配置中英文），返回压缩的相关信息
- 所有API调用和工具执行都在LangGraph代理框架内进行
- 日志系统使用结构化JSON格式，便于后续分析
- **测试时务必设置PYTHONPATH环境变量**，避免模块导入错误
- 使用`timeout`命令包装测试脚本，避免长时间阻塞（推荐30-60秒）
- **工作流优化**: 使用单一快速工作流模式，2次LLM调用实现记忆搜索和情景更新
- **流式推送控制**: `stream_workflow_to_frontend` 控制Agent推理过程是否显示给用户
- **only_forward模式**: 配置`langgraph.only_forward: true`时直接转发，跳过所有Agent处理
- **清理策略**: `scenario.clear_strategy`控制何时清理重复消息（auto/always/manual）

## 调试和日志

### 查看运行日志
```bash
# 查看最新的日志文件
ls -la logs/workflow/

# 实时监控日志
tail -f logs/workflow/$(ls -t logs/workflow/ | head -1)

# 查看特定类型的日志（搜索、编辑、转发）
ls -la logs/workflow/*search*.json
ls -la logs/workflow/*edit*.json
ls -la logs/workflow/*forwarding*.json
```

### 调试Agent工作流
在 `config/config.yaml` 中设置：
```yaml
agent:
  debug: true  # 启用调试模式，输出详细的Agent执行信息
```

### 修改日志级别
```yaml
system:
  log_level: "DEBUG"  # INFO, DEBUG, WARNING, ERROR
```

### 检查配置文件语法
```bash
# 验证YAML配置文件语法
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

### 端口冲突处理
系统会自动检测端口占用，从配置的端口开始递增查找可用端口（最多尝试20个）。实际使用的端口会在终端输出中显示。

### 常见开发调试
```bash
# 检查端口占用情况
lsof -i :6666

# 终止占用端口的进程
pkill -f "python main.py"

# 清理scenario文件（重置角色状态）
rm -f scenarios/scenario.json

# 清理后台表格数据
rm -f DRP_*.json

# 测试特定工作流类型
# 工作流测试
PYTHONPATH=. timeout 60 uv run python src/workflow/graph/fast_scenario_workflow.py

# 检查依赖安装
PYTHONPATH=. uv run python -c "import langgraph, langchain, fastapi; print('All dependencies OK')"

# 验证配置文件
python -c "import yaml; print('Config valid:', bool(yaml.safe_load(open('config/config.yaml'))))"
```

## 项目特性

### API兼容性
- 完全兼容OpenAI Chat Completions API格式
- 支持流式(SSE)和非流式响应
- 自动处理API密钥转发
- 支持所有OpenAI兼容的模型服务商

### 工作流工具
- **思考工具** (`sequential_thinking.py`): 顺序思考和推理
- **搜索工具** (`re_search_tool.py`): 基于正则的内容搜索
- **读取工具** (`read_tool.py`): 文件读取操作
- **写入工具** (`write_tool.py`): 文件写入操作
- **编辑工具** (`edit_tool.py`): 文件编辑操作
- **表格工具** (`scenario_table_tools.py`): JSON表格结构的CRUD操作，支持多表格管理

### 错误处理
- 自动端口递增机制，避免端口冲突
- 详细的错误日志记录（JSON格式）
- 工作流执行异常捕获和处理
- HTTP请求超时和重试机制

## 架构细节

### 数据流向
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

### 关键组件交互
- **ProxyService**: 处理HTTP代理，协调工作流调用
- **ScenarioManager**: 管理情景生命周期，提供同步和流式接口
- **LangGraph工作流**: 使用StateGraph管理复杂的多Agent执行流程
- **工具系统**: 提供文件操作、搜索、思考等原子能力
- **流式转换**: WorkflowStreamConverter将工作流事件转换为SSE格式

### Agent配置要点
- 记忆闪回Agent使用Wikipedia工具搜索外部知识
- 情景更新Agent使用文件操作工具管理scenario文件
- 两个Agent共享sequential_thinking工具进行推理
- debug模式可输出详细的Agent执行信息

## 重要机制说明

### 端口自动递增机制
系统启动时会自动检测配置端口是否被占用：
- 从config.yaml中的端口开始检测
- 如被占用则自动+1，最多尝试20个端口
- 最终使用的端口会在终端输出中显示
- 避免手动解决端口冲突问题

### 角色切换和缓存清理
- 发送"$reset"命令智能适配AI消息索引，适用于预设切换
- 发送"$rm"命令清除历史缓存和表格数据
- 发送"$show"命令查看当前表格数据
- 发送"$drp"或"$help"查看可用命令帮助
- 避免不同角色间的情景混淆

### 配置文件热重载
- 支持在运行时修改config.yaml
- 部分配置项需要重启服务生效
- 建议使用uvicorn的--reload选项进行开发调试

## 工作流架构说明

### 快速工作流模式
- **文件**: `src/workflow/graph/fast_scenario_workflow.py`
- **结构**: 2次LLM调用优化流程，记忆搜索 + 情景编辑
- **优势**: 响应速度快，资源消耗低，功能完整
- **适用**: 角色扮演场景，平衡速度和功能性

### Forward模式 (only_forward: true)
- **文件**: `src/workflow/graph/forward_workflow.py`
- **结构**: 直接转发模式，跳过Agent处理
- **优势**: 最快响应，零额外开销
- **适用**: 测试环境或不需要角色记忆的场景

### 图片生成工作流 (ComfyUI集成)
- **文件**: `src/workflow/graph/image_generation_workflow.py`
- **结构**: 独立的图片生成工作流，支持ComfyUI后端
- **配置**: 通过`config.yaml`中的`comfyui`部分进行配置
- **特性**: 支持自定义工作流JSON，可调整生成参数和图片尺寸

## 图片生成系统

### ComfyUI集成特性
DeepRolePlay集成了ComfyUI后端，支持在角色扮演过程中自动生成符合场景的图片：

- **🖼️ 智能图片生成**：基于对话内容和场景描述自动生成相关图片
- **🔧 自定义工作流**：支持导入自定义的ComfyUI工作流JSON文件
- **⚡ 异步处理**：图片生成与对话并行处理，不影响响应速度
- **📱 前端优化**：自动调整图片尺寸，优化传输效率
- **🎨 智能触发**：根据对话内容智能判断是否需要生成图片

### 配置说明
```yaml
comfyui:
  enabled: true                           # 启用图片生成功能
  comfy_url: "http://127.0.0.1:8188"     # ComfyUI服务器地址
  api_key: "YOUR_COMFYUI_API_KEY_HERE"   # ComfyUI API密钥
  workflow_path: "3rd/comfyui/wai.json"  # 工作流配置文件路径
  positive_prompt_node_id: "6"           # 正向提示词节点ID
  latent_image_node_id: "5"              # 潜在图像节点ID
  width: 960                             # 图片宽度
  height: 1024                           # 图片高度
  num_images: 3                          # 生成图片数量
  positive_prefix: "masterpiece,best quality,amazing quality,"  # 提示词前缀
  max_display_size: 480                  # 最大显示尺寸
```

### 测试图片生成
```bash
# 测试ComfyUI连接和图片生成
PYTHONPATH=. timeout 120 uv run python src/workflow/graph/image_generation_workflow.py

# 检查图片生成工具
PYTHONPATH=. timeout 30 uv run python -c "
from src.workflow.tools.image_generation_tool import generate_one_img
print('工具名称:', generate_one_img.name)
print('工具描述:', generate_one_img.description)
"

# 测试完整的图片生成工作流
PYTHONPATH=. timeout 180 uv run python test_image_generation.py
```

### 图片生成工作流
- **文件**: `src/workflow/graph/image_generation_workflow.py`
- **工具**: `src/workflow/tools/image_generation_tool.py`
- **客户端**: `3rd/comfyui/comfyui_client.py`
- **优化器**: `utils/image_optimizer.py`

## 后台命令系统

DeepRolePlay支持在聊天界面中直接输入命令来管理系统状态和数据，无需进入特殊模式。

### 可用命令

| 命令 | 功能 | 说明 |
|------|------|------|
| `$drp` 或 `$help` | 显示帮助信息 | 查看所有可用命令和使用说明 |
| `$show` | 显示数据表格 | 查看当前所有内存表格（世界观、角色、道具等） |
| `$rm` | 清空数据 | 重置所有内存表格和场景文件 |
| `$reset` | 智能重置 | 智能分析对话历史，自动设置合适的AI消息索引来适配预设 |

### 使用方法

1. **查看帮助**：在任何聊天界面中发送 `$drp` 或 `$help`
   ```
   用户: $drp
   系统: 📚 DeepRolePlay 命令帮助
         
         当前版本支持直接在对话中输入命令，无需进入特殊模式。
         
         🔧 可用命令：
         • $help 或 $drp - 显示此帮助信息
         • $reset - 智能适配AI消息索引，自动判断真实的角色扮演回复
         • $rm - 清空所有表格数据和scenario文件  
         • $show - 显示当前所有表格数据
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

4. **智能重置**：发送 `$reset` 智能适配预设切换
   - 调用`check_last_ai_response_index_workflow`智能判断AI消息索引
   - 特别适用于SillyTavern等工具的预设适配
   - 自动清理旧场景，无需手动操作

### 技术实现
- 命令解析和执行逻辑位于`src/api/proxy_utils.py`的`BackendCommandHandler`类
- 支持在任何聊天界面中直接输入命令，无需模式切换

## 消息处理和流转换

### 消息处理流程
核心消息处理逻辑位于`utils/messages_process.py`：
- `inject_scenario`: 注入角色场景到消息中
- `auto_find_ai_message_index`: 自动查找合适的AI消息索引
- 支持历史消息长度控制和token优化

### 流式响应转换
流式响应处理由多个组件协作：
- `utils/stream_converter.py`: 工作流事件到SSE格式转换
- `utils/format_converter.py`: OpenAI格式响应转换
- `utils/event_formatter.py`: 事件格式化和美化

## 支持的模型

### 🔌 全面兼容OpenAI格式API
本项目采用标准OpenAI API格式，**无论是后台处理模型（Agent）还是转发目标模型（Proxy）都支持任何OpenAI Style格式的模型**：

#### 支持的服务商
- **🌟 OpenAI Style**：所有支持OpenAI Style的API
- **🔥 OpenRouter**：聚合多家服务商，模型选择丰富  
- **💻 本地Ollama**：完全私有化部署，数据安全
- **🚀 DeepSeek**：高质量对话，成本低廉
- **⚡ Claude**：通过OpenRouter或其他兼容服务使用
- **🧠 Gemini**：通过兼容接口使用
- **🔧 自建模型**：任何遵循OpenAI API格式的自部署模型

#### 配置说明
- **Agent模型**：用于后台记忆处理和情景更新，推荐使用成本较低的模型
- **Proxy模型**：用户实际对话的目标模型，可选择高质量对话模型  
- **双重配置**：两者可使用不同服务商，灵活优化成本和效果

#### 配置示例
```yaml
# 转发目标配置（用户主要对话模型）
proxy:
  target_url: "https://api.your-provider.com/v1"
  api_key: "Your-Main-LLM-API-key"

# Agent后台处理配置（记忆管理模型）
agent:
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com/v1"  
  api_key: "Your-Agent-API-Key"
```