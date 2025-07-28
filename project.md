# AI角色扮演代理系统 - 项目架构文档

## 1. 项目概述

本项目是一个基于FastAPI的HTTP代理服务器，作为AI角色扮演系统的中间层，负责接收、处理和转发OpenAI兼容API请求。系统通过动态注入情景文件和异步生成上下文来增强AI的角色扮演能力。

### 1.1 核心功能
- **API代理转发**：接收OpenAI兼容API请求并转发到配置的LLM服务
- **情景注入**：在转发前将情景内容注入到用户消息中
- **动态情景更新**：基于对话历史异步更新情景文件

## 2. 系统架构

### 2.1 技术栈
- **Web框架**: FastAPI
- **异步处理**: Python asyncio
- **HTTP客户端**: httpx/aiohttp
- **工作流引擎**: LangGraph
- **配置管理**: YAML/JSON
- **日志系统**: Python logging

### 2.2 系统架构图
```
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  External       │     │   Proxy Server      │     │  Target LLM      │
│  Application    │───▶│   (FastAPI)          │───▶│  Service         │
│                 │     │                     │     │                  │
└─────────────────┘     └──────────┬──────────┘     └──────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │  Scenario Manager   │
                        │  - Get Scenario     │
                        │  - Update Scenario  │
                        │    (LangGraph)      │
                        └─────────────────────┘
```

## 3. 核心模块设计

### 3.1 API代理模块 (src/api/proxy.py)
负责接收和转发HTTP请求，协调整个请求处理流程。

```python
# 主要功能：
- 接收 POST /v1/chat/completions 请求
- 验证请求格式和认证
- 调用情景管理器获取当前情景
- 注入情景到消息中（使用utils.message中的工具函数）
- 提交请求副本给情景管理器
- 转发到目标LLM服务
- 返回响应（支持流式和非流式）
```

### 3.2 配置管理模块 (config/manager.py)
管理系统配置，包括转发目标、认证信息等。配置项按模块分类组织。

```yaml
# config/config.yaml 示例
# API代理相关配置
proxy:
  target_url: "https://api.openai.com/v1/chat/completions"
  api_key: "sk-..."
  timeout: 30
  
# 情景管理相关配置
scenario:
  file_path: "./scenarios/current_scenario.json"
  update_enabled: true
  
# LangGraph工作流配置
langgraph:
  model: "gpt-4"
  max_history_length: 20
  
# 系统配置
system:
  log_level: "INFO"
  log_file: "./logs/app.log"
```

### 3.3 情景管理模块 (src/scenario/manager.py)
负责情景文件管理和工作流调度。

```python
class ScenarioManager:
    def __init__(self, config):
        """初始化情景管理器，加载配置"""
        pass
    
    async def get_current_scenario(self) -> str:
        """获取当前情景内容"""
        # 从文件或缓存读取当前情景
        pass
    
    async def submit_request(self, messages: List[dict]) -> None:
        """提交请求副本，异步启动情景更新工作流"""
        # 使用asyncio.create_task启动后台任务
        # 调用workflow/scenario_updater.py中的工作流
        pass
```

### 3.4 工作流模块 (src/workflow/scenario_updater.py)
基于LangGraph的情景更新工作流。

```python
async def update_scenario_workflow(messages: List[dict], config):
    """运行LangGraph工作流更新情景"""
    # 分析对话历史
    # 生成新的情景
    # 保存到文件
    pass
```


## 4. 数据流程

### 4.1 请求处理流程
1. **请求验证**：验证API请求格式和认证信息
2. **获取情景**：从情景管理器获取当前情景内容
3. **情景注入**：将情景内容注入到用户消息中
4. **异步提交**：将请求副本提交给情景管理器（后台处理）
5. **请求转发**：将处理后的消息转发到目标LLM服务
6. **响应返回**：返回LLM响应给客户端

### 4.2 情景更新流程（异步后台）
1. **接收请求副本**：从主流程接收消息历史
2. **分析对话**：使用LangGraph分析对话内容和上下文
3. **生成新情景**：基于分析结果生成或更新情景描述
4. **保存情景**：将新情景写入文件系统
5. **更新缓存**：刷新内存中的情景缓存

## 5. API接口设计

### 5.1 主要接口
```
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer {api_key}

{
  "model": "gpt-3.5-turbo",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "stream": false
}
```

### 5.2 健康检查接口
```
GET /health
Response: {"status": "healthy", "version": "1.0.0"}
```

### 5.3 情景管理接口（可选）
```
GET /scenario/current    # 获取当前情景
PUT /scenario/current    # 手动更新情景
GET /scenario/history    # 查看情景历史
```

## 6. 文件结构
```
project/
├── main.py                 # FastAPI应用入口
├── requirements.txt       # 依赖列表
├── src/
│   ├── __init__.py
│   ├── api/               # API相关模块
│   │   ├── __init__.py
│   │   └── proxy.py       # API代理逻辑
│   ├── scenario/          # 情景管理相关模块
│   │   ├── __init__.py
│   │   └── manager.py     # 情景管理
│   └── workflow/          # LangGraph工作流模块
│       ├── __init__.py
│       └── scenario_updater.py # 情景更新工作流
├── config/                # 配置相关
│   ├── __init__.py
│   ├── config.yaml        # 配置文件
│   └── manager.py         # 配置管理代码
├── utils/                 # 工具函数
│   ├── __init__.py
│   ├── message.py         # 消息处理工具函数
│   └── logger.py          # 项目日志保存逻辑
├── scenarios/             # 情景文件目录
├── logs/                  # 日志目录
└── tests/                 # 测试文件
```

## 7. 配置示例

### 7.1 情景文件格式
（未定，以后再说）

=================================================================

## 8. 项目进度记录

### 第一阶段开发进度 (提交: b4b8117)
**完成日期**: 2025年7月28日

#### 已完成功能:
1. **项目基础架构搭建**
   - 创建了完整的项目目录结构
   - 配置了基础的依赖管理 (requirements.txt)
   - 实现了配置管理系统 (config/manager.py, config/config.yaml)

2. **API代理核心功能**
   - 实现了FastAPI的HTTP代理服务器 (main.py)
   - 完成了API代理逻辑 (src/api/proxy.py)
   - 支持OpenAI兼容API请求接收和转发
   - 实现了基础的请求验证和认证

3. **日志系统**
   - 实现了完整的日志记录功能 (utils/logger.py)
   - 支持JSON格式日志输出
   - 配置了按时间戳命名的日志文件
   - 修复了日志系统的相关问题
