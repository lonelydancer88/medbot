# MedBot - 问诊助手

基于 LangGraph 的全科问诊助手，对话式交互，纯 LLM 驱动，输出初步诊断建议和结构化病历总结。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + Vite + TypeScript |
| 后端 | Python FastAPI |
| 数据库 | SQLite + SQLModel |
| AI 编排 | LangGraph 1.x |
| LLM | DeepSeek (Anthropic 兼容 API) / Claude |
| 流式通信 | SSE (text/event-stream) |

## 启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY

# 2. 后端
pip install -r requirements.txt
uvicorn backend.main:app --reload  # http://localhost:8000

# 3. 前端
cd frontend && npm install && npm run dev  # http://localhost:5173
```

或 `./start.sh` 一键启动前后端。

## 项目结构

```
medbot/
├── backend/
│   ├── main.py                    # FastAPI 入口 + CORS + /health
│   ├── router.py                  # API 路由 (5 endpoints)
│   ├── config.py                  # 环境配置 (API key, model, DB URL)
│   ├── db/
│   │   ├── models.py              # SQLModel: Session, Message, Diagnosis
│   │   ├── database.py            # SQLite 引擎 + init_db()
│   │   └── crud.py                # 8 个 CRUD 函数
│   ├── langgraph/
│   │   ├── state.py               # ConsultationState (15 字段, 含 Annotated reducer)
│   │   ├── graph.py               # 图定义 + 条件路由
│   │   ├── llm.py                 # LLM 调用 + JSON 解析 + 流式 generator
│   │   ├── prompts.py             # 5 个 prompt 模板
│   │   └── nodes/
│   │       ├── consultation_loop.py   # 核心对话节点 + build_consultation_prompt()
│   │       ├── information_gather.py  # 结构化信息提取 (年龄/性别/症状等)
│   │       ├── diagnosis.py           # 诊断生成 (JSON → markdown 卡片)
│   │       └── medical_record.py      # 病历总结 (markdown)
│   └── tests/
│       ├── test_graph.py           # 13 tests (mock LLM)
│       └── test_api.py             # API endpoint tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # URL 路由 (无 react-router), popstate 监听
│   │   ├── api/client.ts          # API 客户端 + SSE 流式消费
│   │   ├── types.ts               # 15 TypeScript 类型/接口
│   │   └── components/
│   │       ├── ChatView.tsx         # 聊天界面, 流式回调, session 管理
│   │       ├── MessageBubble.tsx    # 消息气泡 + 思考面板 (流式时自动展开)
│   │       ├── DiagnosisCard.tsx    # 诊断卡片 (黄色, 概率标签)
│   │       ├── MedicalRecordCard.tsx # 病历总结卡片 (绿色)
│   │       └── SessionList.tsx      # 历史记录 + 复制链接
│   └── vite.config.ts              # 开发代理 /api → :8000
├── start.sh                      # 一键启动脚本
├── .env.example
└── requirements.txt
```

## 对话编排（LangGraph）

每次 `graph.invoke()` 处理一轮患者输入，输出一个 AI 回复：

```
consultation_loop (AI 回复 + 决策: ask_more / proceed_diagnosis)
    → information_gather (提取结构化信息)
    → END (等待下一轮输入)
      或 → generate_diagnosis (诊断分析)
           → generate_medical_record (病历总结)
           → END
