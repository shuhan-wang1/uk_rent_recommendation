# Agent Framework Overview
This project follows a **five-layer Agent architecture**, designed to separate reasoning, workflow control, and capability execution.

## Architecture Overview
┌──────────────────────────────────────────────┐
│ 🤖 5️⃣ Agent Logic Layer (ReAct / CoT / Auto)  ← Decision Layer: reasoning, planning, and workflow selection
├──────────────────────────────────────────────┤
│ ⚙️ 4️⃣ Workflow / Orchestration Layer          ← Process Layer: combines multiple tools to complete complex tasks
├──────────────────────────────────────────────┤
│ 🧱 3️⃣ Tool System / Capability Layer          ← Capability Layer: encapsulates atomic abilities (APIs, models, functions)
├──────────────────────────────────────────────┤
│ 💾 2️⃣ Memory / Knowledge Layer                ← Memory Layer: stores context, history, and external knowledge
├──────────────────────────────────────────────┤
│ 🧩 1️⃣ Data / Environment Layer                ← Environment Layer: handles I/O and interaction with the external world
└──────────────────────────────────────────────┘

## Description of each layer
### Data / Environment Layer
它负责为Agent提供真实世界的信息来源和外部交互能力, 为上层Tool，Workflow，Agent建立基础
这一层通常负责:
提供外部API接口(例如天气、地图、数据库、AI模型等)
管理数据的读写、加载、存储
管理环境配置(API Key, 路径, 系统参数等)
记录底层日志或错误信息(用于调试与监控)

### Memory / Knowledge Layer
Memory Layer 负责记录、组织和检索交互历史或中间经验，使Agent拥有长期上下文理解能力
这一层的核心目标:
让Agent记得自己做过什么
让Agent能利用过去的经验优化当前行为

| 类型 | 功能 | 示例 |
|------|------|------|
| 🕐 **短期记忆（Short-term Memory）** | 存储当前任务或对话上下文 | 对话历史、最近调用的 Tool 结果、当前 session cache |
| 🧠 **长期记忆（Long-term Memory）** | 存储过去任务结果或长期知识 | 用户偏好、房源推荐记录、已完成任务列表 |
| 🔁 **工作记忆（Working Memory）** | 临时存储中间计算结果，辅助思考 | CoT reasoning 中的中间推理链 |

Knowledge Layer 让Agent拥有堆世界的理解能力
它负责组织、存储和检索外部知识(facts/documents/embeddings)
使Agent能基于事实回答问题或生成推理

| 功能类型 | 说明 | 示例 |
|-----------|------|------|
| 🧩 **知识检索（Retrieval）** | 从外部知识库中搜索相关信息 | 向量检索、全文搜索、RAG |
| 🧠 **知识存储（Knowledge Base）** | 组织世界知识或专业文档 | 房源数据、地理数据、用户文档 |
| 📘 **知识更新与版本控制** | 动态添加或修改知识内容 | 自动同步最新数据或模型文档 |

主要两部分数据，结构化数据和非结构化数据
| 数据类型 | 存储方式 | 检索方式 | 应用场景 |
|-----------|------------|------------|------------|
| 🧩 **结构化数据** | SQL / Pandas DataFrame / JSON | SQL 语句、逻辑过滤 | 房源筛选、计算通勤时间、平均租金 |
| 📄 **非结构化数据** | 向量数据库（ChromaDB / FAISS） | 语义相似度检索 | 文本描述匹配、自然语言问答、推荐解释 |

RAG是由“检索”与“生成”两部分组成的框架
其中检索阶段可以包括结构化查询(如SQL)和语义向量检索(如FAISS/ChromaDB), 它们共同提供外部知识给语言模型使用
然后模型在生成阶段融合这些知识，产出新的、上下文相关的内容

### Tool System / Capability Layer
Tool system定义Agent能做什么，每个tool是一个具体功能模块，可以被调用来完成特定任务

一个tool一般由五个核心部分组成:
| 部分 | 作用 | 示例（通俗解释） |
|------|------|----------------|
| 🧩 **name** | 工具名，标识这个工具 | `"GoogleMapsTool"` |
| 🧠 **description** | 告诉 LLM 这个工具是干什么的 | `"计算两个地址间的步行或通勤时间"` |
| ⚙️ **args_schema** | 定义输入参数（类型、格式） | `{origin: str, destination: str}` |
| 🔧 **function (execute)** | 工具的实际执行逻辑 | Python 代码实现 |
| 📤 **return value** | 工具的输出结果 | 字符串、JSON、DataFrame等 |

### Workflow Layer
定义了Agent完成一个复杂任务所需的步骤、顺序和依赖关系

核心功能与作用
| 功能 | 说明 | 项目示例 |
|------|------|-----------|
| 🧩 **定义任务流程** | 指定各步骤的执行顺序和依赖关系 | 先获取房源 → 再计算通勤时间 → 再评估安全性 |
| ⚙️ **调度能力（调用 Capability）** | 根据任务步骤调用对应的能力模块 | 调用 “地理计算能力” “安全评分能力” |
| 🔄 **自动数据传递** | 将上一步的输出作为下一步输入 | 房源列表 → 传递给地理计算模块 |
| 📈 **支持条件分支或并行** | 根据条件执行不同流程 | 如果用户指定区域 → 跳过地理计算 |
| 🧠 **可被上层 ReAct 控制** | ReAct 可以决定执行哪个 workflow | “房源推荐流程”“价格预测流程”等 |

### Agent Logic Layer
是Agent的大脑，负责理解任务、规划行为，并动态选择要执行的workflow或tool

| 功能 | 说明 | 项目示例 |
|------|------|-----------|
| 🧠 **任务理解与意图识别** | 分析用户输入，理解任务目标 | 识别 “找房需求” vs “价格预测” |
| 🗺️ **任务规划与分解** | 将复杂任务拆解为子任务 | 解析为 “房源检索 → 通勤计算 → 安全评估” |
| ⚙️ **动态选择 Workflow / Tool** | 决定调用哪个流程或工具 | 判断执行 “房源推荐流程” 还是调用 “租金统计工具” |
| 🔁 **推理-行动循环（Reasoning–Acting Loop）** | 结合思考与行动的闭环机制 | LLM 思考下一步 → 调用工具 → 根据结果再推理 |
| 🧾 **生成最终答案** | 整合多次推理与结果，形成自然语言输出 | 输出推荐解释：“这套房更安全且通勤时间短” |




## Project Structure
src/
├── environment/                 ← 🌐 外部世界：API 客户端、配置
│   ├── api_clients/
│   │   ├── google_client.py
│   │   ├── rightmove_client.py
│   │   ├── gov_safety_client.py
│   │   └── openai_client.py
│   └── config/
│       └── api_keys.yaml
│
├── tools/                       ← 🧱 工具层：封装这些 API
│   ├── google_maps_tool.py
│   ├── rightmove_tool.py
│   ├── openai_summary_tool.py
│   └── gov_safety_tool.py
│
├── workflows/                   ← ⚙️ 任务流层
│   ├── rent_analysis_workflow.py
│   └── property_summary_workflow.py
│
└── agent_logic/                 ← 🤖 推理层（ReAct / CoT）
    └── rent_agent_controller.py
