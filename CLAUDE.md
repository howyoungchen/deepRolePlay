# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

DeepRolePlay是一个基于FastAPI的AI角色扮演代理系统，使用LangGraph工作流管理情景更新和记忆闪回功能。系统提供OpenAI兼容的HTTP代理服务，通过多智能体架构解决角色遗忘问题。

## 核心架构

### 技术栈
- **Web框架**: FastAPI + uvicorn
- **AI工作流**: LangGraph + LangChain
- **HTTP客户端**: httpx
- **配置管理**: Pydantic + PyYAML
- **外部知识**: Wikipedia API
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

2. **工作流系统** (`src/workflow/graph/scenario_workflow.py`)
   - ParentState状态管理，包含messages、current_scenario、memory_flashback
   - 记忆闪回节点：MemoryFlashbackAgent使用Wikipedia搜索外部知识
   - 情景更新节点：ScenarioUpdaterAgent基于对话更新角色情景
   - 使用LangGraph创建有向无环图工作流

3. **情景管理** (`src/scenario/manager.py`)
   - ScenarioManager协调工作流执行
   - 支持流式事件输出到前端
   - 管理scenario文件的读写操作

4. **配置系统** (`config/manager.py`)
   - 基于Pydantic的配置管理
   - 支持YAML文件和命令行参数
   - ProxyConfig、AgentConfig、LangGraphConfig等结构化配置
   - 支持从当前目录或指定路径加载配置

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
# 使用pip安装
pip install -r requirements.txt

# 使用uv安装（推荐）
uv pip install -r requirements.txt
```

### 测试工作流
```bash
# 测试完整工作流（包含记忆闪回和情景更新）
python src/workflow/graph/scenario_workflow.py

# 测试单个工作流组件
PYTHONPATH=. python src/workflow/graph/scenario_workflow.py
```

### 测试单个Agent功能
```bash
# 测试记忆闪回Agent（需要先配置API密钥）
PYTHONPATH=. python -c "
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

### 指定配置文件启动
```bash
python main.py --config_path /path/to/config.yaml
```

### 打包为可执行文件
```bash
# 使用PyInstaller打包
pyinstaller --name DeepRolePlay --onefile --clean --console --add-data "src;src" --add-data "utils;utils" main.py
```

## 配置文件结构

`config/config.yaml` 主配置文件包含：
- `proxy`: 目标API的URL和密钥
- `agent`: LLM模型配置（base_url、api_key、model等）
- `langgraph`: 工作流参数（历史长度、模型选择）
- `scenario`: 情景文件路径和更新开关
- `system`: 日志级别和目录
- `server`: 主机和端口配置

## 文件结构重点

- `scenarios/`: 动态生成的情景文件存储
- `logs/proxy/`: 结构化JSON日志输出
- `src/prompts/`: 记忆闪回和情景更新的提示词模板
- `src/workflow/tools/`: LangGraph工具集（思考、搜索、文件操作）
- `utils/`: 消息处理、日志、流转换等工具

## 开发注意事项

- 系统在端口6666提供服务，可通过config.yaml修改
- 工作流使用异步执行，所有节点支持流式事件输出
- 情景文件路径动态获取，由`utils/scenario_utils.py`管理
- 配置系统支持运行时通过命令行参数覆盖
- 记忆闪回使用中文Wikipedia API，返回压缩的相关信息
- 所有API调用和工具执行都在LangGraph代理框架内进行
- 日志系统使用结构化JSON格式，便于后续分析

## 调试和日志

### 查看运行日志
```bash
# 查看最新的日志文件
ls -la logs/proxy/

# 实时监控日志
tail -f logs/proxy/$(ls -t logs/proxy/ | head -1)
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

### 错误处理
- 自动端口递增机制，避免端口冲突
- 详细的错误日志记录（JSON格式）
- 工作流执行异常捕获和处理
- HTTP请求超时和重试机制

## 架构细节

### 数据流向
```
HTTP请求 → ProxyService → 
  ↓
情景注入(inject_scenario) → 
  ↓
ScenarioManager.update_scenario → 
  ↓
LangGraph工作流(scenario_workflow) →
  ↓
记忆闪回节点(memory_flashback_node) + 情景更新节点(scenario_updater_node) →
  ↓
文件系统(scenarios/*.txt) →
  ↓
目标LLM API调用 → 响应返回
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