# 租房推荐 Agent 系统 - 完整教程

## 📋 系统架构

```
┌─────────────────────────────────────────┐
│         用户查询 (User Query)            │
└─────────────┬───────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│           Agent (ReAct Loop)             │
│  推理 (Reasoning) → 决策 (Action)        │
└─────────────┬───────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      Function Calling (工具选择)         │
│  LLM 从工具列表中选择合适的工具           │
└─────────────┬───────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      ToolRegistry (工具注册中心)         │
│  管理、查询、执行所有工具                 │
└─────────────┬───────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│         Tool 对象（具体工具）            │
│  search_properties, calculate_commute等  │
└─────────────────────────────────────────┘
```

---

## 🔧 核心概念

### 1. **Tool（工具）**
定义了一个单独的能力单元。

**示例：**
```python
from core.tool_system import Tool

async def search_properties_impl(location: str, max_budget: int):
    # 搜索房源的实际逻辑
    return {...}

search_tool = Tool(
    name="search_properties",
    description="搜索符合条件的房源",
    func=search_properties_impl,
    parameters={
        'type': 'object',
        'properties': {
            'location': {'type': 'string'},
            'max_budget': {'type': 'integer'}
        },
        'required': ['location', 'max_budget']
    }
)
```

### 2. **ToolResult（工具结果）**
所有工具执行都返回标准化的结果格式。

```python
from core.tool_system import ToolResult

result = ToolResult(
    success=True,
    data={'properties': [...]},
    error=None,
    execution_time_ms=250,
    tool_name='search_properties'
)
```

### 3. **ToolRegistry（工具注册中心）**
管理所有工具，负责执行和统计。

```python
from core.tool_system import ToolRegistry

registry = ToolRegistry()
registry.register(search_tool)
registry.register(commute_tool)

# 执行工具
result = await registry.execute_tool('search_properties', 
    location='UCL', max_budget=1500)
```

### 4. **FunctionCalling（函数调用）**
让 LLM 从工具列表中选择合适的工具。

```python
from core.tool_system import FunctionCalling

fc = FunctionCalling(registry)
decision = fc.ask_ai_to_choose_tool(
    user_query="Find me a flat near UCL",
    llm_func=llm,
    context={'observations': [...]}
)
# 返回：{'action': 'use_tool', 'tool_name': 'search_properties', ...}
```

### 5. **Agent（代理）**
实现 ReAct 循环，自动推理和执行。

```python
from core.agent import Agent

agent = Agent(
    tool_registry=registry,
    llm_func=llm,
    max_turns=5
)

result = await agent.run("Find me a flat...")
```

---

## 📦 已实现的工具

### ✅ Tool 1: search_properties
**功能：** 搜索符合条件的房源

**参数：**
- `location` **(必需)**: 地点（如 UCL、King's College）
- `max_budget` **(必需)**: 最大预算（英镑）
- `min_budget` (可选): 最小预算，默认 500
- `radius_miles` (可选): 搜索半径，默认 2.0
- `limit` (可选): 结果数限制，默认 25

**何时使用：**
- 用户要找房子
- 需要获取房源列表
- 开始新的搜索任务

---

### ✅ Tool 2: calculate_commute
**功能：** 计算两个地址之间的通勤时间

**参数：**
- `from_address` **(必需)**: 出发地（房源地址）
- `to_address` **(必需)**: 目的地（工作地点）
- `mode` (可选): 通勤方式（transit/driving/walking/bicycling），默认 transit

**何时使用：**
- 用户提到通勤时间要求
- 需要过滤房源
- 用户问"到XX要多久"

---

### ✅ Tool 3: check_safety
**功能：** 检查地区的安全指数

**参数：**
- `address` **(必需)**: 要检查的地址
- `latitude` (可选): 纬度
- `longitude` (可选): 经度

**何时使用：**
- 用户关心地区安全
- 需要对房源进行安全评估
- 比较不同房源的安全性

---

### ✅ Tool 4: get_weather
**功能：** 获取地点的天气信息

**参数：**
- `location` **(必需)**: 地点名称
- `latitude` (可选): 纬度
- `longitude` (可选): 经度

**何时使用：**
- 用户想了解该地区的天气
- 规划看房时间时需要天气信息
- 评估地区气候环境

---

## 🚀 使用示例

### 方式 1: 直接使用 Tool

```python
import asyncio
from core.tools import search_properties_tool

async def example1():
    result = await search_properties_tool.execute(
        location="UCL",
        max_budget=1500
    )
    
    if result.success:
        print(f"找到 {result.data['count']} 个房源")
    else:
        print(f"错误: {result.error}")

asyncio.run(example1())
```

### 方式 2: 使用 ToolRegistry

