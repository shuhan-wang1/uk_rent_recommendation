# 🚀 快速开始 - Agent 系统

## 📋 你刚刚获得了什么

基于 `local_data_demo` 文件，我完整重写了整个工具系统，现在你拥有：

✅ **完整的 Agent 框架**
- Tool（工具定义）
- ToolRegistry（工具管理）
- FunctionCalling（AI 工具选择）
- Agent（ReAct 自动循环）

✅ **4 个现成的工具**
1. `search_properties` - 搜索房源
2. `calculate_commute` - 计算通勤时间
3. `check_safety` - 检查安全性
4. `get_weather` - 获取天气信息

✅ **智能自动化**
- AI 自动分析用户问题
- 自动选择合适的工具
- 自动执行工具
- 自动反馈和决策
- 支持多轮循环

---

## 🎯 三种使用方式

### 方式 1️⃣：直接使用单个工具（最简单）

```python
import asyncio
from core.tools import search_properties_tool

async def example():
    result = await search_properties_tool.execute(
        location="UCL",
        max_budget=1500
    )
    
    if result.success:
        print(f"✅ 找到 {result.data['count']} 个房源")
        for prop in result.data['properties'][:3]:
            print(f"  - {prop.get('address')}")
    else:
        print(f"❌ 错误: {result.error}")

asyncio.run(example())
```

---

### 方式 2️⃣：使用工具注册表（中等难度）

```python
import asyncio
from core.tool_system import create_tool_registry

async def example():
    # 初始化
    registry = create_tool_registry()
    
    # 顺序执行工具
    search_result = await registry.execute_tool(
        'search_properties',
        location="King's College",
        max_budget=1200
    )
    
    if search_result.success and search_result.data['properties']:
        first_property = search_result.data['properties'][0]
        
        # 计算通勤时间
        commute_result = await registry.execute_tool(
            'calculate_commute',
            from_address=first_property['address'],
            to_address="British Library"
        )
        
        if commute_result.success:
            print(f"✅ 通勤时间: {commute_result.data['duration_minutes']} 分钟")
    
    # 打印统计
    registry.print_stats()

asyncio.run(example())
```

---

### 方式 3️⃣：完全自动化 Agent（最强大）⭐

```python
import asyncio
from core.tool_system import create_tool_registry
from core.agent import Agent
from core.llm_interface import call_ollama

async def example():
    # 初始化
    registry = create_tool_registry()
    agent = Agent(
        tool_registry=registry,
        llm_func=call_ollama,
        max_turns=5,
        verbose=True
    )
    
    # 提问，Agent 自动处理
    result = await agent.run(
        "Find me a flat near UCL with less than 30 min commute to King's College"
    )
    
    # 得到答案
    if result['success']:
        print(f"\n✅ 完成！")
        print(f"最终答案:\n{result['final_answer']}")
    else:
        print(f"\n❌ 失败: {result['error']}")
    
    # 查看执行过程
    print(f"\n执行过程:")
    for i, obs in enumerate(result['observations'], 1):
        print(f"  {i}. {obs['tool_name']}: {'✅' if obs['success'] else '❌'}")

asyncio.run(example())
```

---

## 🧪 立即测试

### 运行完整测试

```bash
cd c:\Users\shuhan\Desktop\uk_rent_recommendation\local_data_demo

python test_agent.py
```

### 预期输出

你会看到 Agent 自动进行多轮推理和工具调用：

```
══════════════════════════════════════════════════════════════
🚀 Agent 开始工作
══════════════════════════════════════════════════════════════
📝 用户问题: Find me a flat near UCL, budget £1500, max 30 min commute

🤖 Function Calling: 询问 AI 选择工具
✅ AI 决定: use_tool
   工具: search_properties
   参数: {'location': 'UCL', 'max_budget': 1500}

🔧 第 1 步: 执行工具
   ✅ 执行成功
   📊 找到 15 个结果

...（继续执行）...

✅ 第 3 步: 任务完成
💡 最终答案:
根据您的需求，我为您找到了...

📊 执行结果
✅ 成功
📈 统计信息:
   - 执行轮次: 3
   - 工具调用: 2
   - 成功: 2
   - 失败: 0
   - 总耗时: 1250ms
```

---

## 📂 核心文件结构

```
local_data_demo/
├── core/
│   ├── tool_system.py              # ⭐ 核心系统（新）
│   ├── agent.py                    # ⭐ ReAct 循环（新）
│   ├── tools/                      # ⭐ 工具集合（新）
│   │   ├── search_properties.py    # 房源搜索
│   │   ├── calculate_commute.py    # 通勤计算
│   │   ├── check_safety.py         # 安全检查
│   │   └── get_weather.py          # 天气获取
│   └── ... (现有文件)
│
├── test_agent.py                   # ⭐ 测试脚本（新）
├── README_AGENT_SYSTEM.md          # ⭐ 完整文档（新）
├── QUICK_START_AGENT.md            # ⭐ 本文件（新）
└── app.py                          # Flask 应用（已更新）
```

---

## 🎓 核心概念

### 📌 1. 不再是固定流程！

**之前** ❌
```
用户 → 搜索房源 → 计算通勤 → 检查安全 → 完成
           ↑              ↑              ↑
        固定的流程顺序，没有智能决策
```

**现在** ✅
```
用户 → AI 思考 → AI 选择工具 → 执行 → AI 决定下一步
           ↑         ↑         ↑          ↑
        智能、灵活、自适应、自动化
```

