"""
get_weather 工具 - 用于获取指定位置的天气信息

这个文件同时作为 ReActAgent 工具创建的标准示例

OpenAI 原生函数调用工具创建指南：
============================

官方文档：https://platform.openai.com/docs/guides/function-calling

1. 工具文件结构
--------------
每个工具文件必须包含以下三个部分：

第一部分：工具函数定义
```python
async def tool_function(param1: str, param2: int = 10) -> str:
    \"\"\"
    工具功能描述
    
    Args:
        param1: 参数1描述
        param2: 参数2描述，默认值10
    
    Returns:
        str: 返回值描述
    \"\"\"
    # 工具实现逻辑
    return "结果"
```

第二部分：OpenAI Schema 定义
```python
tool_schema = {
    "type": "function",
    "function": {
        "name": "tool_function",
        "description": "工具功能的详细描述",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "参数1的描述"
                },
                "param2": {
                    "type": "integer",
                    "description": "参数2的描述",
                    "default": 10
                }
            },
            "required": ["param1"],
            "additionalProperties": False
        },
        "strict": True  # 启用严格模式，确保参数验证
    }
}
```

第三部分：导出配置
```python
# 组合工具配置（推荐格式）
tool_config = {
    "function": tool_function,
    "schema": tool_schema
}

# 导出列表
__all__ = ["tool_function", "tool_schema", "tool_config"]
```

2. 工具使用
----------
创建工具后，在使用时导入并传递给 ReActAgent：

```python
from workflow.tools.your_tool import tool_config

tools_with_schemas = [tool_config]

agent = ReActAgent(
    model=client,
    max_iterations=3,
    system_prompt=system_prompt,
    user_input=user_input,
    tools_with_schemas=tools_with_schemas,
    ...
)
```

3. 重要技术事项
--------------
- 工具函数支持同步和异步两种形式
- Schema 必须严格遵循 OpenAI 函数调用规范
- 使用 "strict": True 启用严格参数验证
- 参数类型要明确定义（string, integer, boolean, array, object）
- required 字段列出所有必需参数
- 建议使用 additionalProperties: False 防止意外参数
- enum 可用于限制参数值范围
- default 字段设置可选参数的默认值

4. 函数定义最佳实践（OpenAI 官方建议）
===============================

### 4.1 清晰的函数设计
- **编写清晰且详细的函数名称、参数描述和说明**
  - 函数名应该明确表达功能，如 get_weather 而不是 weather
  - 每个参数都要有详细描述，包括格式要求和示例
  - 明确描述输出代表什么，包括数据格式和含义

- **明确使用场景**
  - 在系统提示中描述何时使用此函数，何时不使用
  - 告诉模型确切地做什么，避免模糊指令
  - 提供具体的触发条件

### 4.2 包含示例和边缘情况
- **提供具体示例**（注意：过多示例可能降低推理性能）
  - 正常用例：get_weather("北京, 中国")
  - 边缘情况：模糊地名、不存在的城市等
  - 错误处理：网络超时、服务不可用等

- **纠正重复出现的故障**
  - 记录常见错误和解决方案
  - 在描述中明确禁止的操作

### 4.3 软件工程最佳实践
- **最小惊讶原则**
  - 函数行为应该符合直觉
  - 参数命名应该自解释
  - 返回格式应该一致

- **防止无效状态**
  - 使用枚举限制参数值：temperature_unit: ["celsius", "fahrenheit"]
  - 避免冲突参数：如 toggle_light(on: bool, off: bool) 允许无效调用
  - 使用对象结构确保数据完整性

- **实习生测试**
  - 仅凭你提供的信息，新人能否正确使用该函数？
  - 如果不能，他们会问什么问题？将答案添加到描述中
  - 确保文档自包含，无需额外解释

### 4.4 减少模型负担
- **避免重复参数**
  - 不要让模型填充你已经知道的参数
  - 如果有上下文信息，通过代码传递而非参数

- **合并序列调用**
  - 如果总是按顺序调用多个函数，考虑合并
  - 减少来回调用，提高效率

- **使用代码处理复杂逻辑**
  - 将复杂的数据处理放在函数内部
  - 让模型专注于高级决策，而非细节处理

5. 完整实际示例（体现最佳实践）
=============================
"""

import asyncio
import json
import random
from typing import Dict, Any