```

**SSE 流式端点** 绕过 LangGraph，直接控制 LLM stream，流结束后手动调用 information_gather / generate_diagnosis / generate_medical_record 节点函数。

### State 字段 (`ConsultationState`)

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | `str` | 会话 UUID |
| `messages` | `Annotated[list, operator.add]` | 对话历史 (自动追加) |
| `age` | `str` | 年龄 |
| `gender` | `str` | 性别 |
| `pregnancy` | `str` | 是否怀孕 (yes/no/unknown，仅女性 18-50) |
| `chief_complaint` | `str` | 主诉 |
| `symptoms` | `Annotated[list, operator.add]` | 症状列表 `[{name, duration, detail}]` |
| `associated_symptoms` | `Annotated[list, operator.add]` | 伴随症状 |
| `past_history` | `str` | 既往病史 |
| `medication_history` | `str` | 用药史 |
| `allergies` | `str` | 过敏史 |
| `phase` | `str` | collecting / diagnosing / complete |
| `next_action` | `str` | ask_more / proceed_diagnosis |
| `diagnosis` | `dict` | LLM 诊断 JSON |
| `medical_record` | `str` | LLM 病历总结 (markdown) |
| `thinking` | `str` | 当前轮 LLM 思考过程 |

### 节点职责

| 节点 | 函数 | 职责 | LLM |
|---|---|---|---|
| `consultation_loop` | `consultation_loop(state)` | 生成 AI 回复 + 决定追问/诊断，首次返回硬编码问候语 | ✅ |
| `information_gather` | `information_gather(state)` | 从对话提取年龄/性别/怀孕/症状等结构化字段 | ✅ |
| `generate_diagnosis` | `generate_diagnosis(state)` | 综合分析输出诊断 + 检查/就医/生活建议 | ✅ |
| `generate_medical_record` | `generate_medical_record(state)` | 生成结构化病历总结：基本信息、主诉、现病史、既往史、诊断、挂号科室、处理建议 | ✅ |

### Prompt 模板

| 常量 | 占位符 | 输出 |
|---|---|---|
| `CONSULTATION_LOOP_PROMPT` | `{history}`, `{structured_info}` | JSON `{response, next_action, info_gaps}` |
| `INFORMATION_GATHER_PROMPT` | `{latest_exchange}`, `{current_info}` | JSON 结构化提取 |
| `DIAGNOSIS_PROMPT` | `{all_info}` | JSON `{diagnoses[], suggested_exams[], referral_advice, ...}` |
| `MEDICAL_RECORD_PROMPT` | `{conversation}`, `{all_info}`, `{diagnosis}` | Markdown 病历文本 |

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/sessions` | 创建新会话，返回初始 greeting |
| POST | `/api/sessions/{id}/chat` | 同步发送消息 (非流式) |
| POST | `/api/sessions/{id}/chat/stream` | **流式**发送消息 (SSE: thinking / text / done / diagnosis / medical_record / phase / error) |
| GET | `/api/sessions/{id}` | 获取会话详情 (含 messages, diagnoses, medical_record) |
| GET | `/api/sessions` | 历史会话列表 (按 updated_at 倒序) |

### SSE 事件类型 (stream 端点)

| event | data | 时机 |
|---|---|---|
| `thinking` | `"增量文本"` | LLM 输出 thinking 块 |
| `text` | `"增量文本"` | LLM 输出 text 块 |
| `done` | `{text, thinking}` | LLM 流结束，clean text |
| `diagnosis` | `{diagnoses, content}` | 诊断生成完成 |
| `medical_record` | `{content, thinking}` | 病历总结生成完成 |
| `phase` | `{phase, is_complete}` | 全部处理完成 |
| `error` | `"错误信息"` | 任意阶段出错 |

## 前端路由

基于 `window.location.pathname` + `pushState` + `popstate`（无 React Router）：

| URL | 视图 | 行为 |
|---|---|---|
| `/` | 聊天 | 新会话 (sessionId=null, key='new') |
| `/sessions` | 历史列表 | 展示 SessionList |
| `/sessions/{uuid}` | 聊天 | 加载已有会话 (key=sessionId 强制 remount) |

## 测试

```bash
# 单元测试 (mock LLM, 无需 API key)
python -m pytest backend/tests/ -v

# 前端类型检查
cd frontend && npx tsc --noEmit
```

## 关键设计决策

- **流式绕过 LangGraph** — LangGraph invoke 不支持中间 token 推送，流式端点直接控制 LLM stream，结束后手动调节点函数做后处理
- **content blocks** — DeepSeek 返回 `thinking` + `text` 多块内容，`_extract_content_blocks()` 和 `_extract_chunk_delta()` 分别处理同步/流式场景
- **JSON fallback** — LLM 偶尔不输出纯 JSON，`_parse_json_lenient()` 降级为 `{"response": text, "next_action": "ask_more"}`
- **思考面板** — 流式期间自动展开，结束后用户可手动折叠
- **年龄/性别/怀孕** — 首先询问，女性 18-50 岁必须确认怀孕状态后才进入诊断
- **结束信号** — 患者说"没有了""就这些""可以了"等时立即进入诊断，不问"要不要我分析"
