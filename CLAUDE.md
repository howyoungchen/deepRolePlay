# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个AI角色扮演代理系统（NarratorAI），基于FastAPI的HTTP代理服务器，集成LangGraph工作流来动态更新角色情景。

## 开发命令

### 启动服务
```bash
python main.py
```

### 安装依赖
```bash
pip install -r requirements.txt
```

## 核心架构

### 主要模块结构
- `main.py` - FastAPI应用入口，配置CORS和路由
- `config/` - 配置管理，使用Pydantic和YAML配置
- `src/api/proxy.py` - OpenAI兼容的代理服务，处理聊天完成请求
- `src/scenario/manager.py` - 情景管理器，协调工作流更新
- `src/workflow/graph/scenario_workflow.py` - LangGraph工作流，包含记忆闪回和情景更新两个节点
- `utils/` - 工具模块，包含日志、消息处理、情景工具等

### 工作流架构
系统采用LangGraph纯函数式设计，包含两个核心节点：
1. **记忆闪回节点** - 使用re_search工具搜索历史对话，提取相关记忆
2. **情景更新节点** - 基于记忆闪回结果更新角色情景文件

### 配置管理
- 主配置文件：`config/config.yaml`
- 配置类定义：`config/manager.py`
- 支持代理、服务器、LangGraph、Agent等多个配置模块

### 代理流程
1. 接收OpenAI格式的聊天请求
2. 同步调用情景更新工作流
3. 将更新后的情景注入到消息中
4. 转发请求到目标LLM服务（如DeepSeek）
5. 支持流式和非流式响应

### 日志系统
- 请求/响应日志记录到 `logs/proxy/` 目录
- 工作流日志记录到 `logs/workflow/` 目录
- 支持结构化JSON日志格式

## 关键配置

### 服务器配置
- 默认端口：6666
- 目标API：DeepSeek API (https://api.deepseek.com/v1)
- 情景文件路径：`./scenarios/scenario.txt`

### LangGraph配置
- 默认模型：deepseek-chat
- 历史记录长度：20条消息
- 历史消息偏移：1（从倒数第1个AI消息开始）

## 重要工具和依赖

### 核心依赖
- FastAPI - Web框架
- LangGraph - 工作流编排
- LangChain-OpenAI - LLM集成
- Pydantic - 数据验证
- HTTPX - HTTP客户端

### 自定义工具
- `sequential_thinking` - 顺序思考工具
- `re_search` - 正则搜索工具
- `read_target_file`/`write_file`/`edit_file` - 文件操作工具

## 开发注意事项

### 文件路径约定
- 配置文件使用相对路径，如 `./scenarios/scenario.txt`
- 日志文件按时间戳命名，存储在对应子目录

### 错误处理
- 工作流执行失败时返回空字符串，不阻塞主流程
- HTTP错误会被捕获并转换为适当的HTTP状态码
- 日志中记录详细的错误信息用于调试

### 异步编程
- 所有I/O操作都使用异步模式
- 工作流节点函数都是异步函数
- 文件操作使用aiofiles库