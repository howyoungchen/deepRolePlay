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

### 3.1 API代理模块 (api_proxy.py)
负责接收和转发HTTP请求，协调整个请求处理流程。

```python
# 主要功能：
- 接收 POST /v1/chat/completions 请求
- 验证请求格式和认证
- 调用情景管理器获取当前情景
- 注入情景到消息中
- 提交请求副本给情景管理器
- 转发到目标LLM服务
- 返回响应（支持流式和非流式）
```

### 3.2 配置管理模块 (config.py)
管理系统配置，包括转发目标、认证信息等。

```yaml
# config.yaml 示例
proxy:
  target_url: "https://api.openai.com/v1/chat/completions"
  api_key: "sk-..."
  timeout: 30
  
scenario:
  file_path: "./scenarios/current_scenario.json"
  update_enabled: true
  
langgraph:
  model: "gpt-4"
  max_history_length: 20
```

### 3.3 情景管理模块 (scenario_manager.py)
整合了情景文件管理和LangGraph工作流，提供统一的接口。

```python
class ScenarioManager:
    def __init__(self, config):
        """初始化情景管理器，加载配置和LangGraph"""
        pass
    
    async def get_current_scenario(self) -> str:
        """获取当前情景内容"""
        # 从文件或缓存读取当前情景
        pass
    
    async def submit_request(self, messages: List[dict]) -> None:
        """提交请求副本，异步启动情景更新工作流"""
        # 使用asyncio.create_task启动后台任务
        # 不阻塞主流程
        pass
    
    async def _update_scenario_workflow(self, messages: List[dict]):
        """内部方法：运行LangGraph工作流更新情景"""
        # 分析对话历史
        # 生成新的情景
        # 保存到文件
        pass
```

### 3.4 消息处理模块 (message_processor.py)
处理消息的转换和情景注入。

```python
def inject_scenario(messages: List[dict], scenario: str) -> List[dict]:
    """将情景注入到消息列表中"""
    # 找到最后一条用户消息
    # 在消息内容前面添加情景
    # 返回处理后的消息列表
    pass
```

## 4. 数据流程

### 4.1 请求处理流程
```python
async def handle_chat_completion(request):
    # 1. 验证请求
    validate_request(request)
    
    # 2. 获取当前情景
    scenario = await scenario_manager.get_current_scenario()
    
    # 3. 注入情景到消息
    messages = inject_scenario(request.messages, scenario)
    
    # 4. 提交请求副本（异步，不等待）
    await scenario_manager.submit_request(request.messages)
    
    # 5. 转发请求
    response = await forward_to_llm(messages)
    
    # 6. 返回响应
    return response
```

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

## 6. 实现细节

### 6.1 情景注入策略
```python
# 示例：将情景作为用户消息的前缀
def inject_scenario(messages, scenario):
    messages_copy = messages.copy()
    for i in reversed(range(len(messages_copy))):
        if messages_copy[i]["role"] == "user":
            original_content = messages_copy[i]["content"]
            messages_copy[i]["content"] = f"{scenario}\n\n{original_content}"
            break
    return messages_copy
```

### 6.2 异步任务管理
```python
async def submit_request(self, messages):
    # 创建任务但不等待完成
    task = asyncio.create_task(
        self._update_scenario_workflow(messages)
    )
    # 可选：保存任务引用以便监控
    self._running_tasks.add(task)
    task.add_done_callback(self._running_tasks.discard)
```

### 6.3 LangGraph工作流示例
```python
async def _update_scenario_workflow(self, messages):
    # 构建分析prompt
    analysis_prompt = self._build_analysis_prompt(messages)
    
    # 调用LLM分析对话
    analysis = await self._call_llm(analysis_prompt)
    
    # 生成新情景
    new_scenario = await self._generate_scenario(analysis)
    
    # 保存到文件
    await self._save_scenario(new_scenario)
```

## 7. 文件结构
```
project/
├── main.py                 # FastAPI应用入口
├── config.yaml            # 配置文件
├── requirements.txt       # 依赖列表
├── src/
│   ├── __init__.py
│   ├── api_proxy.py       # API代理逻辑
│   ├── config.py          # 配置管理
│   ├── scenario_manager.py # 情景管理（含LangGraph）
│   ├── message_processor.py # 消息处理工具
│   └── utils.py           # 通用工具函数
├── scenarios/             # 情景文件目录
│   ├── current_scenario.json
│   └── history/          # 历史情景备份
├── logs/                  # 日志目录
└── tests/                 # 测试文件
```

## 8. 配置示例

### 8.1 情景文件格式
```json
{
  "version": "1.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "scenario": "你现在身处一个中世纪的魔法学院...",
  "context": {
    "location": "魔法学院图书馆",
    "time": "深夜",
    "atmosphere": "神秘而安静"
  },
  "recent_events": [
    "发现了一本古老的魔法书",
    "遇到了神秘的图书管理员"
  ]
}
```

### 8.2 LangGraph配置
```python
# LangGraph工作流配置
workflow_config = {
    "nodes": {
        "analyze": "分析对话历史",
        "extract": "提取关键信息",
        "generate": "生成新情景"
    },
    "edges": [
        ("analyze", "extract"),
        ("extract", "generate")
    ]
}
```

## 9. 性能优化

### 9.1 缓存策略
- 情景文件内存缓存，减少文件IO
- 设置缓存过期时间，确保及时更新

### 9.2 并发控制
- 限制同时运行的情景更新任务数
- 使用信号量控制并发量

### 9.3 资源管理
- 定期清理完成的异步任务
- 监控内存使用，防止泄漏

## 10. 错误处理

### 10.1 降级策略
```python
async def get_current_scenario(self):
    try:
        # 尝试读取情景文件
        return await self._read_scenario_file()
    except Exception as e:
        logger.error(f"Failed to read scenario: {e}")
        # 返回默认情景
        return self._get_default_scenario()
```

### 10.2 异常隔离
- 情景更新失败不影响主请求
- 记录错误日志便于调试

## 11. 监控指标
- 请求处理延迟
- 情景更新成功率
- 异步任务队列长度
- 缓存命中率

## 12. 开发计划
1. **Phase 1**: 基础代理功能和情景注入
2. **Phase 2**: 集成LangGraph工作流
3. **Phase 3**: 优化异步处理和缓存
4. **Phase 4**: 添加监控和管理接口
5. **Phase 5**: 性能调优和压力测试