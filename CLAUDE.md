# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于FastAPI的AI角色扮演代理系统，使用LangGraph工作流管理情景更新和记忆闪回功能。系统提供OpenAI兼容的HTTP代理服务，在LLM请求前自动更新角色情景。

## 核心架构

### 技术栈
- **Web框架**: FastAPI + uvicorn
- **AI工作流**: LangGraph + LangChain
- **HTTP客户端**: httpx
- **配置管理**: Pydantic + PyYAML
- **外部知识**: Wikipedia API

### 关键执行流程

1. **请求代理流程**: HTTP请求 → 情景注入 (`utils/messages_process.py`) → 工作流执行 → 目标API调用 → 响应返回
2. **工作流执行**: 记忆闪回节点 → 情景更新节点 → 文件写入
3. **配置加载**: 支持命令行参数 `--config_path` 指定配置文件路径

### 主要组件

1. **HTTP代理服务** (`src/api/proxy.py`)
   - OpenAI兼容的 `/v1/chat/completions` 接口
   - ProxyService类处理转发逻辑，支持流式和非流式响应
   - 自动调用scenario_manager执行工作流

2. **工作流系统** (`src/workflow/graph/scenario_workflow.py`)
   - ParentState状态管理，包含messages、current_scenario、memory_flashback
   - 记忆闪回节点：MemoryFlashbackAgent使用Wikipedia搜索外部知识
   - 情景更新节点：ScenarioUpdaterAgent基于对话更新角色情景
   - 使用LangGraph创建有向无环图工作流

3. **情景管理** (`src/scenario/manager.py`)
   - ScenarioManager协调工作流执行
   - 支持流式事件输出到前端

4. **配置系统** (`config/manager.py`)
   - 基于Pydantic的配置管理
   - 支持YAML文件和命令行参数
   - ProxyConfig、AgentConfig、LangGraphConfig等结构化配置

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
python src/workflow/graph/scenario_workflow.py
```

### 测试单个Agent功能
```bash
# 测试记忆闪回Agent（需要先配置API密钥）
PYTHONPATH=. python -c "
from src.workflow.graph.scenario_workflow import MemoryFlashbackAgent
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