async def get_weather(location: str, unit: str = "celsius") -> str:
    """
    获取指定位置的实时天气信息
    
    此函数应在以下情况使用：
    - 用户明确询问天气情况
    - 需要基于天气做出决策时
    - 用户提到特定城市并想了解当地情况
    
    不应使用的情况：
    - 用户只是随意提及城市名，但没有询问天气
    - 进行历史天气查询（此函数只提供当前天气）
    
    Args:
        location (str): 城市和国家的完整名称
            格式要求："城市名, 国家" 
            正确示例："北京, 中国", "New York, USA", "London, UK"
            错误示例："北京"（缺少国家）, "NYC"（使用缩写）
            
        unit (str, optional): 温度单位，默认 "celsius"
            可选值：["celsius", "fahrenheit"]
            - "celsius": 摄氏度（°C）
            - "fahrenheit": 华氏度（°F）
    
    Returns:
        str: 结构化天气信息字符串，包含以下信息：
            - 位置确认
            - 当前温度（带单位）
            - 天气状况（晴朗/多云/阴天/雨/雪等）
            - 湿度百分比
            - 风力情况
            
        返回格式："天气信息: {location} 当前温度 {temp}°C, {condition}，湿度{humidity}%，{wind}"
    
    边缘情况处理：
        - 无效城市名：返回错误提示
        - 网络超时：返回服务暂时不可用提示
        - 参数格式错误：自动尝试修正或返回格式要求
    """
    # 模拟异步API调用
    await asyncio.sleep(0.1)
    
    # 生成合理范围内的随机温度和湿度
    temperature = random.randint(-10, 40)  # -10°C 到 40°C
    humidity = random.randint(30, 90)      # 30% 到 90% 湿度
    
    # 随机选择天气状况
    weather_conditions = ["晴朗", "多云", "阴天", "小雨", "中雨", "雪", "雾"]
    condition = random.choice(weather_conditions)
    
    # 随机选择风力
    wind_levels = ["无风", "微风", "轻风", "中风"]
    wind = random.choice(wind_levels)
    
    return f"天气信息: {location} 当前温度 {temperature}°C, {condition}，湿度{humidity}%，{wind}"

# OpenAI 函数调用 schema 定义（体现最佳实践）
get_weather_schema = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": """获取指定位置的实时天气信息。

使用场景：
- 用户明确询问天气："今天北京天气怎么样？"
- 需要基于天气做决策："我应该带伞吗？"
- 比较不同城市天气："上海和广州天气对比"

不要使用的情况：
- 用户只是提及城市但未询问天气
- 历史天气查询（此函数仅提供当前天气）
- 天气预报（此函数仅提供当前状况）

返回信息包含：位置、温度、天气状况、湿度、风力""",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": """城市和国家的完整名称，必须包含城市和国家两部分。

格式要求："城市名, 国家名"
正确示例：
- "北京, 中国"
- "New York, USA" 
- "London, UK"
- "Tokyo, Japan"

错误格式：
- "北京" (缺少国家)
- "NYC" (使用缩写)
- "纽约" (应使用 "New York, USA")

如果用户提供的地名不完整，优先尝试补全为完整格式。"""
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": """温度单位选择。默认使用摄氏度。

- "celsius": 摄氏度(°C)，国际标准单位
- "fahrenheit": 华氏度(°F)，美国常用单位

自动选择建议：
- 中国、欧洲、大部分国家使用 celsius
- 美国使用 fahrenheit""",
                    "default": "celsius"
                }
            },
            "required": ["location"],
            "additionalProperties": False
        },
        "strict": True
    }
}

# 导出工具配置
weather_tool = {
    "function": get_weather,
    "schema": get_weather_schema
}

# 为了方便直接使用，也可以单独导出
__all__ = ["get_weather", "get_weather_schema", "weather_tool"]

"""
上面的代码展示了完整的工具创建流程，体现了所有最佳实践：

✅ 最佳实践体现：
===============

1. **清晰的函数设计**：
   - 函数名 get_weather 明确表达功能
   - 详细的文档字符串包含使用场景和不使用场景
   - 明确的参数格式要求和示例
   - 清晰的返回值格式说明

2. **Schema 最佳实践**：
   - 详细的 description 包含使用指导
   - 具体的参数格式要求和示例
   - 错误格式的明确说明
   - 自动选择建议减少模型决策负担

3. **防止无效状态**：
   - 使用 enum 限制 unit 参数值
   - required 字段确保必需参数
   - additionalProperties: False 防止意外参数

❌ 常见错误示例（避免这样做）：
==========================

错误示例1 - 模糊的函数设计：
```python
def weather(place, temp_type="c"):  # ❌ 函数名不清晰
    # ❌ 缺少详细文档
    return "some weather data"      # ❌ 返回格式不明确
```

错误示例2 - 允许无效状态的参数：
```python
def toggle_light(on: bool, off: bool):  # ❌ 允许 on=True, off=True
    pass

def set_temperature(celsius: float, fahrenheit: float):  # ❌ 冲突参数
    pass
```

错误示例3 - 不清晰的 Schema：
```python
bad_schema = {
    "description": "天气工具",  # ❌ 描述过于简单
    "parameters": {
        "location": {"type": "string"},  # ❌ 没有格式要求
        "unit": {"type": "string"}       # ❌ 没有值约束
    }
}
```

✅ 使用此模板创建新工具：
======================

1. 复制这个文件
2. 修改函数名和功能实现
3. 更新文档字符串，明确使用场景
4. 调整 Schema 描述和参数
5. 确保通过"实习生测试"：新人能否仅凭文档正确使用

记住：好的工具设计应该让模型和人类都能轻松理解和正确使用。
"""