### 📌 2. AI 智能决策

```python
# AI 根据不同的用户问题，自动选择不同的工具组合

用户 1: "Find a flat near UCL, budget £1500"
  → AI: 调用 search_properties

用户 2: "Is Bloomsbury safe?"
  → AI: 调用 check_safety

用户 3: "Find a flat near UCL with less than 30 min commute"
  → AI: 先调用 search_properties，再调用 calculate_commute，最后总结

用户 4: "Tell me about the weather in King's College"
  → AI: 调用 get_weather
```

### 📌 3. 标准化工具格式

```python
# 所有工具都遵循相同的格式
Tool(
    name="工具名",
    description="详细描述",
    func=执行函数,
    parameters=JSON_Schema  # OpenAI 标准格式
)

# 所有工具返回相同的格式
ToolResult(
    success=True,
    data={...},
    error=None,
    execution_time_ms=250,
    tool_name='tool_name'
)
```

---

## 🔧 常见操作

### 1️⃣ 添加新工具

```python
# 1. 创建 core/tools/my_tool.py
from core.tool_system import Tool

async def my_function(param: str):
    return {"result": ...}

my_tool = Tool(
    name="my_tool",
    description="What it does",
    func=my_function,
    parameters={...}
)

# 2. 在 core/tools/__init__.py 导出
from core.tools.my_tool import my_tool
__all__ = [..., 'my_tool']

# 3. 在 core/tool_system.py 注册
def create_tool_registry():
    from core.tools import (..., my_tool)
    registry = ToolRegistry()
    registry.register(my_tool)
    return registry
```

### 2️⃣ 修改工具行为

```python
# 增加重试次数
search_tool = Tool(
    name="search_properties",
    ...,
    max_retries=5  # 默认是 2
)

# 禁用重试
Tool(
    ...,
    retry_on_error=False
)

# 修改超时
Tool(
    ...,
    max_retries=1  # 快速失败
)
```

### 3️⃣ 自定义 LLM

```python
# 使用 Ollama（本地，免费）
from core.llm_interface import call_ollama
agent = Agent(tool_registry, llm_func=call_ollama)

# 使用 Gemini（云）
from core.llm_interface import call_gemini
agent = Agent(tool_registry, llm_func=call_gemini)

# 自定义
def my_llm(prompt: str) -> str:
    return "AI response"

agent = Agent(tool_registry, llm_func=my_llm)
```

### 4️⃣ 调试

```python
# 启用详细日志
agent = Agent(..., verbose=True)

# 查看工具统计
registry.print_stats()

# 查看单个结果
result = await tool.execute(...)
print(result.to_dict())

# 检查 LLM 原始回复
from core.tool_system import extract_json_from_text
decision = fc.ask_ai_to_choose_tool(...)
print(f"完整决策: {decision}")
```

---

## 📊 工具选择决策树

```
用户问题
  ├─ 提到"找房"？
  │  └─ 调用 search_properties
  │
  ├─ 提到"通勤"、"交通"、"多久"？
  │  └─ 调用 calculate_commute
  │
  ├─ 提到"安全"、"犯罪"？
  │  └─ 调用 check_safety
  │
  ├─ 提到"天气"、"气候"？
  │  └─ 调用 get_weather
  │
  ├─ 多个需求？
  │  └─ 循环执行多个工具
  │
  └─ 已有足够信息？
     └─ 完成，返回答案
```

---

## 🚀 下一步

### 短期任务
1. 运行 `test_agent.py` 验证系统
2. 尝试三种使用方式
3. 修改参数看效果

### 中期任务
1. 添加更多工具（餐厅、超市、公园等）
2. 优化 Prompt 使 AI 更聪明
3. 集成到 Flask 应用

### 长期任务
1. 添加会话记忆（对话上下文）
2. 实现工具链（A 的输出作为 B 的输入）
3. 性能优化和缓存
4. 用户界面改进

---

## 🎁 你获得的优势

| 功能 | 之前 | 现在 |
|------|------|------|
| 工具调用 | 手动、固定 | 自动、灵活 |
| 流程 | 线性、预定义 | 树形、自适应 |
| AI 参与度 | 低（只生成文本） | 高（决策 + 执行） |
| 错误处理 | 手动 | 自动重试 |
| 扩展性 | 困难 | 简单（标准格式） |
| 代码复用 | 低 | 高（标准化） |
| 可维护性 | 差 | 好（模块化） |

---

## 📞 常见问题

**Q: 为什么我的工具没有被调用？**
A: 检查：
1. 工具是否注册了？`registry.list_tool_names()`
2. 工具描述是否清晰？帮助 AI 理解何时使用
3. LLM 是否启动？`call_ollama("test")`

**Q: 如何让 Agent 执行更复杂的任务？**
A: 添加更多工具或改进 Prompt。看 `README_AGENT_SYSTEM.md` 的"添加新工具"部分。

**Q: 能在 Flask 应用中使用吗？**
A: 可以！需要处理异步。看 `app.py` 中的集成示例。

---

## 📚 详细文档

详见：`README_AGENT_SYSTEM.md`

---

## ✨ 总结

你现在拥有一个**完整、灵活、可扩展的 Agent 系统**！

- ✅ 智能工具选择
- ✅ 自动多轮循环
- ✅ 标准化工具格式
- ✅ 完善的错误处理
- ✅ 详细的日志和统计

**开始使用：** `python test_agent.py`

**需要帮助？** 看文档或添加 `verbose=True` 调试。

🚀 Happy coding!
