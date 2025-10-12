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
│ 💾 2️⃣ Memory & Knowledge Layer                ← Memory Layer: stores context, history, and external knowledge
├──────────────────────────────────────────────┤
│ 🧩 1️⃣ Data / Environment Layer                ← Environment Layer: handles I/O and interaction with the external world
└──────────────────────────────────────────────┘

## Description of each layer
### Data / Environment Layer






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
