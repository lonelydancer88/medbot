# 问诊助手 (MedBot) 设计文档

## 概述

基于 LangGraph 的全科问诊助手，面向患者端，采用对话式交互，纯 LLM 驱动，输出初步诊断建议。

## 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | React + Vite + TypeScript | 生态成熟，与后端解耦 |
| 后端 | Python FastAPI | 原生 async，与 LangGraph 完美搭配 |
| 数据库 | SQLite + SQLModel | 零配置，后续可升 PostgreSQL |
| AI 编排 | LangGraph | 状态机驱动对话流 |
| LLM | Claude API (可配置) | 主驱动引擎 |

## 对话编排设计

### 方案选择：动态状态机

单一主循环节点 + 结构化 State，LLM 每轮根据已收集信息动态决定追问方向。在"对话自然度"和"实现复杂度"之间取得最佳平衡。

### State 设计

```python
class ConsultationState(TypedDict):
    # 会话信息
    session_id: str
    messages: list[dict]          # 完整对话历史 [{role, content}, ...]

    # 结构化医学信息
    chief_complaint: str           # 主诉
    symptoms: list[dict]           # [{"name": "咳嗽", "duration": "3天", "detail": "干咳无痰"}]
    associated_symptoms: list      # 伴随症状列表
    past_history: str              # 既往病史
    medication_history: str        # 用药史
    allergies: str                 # 过敏史

    # 流程控制
    phase: str                     # collecting / diagnosing / complete
    next_action: str               # ask_more / proceed_diagnosis
    diagnosis: dict                # 诊断结果（生成后填充）
```

### Graph 节点

```
[collect_chief_complaint] → [consultation_loop] ←→ [information_gather]
                                    ↓
                            [generate_diagnosis]
```

#### 1. collect_chief_complaint
- 入口节点，输出"请描述您的主要症状"
- 等待患者输入主诉，提取 chief_complaint 字段

#### 2. consultation_loop（核心循环）
- 接收患者消息后调用 LLM
- LLM 分析全部上下文，生成回复 + 决策
- **追问策略**：遵循临床逻辑链（症状细节 → 伴随症状 → 既往史 → 用药史）
- 每次只问 1-2 个问题
- 输出 JSON: `{response, next_action, info_gaps}`

#### 3. information_gather
- 不生成对话，只从最新对话中提取结构化字段
- 合并到 state.symptoms / state.past_history 等

#### 4. generate_diagnosis
- LLM 综合分析全部信息
- 输出：初步诊断列表（含可能性评级）+ 检查建议 + 就医建议 + 生活建议

### Graph 边路由

```python
def route_consultation(state):
    if state.next_action == "proceed_diagnosis":
        return "generate_diagnosis"
    return "information_gather"  # → 继续问
```

图中的条件边判断：如果 LLM 标记信息充足则进入诊断，否则收集信息后回到主循环。

### LLM Prompt 策略

| 节点 | Prompt 重点 |
|---|---|
| consultation_loop | 提供全部历史 + 已提取的结构化信息，让 LLM 做 informed decision |
| information_gather | 专注信息提取，使用独立的轻量 prompt，不参与对话 |
| generate_diagnosis | 综合分析，输出结构化诊断（含免责声明） |

## 后端 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/sessions | 创建新会话 |
| GET | /api/sessions/{id} | 获取会话 |
| POST | /api/sessions/{id}/chat | 发送消息，接收回复 |
| GET | /api/sessions | 历史会话列表 |

核心流程：
1. 从 DB 恢复 state
2. 追加患者消息
3. `graph.ainvoke(state)` 执行
4. 持久化 state 到 DB
5. 返回 AI 回复

## 前端

视图结构：
- 首页：开始新问诊 / 历史记录
- 对话页：聊天界面（主要界面）
- 诊断结果页：诊断报告展示

状态管理：sessionId, messages[], phase, loading

## 数据库 Schema（SQLite + SQLModel）

```sql
-- Session: 问诊会话
CREATE TABLE session (
    id TEXT PRIMARY KEY,          -- UUID
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    status TEXT,                  -- active / completed
    state_json TEXT,              -- ConsultationState 序列化
    phase TEXT                    -- 当前阶段
);

-- Message: 对话消息
CREATE TABLE message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES session(id),
    role TEXT,                    -- patient / ai
    content TEXT,
    created_at TIMESTAMP
);

-- Diagnosis: 诊断结果
CREATE TABLE diagnosis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES session(id),
    disease TEXT,
    probability TEXT,             -- 高/中/低
    reason TEXT,
    created_at TIMESTAMP
);
```

## 项目目录结构

```
medbot/
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── router.py                # API 路由
│   ├── langgraph/
│   │   ├── graph.py             # 图定义 + 边路由
│   │   ├── state.py             # State 类型定义
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── chief_complaint.py
│   │   │   ├── consultation_loop.py
│   │   │   ├── information_gather.py
│   │   │   └── diagnosis.py
│   │   └── prompts.py           # 所有 prompt 模板
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py            # SQLModel 定义
│   │   ├── database.py          # 引擎/会话管理
│   │   └── crud.py              # 增删改查
│   └── config.py                # LLM 配置
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── ChatView.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── DiagnosisCard.tsx
│   │   │   └── SessionList.tsx
│   │   └── types.ts
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── requirements.txt
└── CLAUDE.md
```

## 数据流

```
用户输入 → Frontend → POST /chat → Backend → graph.invoke()
  → consultation_loop (LLM 决定方向)
  → information_gather (提取结构化信息)
  → 循环直到信息充足 → generate_diagnosis
  → 持久化到 SQLite
  → 返回回复给 Frontend
```

## 设计决策记录

| 决策 | 选择 | 替代方案 |
|---|---|---|
| 对话架构 | 动态状态机（单一主循环） | 线性阶段机 / 分层Agent |
| 信息提取 | 独立 `information_gather` 节点 | 在对话节点内部分析 |
| 诊断触发 | LLM 自主判断 | 固定阶段触发 |
| 流式输出 | 初期非流式，后续升级 SSE | — |
| State 持久化 | 整体系列化存 state_json 列 | 完全关系型展开 |
