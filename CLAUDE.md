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

### 主要组件

1. **HTTP代理服务** (`src/api/proxy.py`)
   - 提供 `/v1/chat/completions` 接口
   - 支持流式和非流式响应
   - 自动注入情景内容到消息中

2. **工作流系统** (`src/workflow/graph/scenario_workflow.py`)
   - 记忆闪回节点：搜索历史相关信息
   - 情景更新节点：基于对话更新角色情景
   - 支持流式事件输出

3. **情景管理** (`src/scenario/manager.py`)
   - 管理情景文件读写
   - 协调工作流执行

4. **工具集** (`src/workflow/tools/`)
   - `sequential_thinking`: 序列思考工具
   - `re_search`: 正则搜索工具
   - `read_tool`/`write_tool`/`edit_tool`: 文件操作工具

## 常用命令

### 启动服务器
```bash
python main.py
```

### 启动开发服务器（带热重载）
```bash
uvicorn main:app --host 0.0.0.0 --port 6666 --reload
```

### 安装依赖
```bash
pip install -r requirements.txt
```

### 测试工作流
```bash
python src/workflow/graph/scenario_workflow.py
```

## 配置文件

- `config/config.yaml`: 主配置文件
  - `proxy`: 代理目标URL和API密钥
  - `agent`: LLM模型配置
  - `langgraph`: 工作流参数
  - `scenario`: 情景文件路径

## 文件结构重点

- `scenarios/`: 存储情景文件
- `logs/`: 日志输出目录
- `src/prompts/`: 工作流提示词模板
- `utils/`: 通用工具模块

## 开发注意事项

- 情景文件路径在 `config.yaml` 中的 `scenario.file_path` 配置
- 工作流使用异步执行，支持流式输出
- LLM调用前会自动注入当前情景内容
- 记忆闪回功能会搜索维基百科获取外部知识
- 所有工具调用都在LangGraph代理框架内执行