```python
import asyncio
from core.tool_system import create_tool_registry

async def example2():
    registry = create_tool_registry()
    
    # 执行工具
    result = await registry.execute_tool(
        'search_properties',
        location="King's College",
        max_budget=1200
    )
    
    # 打印统计
    registry.print_stats()

asyncio.run(example2())
```

### 方式 3: 使用 Agent（完全自动化）

```python
import asyncio
from core.tool_system import create_tool_registry
from core.agent import Agent
from core.llm_interface import call_ollama

async def example3():
    # 初始化
    registry = create_tool_registry()
    agent = Agent(
        tool_registry=registry,
        llm_func=call_ollama,
        max_turns=5
    )
    
    # 运行代理
    result = await agent.run(
        "Find me a flat near UCL with less than 30 min commute to King's College"
    )
    
    # 获取结果
    if result['success']:
        print(f"✅ 完成！")
        print(f"最终答案: {result['final_answer']}")
    else:
        print(f"❌ 失败: {result['error']}")
    
    # 打印统计
    print(f"执行轮次: {result['turns']}")
    for obs in result['observations']:
        print(f"- {obs['tool_name']}: {'✅' if obs['success'] else '❌'}")

asyncio.run(example3())
```

---

## 📂 项目结构

```
local_data_demo/
├── core/
│   ├── __init__.py
│   ├── tool_system.py          # 核心系统（Tool, Registry, FunctionCalling）
│   ├── agent.py                # ReAct Agent 实现
│   ├── llm_interface.py        # LLM 接口（调用 Ollama）
│   ├── tools/                  # 工具集合
│   │   ├── __init__.py
│   │   ├── search_properties.py    # 房源搜索工具
│   │   ├── calculate_commute.py    # 通勤计算工具
│   │   ├── check_safety.py         # 安全检查工具
│   │   └── get_weather.py          # 天气获取工具
│   ├── data_loader.py          # 数据加载
│   ├── maps_service.py         # 地图服务
│   ├── location_service.py     # 位置服务
│   └── ... (其他支持模块)
│
├── test_agent.py               # Agent 测试脚本
├── app.py                      # Flask 应用
└── README_AGENT_SYSTEM.md      # 本文件
```

---

## 🧪 测试

### 运行测试脚本

```bash
cd local_data_demo
python test_agent.py
```

### 预期输出

```
══════════════════════════════════════════════════════════════
🚀 Agent 开始工作
══════════════════════════════════════════════════════════════
📝 用户问题: Find me a flat near UCL, budget £1500, max 30 min commute to King's College

══════════════════════════════════════════════════════════════
🤖 Function Calling: 询问 AI 选择工具
══════════════════════════════════════════════════════════════
📤 发送给 LLM...
📥 LLM 回复 (342 字符)
   ...
✅ AI 决定: use_tool
   工具: search_properties
   参数: {'location': 'UCL', 'max_budget': 1500}

🔧 第 1 步: 执行工具
   推理: 用户要找房子，需要先搜索符合预算要求的房源
   工具: search_properties
   参数: {'location': 'UCL', 'max_budget': 1500}
   ✅ 执行成功
   📊 找到 15 个结果

... (继续执行)

✅ 第 3 步: 任务完成
💡 最终答案:
根据您的需求，我找到了15个符合条件的房源...

══════════════════════════════════════════════════════════════
📊 执行结果
══════════════════════════════════════════════════════════════
✅ 成功
   最终答案: 根据您的需求，我找到了15个符合条件的房源...

📈 统计信息:
   - 执行轮次: 3
   - 工具调用: 2
   - 成功: 2
   - 失败: 0
   - 总耗时: 1250ms
```

---

## 🔄 工作流程详解

### ReAct 循环

```
┌─────────────────────────────┐
│   第1步：推理 (Reasoning)    │
│  AI分析用户问题，决定策略    │
└──────────┬──────────────────┘
           ↓
┌─────────────────────────────┐
│  第2步：行动 (Action)        │
│  AI选择一个工具来执行        │
└──────────┬──────────────────┘
           ↓
┌─────────────────────────────┐
│ 第3步：观察 (Observation)   │
│ 执行工具，获得结果            │
└──────────┬──────────────────┘
           ↓
┌─────────────────────────────┐
│  是否完成？                   │
│  - 完成 → 返回答案            │
│  - 继续 → 回到第1步           │
│  - 澄清 → 询问用户            │
└─────────────────────────────┘
```

### 示例：找房子的完整流程

```
用户: "Find me a flat near UCL, budget £1500, max 30 min commute"

↓ Agent 思考 ↓

第1轮：
- 推理: "用户要找房子，需要先搜索符合预算要求的房源"
- 行动: 调用 search_properties(location="UCL", max_budget=1500)
- 观察: 找到 15 个房源

第2轮：
- 推理: "用户要求通勤 < 30 分钟，需要计算每个房源的通勤时间"
- 行动: 调用 calculate_commute(from_address=property1, to_address="King's College")
- 观察: 通勤 25 分钟，符合要求

第3轮：
- 推理: "已经有足够信息回答用户"
- 行动: 完成任务
- 观察: 返回最终答案

结果: "我为您找到 8 个符合条件的房源..."
```

---

## 🎯 添加新工具

### 步骤 1: 创建工具文件

```python
# core/tools/my_new_tool.py

from core.tool_system import Tool

async def my_function_impl(param1: str, param2: int) -> dict:
    """实现你的功能"""
    result = do_something(param1, param2)
    return result

my_tool = Tool(
    name="my_tool_name",
    description="What does this tool do",
    func=my_function_impl,
    parameters={
        'type': 'object',
        'properties': {
            'param1': {'type': 'string', 'description': 'Parameter 1'},
            'param2': {'type': 'integer', 'description': 'Parameter 2'}
        },
        'required': ['param1', 'param2']
    }
)
```

### 步骤 2: 在 tools/__init__.py 中导出

```python
from core.tools.my_new_tool import my_tool

__all__ = [
    'search_properties_tool',
    'calculate_commute_tool',
    'check_safety_tool',
    'get_weather_tool',
    'my_tool'  # 添加这行
]
```

### 步骤 3: 在 create_tool_registry 中注册

```python
def create_tool_registry():
    from core.tools import (..., my_tool)
    
    registry = ToolRegistry()
    registry.register(search_properties_tool)
    # ... 其他工具 ...
    registry.register(my_tool)  # 添加这行
    
    return registry
```

---

## 🐛 调试技巧

### 1. 启用详细日志

```python
agent = Agent(
    tool_registry=registry,
    llm_func=llm,
    verbose=True  # 打印所有步骤
)
```

### 2. 查看工具统计

```python
registry.print_stats()
```

### 3. 检查 LLM 的原始回复

```python
decision = fc.ask_ai_to_choose_tool(user_query, llm)
print(decision)  # 查看完整的决策信息
```

### 4. 手动测试单个工具

```python
import asyncio
from core.tools import search_properties_tool

async def test():
    result = await search_properties_tool.execute(
        location="Test",
        max_budget=1500
    )
    print(result.to_dict())

asyncio.run(test())
```

---

## ⚙️ 配置 LLM

### 方式 1: 使用 Ollama（推荐，本地免费）

```python
from core.llm_interface import call_ollama

result = call_ollama("Your prompt here")
```

### 方式 2: 使用 Gemini

```python
from core.llm_interface import call_gemini

result = call_gemini("Your prompt here")
```

### 方式 3: 自定义 LLM

```python
def my_llm_func(prompt: str) -> str:
    # 你的 LLM 实现
    return response

agent = Agent(
    tool_registry=registry,
    llm_func=my_llm_func  # 传入自定义函数
)
```

---

## 📊 性能优化

### 1. 批量执行工具
```python
# 并行执行多个工具（需要修改 Agent）
results = await asyncio.gather(
    registry.execute_tool('tool1', ...),
    registry.execute_tool('tool2', ...)
)
```

### 2. 缓存结果
```python
# 可以在 Tool 中加入缓存
@functools.lru_cache(maxsize=100)
def get_cached_data(location):
    return ...
```

### 3. 限制工具调用次数
```python
agent = Agent(
    tool_registry=registry,
    llm_func=llm,
    max_turns=3  # 最多 3 轮
)
```

---

## 🎓 学习路径

1. **初级**: 使用现成的工具
   - 理解 Tool 的结构
   - 学会注册工具
   - 执行单个工具

2. **中级**: 创建新工具
   - 实现自己的工具函数
   - 定义参数 Schema
   - 处理错误和重试

3. **高级**: 优化 Agent
   - 改进 Prompt 设计
   - 实现工具链接逻辑
   - 性能优化和缓存

---

## 🤝 贡献

欢迎添加新工具！请遵循：

1. ✅ 实现函数（同步或异步）
2. ✅ 定义参数 Schema
3. ✅ 编写详细的描述
4. ✅ 添加错误处理
5. ✅ 编写测试代码

---

## 📞 常见问题

### Q: Agent 为什么没有调用我期望的工具？
A: 检查 LLM 的 Prompt。工具描述应该清晰、具体，帮助 LLM 做出正确决策。

### Q: 如何让 Agent 一次调用多个工具？
A: 修改 Agent 的决策逻辑，允许返回多个工具。目前实现是一次一个。

### Q: 如何处理工具执行失败？
A: Tool 会自动重试（max_retries），如果全部失败会返回错误。Agent 会根据错误决定下一步。

### Q: 可以离线使用吗？
A: 可以！使用 Ollama（本地模型）和本地数据即可完全离线。

---

## 📚 参考资源

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [LangChain 工具文档](https://python.langchain.com/docs/modules/tools/)

---

祝你使用愉快！🚀
