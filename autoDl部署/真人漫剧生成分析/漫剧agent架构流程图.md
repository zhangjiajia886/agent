# 漫剧 Agent 系统架构流程图

> 基于 `/Users/zjj/home/learn26/ttsapp` 代码库实际分析  
> 生成时间：2026-04-28

---

## 一、整体架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          前端 (Vue 3 + Element Plus)                     │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────────────┐ │
│  │ ComicAgentView │  │ comic-agent  │  │  ComicAgentWS (WebSocket)    │ │
│  │   .vue 页面    │──│   .ts API    │──│  连接 / 发送消息 / 接收事件  │ │
│  │  对话 + 配置   │  │  REST 封装   │  │  AgentEvent 流式消费         │ │
│  └────────────────┘  └──────────────┘  └──────────────────────────────┘ │
└──────────────────────────────┬───────────────────────┬──────────────────┘
                               │ HTTP REST             │ WebSocket
                       ┌───────▼───────┐       ┌───────▼───────┐
                       │ Vite Proxy    │       │ Vite Proxy    │
                       │ /api → :8000  │       │ ws:true       │
                       └───────┬───────┘       └───────┬───────┘
                               │                       │
┌──────────────────────────────▼───────────────────────▼──────────────────┐
│                       后端 (FastAPI + SQLAlchemy Async)                  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                    API 路由层 (api/v1/comic_agent.py)               ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ││
│  │  │ /models  │ │ /tools   │ │/workflows│ │/convs    │ │/ws/chat  │ ││
│  │  │ CRUD     │ │ CRUD     │ │ CRUD     │ │ CRUD     │ │ WebSocket│ ││
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────┬─────┘ ││
│  └───────────────────────────────────────────────────────────┬┘       ││
│                                                              │        ││
│  ┌───────────────────────────────────────────────────────────▼───────┐││
│  │                 Agent 核心层 (core/)                               │││
│  │                                                                   │││
│  │  ┌─────────────────────┐     ┌────────────────────────────────┐   │││
│  │  │ comic_chat_agent/   │     │ comic_agent/                   │   │││
│  │  │  ┌────────────────┐ │     │  ┌──────────────┐              │   │││
│  │  │  │ smart_agent.py │ │     │  │ agent.py     │──ComicAgent  │   │││
│  │  │  │ (意图分发 +    │ │     │  │  generate()  │  编排引擎    │   │││
│  │  │  │  Mock 工具链)  │ │     │  │  edit_image()│              │   │││
│  │  │  ├────────────────┤ │     │  │  animate()   │              │   │││
│  │  │  │ mock_agent.py  │ │     │  │  t2v()       │              │   │││
│  │  │  │ (纯 Mock 模式) │ │     │  │  upscale()   │              │   │││
│  │  │  └────────────────┘ │     │  └──────┬───────┘              │   │││
│  │  └─────────────────────┘     │         │                      │   │││
│  │                              │  ┌──────▼───────┐              │   │││
│  │                              │  │intent_parser │← LLM         │   │││
│  │                              │  │story_planner │← LLM         │   │││
│  │                              │  │prompt_builder│← LLM         │   │││
│  │                              │  └──────┬───────┘              │   │││
│  │                              │  ┌──────▼────────────────┐     │   │││
│  │                              │  │workflow_selector.py   │     │   │││
│  │                              │  │  select_workflow()    │     │   │││
│  │                              │  │  inject_params()      │     │   │││
│  │                              │  ├──────────────────────┤     │   │││
│  │                              │  │workflow_registry.py   │     │   │││
│  │                              │  │  scan_all()           │     │   │││
│  │                              │  │  load_by_name()       │     │   │││
│  │                              │  └──────┬───────────────┘     │   │││
│  │                              │  ┌──────▼───────┐              │   │││
│  │                              │  │ workflows/   │ 40+ JSON     │   │││
│  │                              │  │ Flux / Wan / │ ComfyUI      │   │││
│  │                              │  │ Qwen / LTX2  │ 工作流文件   │   │││
│  │                              │  └──────────────┘              │   │││
│  │                              └────────────────────────────────┘   │││
│  │                                                                   │││
│  │  ┌─────────────────────┐  ┌─────────────────────┐                │││
│  │  │ llm_client.py       │  │ comfyui_client.py    │                │││
│  │  │ SouthgridLLMClient  │  │ ComfyUIClient        │                │││
│  │  │  chat() / stream()  │  │  submit / wait /     │                │││
│  │  │  HMAC-SHA256 签名   │  │  upload / download   │                │││
│  │  └─────────┬───────────┘  └─────────┬────────────┘                │││
│  └────────────┼────────────────────────┼─────────────────────────────┘││
│               │                        │                              ││
│  ┌────────────▼────────────────────────▼─────────────────────────────┐││
│  │                    数据层 (MySQL + SQLAlchemy Async ORM)           │││
│  │  ┌──────────────┐ ┌───────────────┐ ┌────────────────┐           │││
│  │  │ model_config │ │ tool_registry │ │workflow_template│           │││
│  │  │ 21 条记录    │ │ 8 条记录      │ │ ~40 条记录     │           │││
│  │  ├──────────────┤ ├───────────────┤ ├────────────────┤           │││
│  │  │agent_convers │ │ agent_message │ │ comic_tasks    │           │││
│  │  │ ation        │ │               │ │ (HTTP API)     │           │││
│  │  └──────────────┘ └───────────────┘ └────────────────┘           │││
│  └───────────────────────────────────────────────────────────────────┘││
└──────────────────────────────────────────────────────────────────────┘│
                               │                        │
                    ┌──────────▼──────────┐  ┌──────────▼──────────┐
                    │  南格 AI 网关        │  │  ComfyUI (AutoDL)   │
                    │  192.168.0.246:5030  │  │  RTX 5090 GPU       │
                    │  ┌────────────────┐  │  │  ┌───────────────┐  │
                    │  │ Qwen3-32B      │  │  │  │ 40+ 工作流    │  │
                    │  │ qwen2.5-3b     │  │  │  │ Flux/Wan/LTX2 │  │
                    │  │ Qwen3-VL       │  │  │  │ 各类 LoRA     │  │
                    │  │ bge-m3         │  │  │  └───────────────┘  │
                    │  └────────────────┘  │  └─────────────────────┘
                    └─────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  AIPro 聚合平台      │
                    │  vip.aipro.love/v1   │
                    │  ┌────────────────┐  │
                    │  │ Claude 4.x     │  │
                    │  │ GPT 5.x        │  │
                    │  │ Gemini 3.x     │  │
                    │  │ (16 个模型)    │  │
                    │  └────────────────┘  │
                    └─────────────────────┘
```

---

## 二、分层详细解析

### 2.1 前端层 — 对话交互界面

| 组件 | 文件 | 职责 |
|------|------|------|
| **ComicAgentView.vue** | `frontend/src/views/comic-agent/` | 对话页面：消息流、工具卡片、图片/视频内联、思考气泡、配置抽屉 |
| **comic-agent.ts** | `frontend/src/api/` | API 封装：REST (models/tools/workflows/conversations) + WebSocket (`ComicAgentWS`) |
| **request.ts** | `frontend/src/api/` | Axios 实例：`baseURL=/api`，拦截器添加 JWT Token |

**数据流：**
```
用户输入 → ComicAgentWS.send(message, {style, frames, model})
         → WebSocket /api/v1/comic-agent/ws/chat
         → 后端 smart_agent_stream() 逐事件 yield
         → ws.onmessage → 逐事件渲染到消息流
```

**事件类型协议：**
| 事件 | 方向 | 说明 |
|------|------|------|
| `thinking` | 后端→前端 | Agent 思考过程（意图识别/规划） |
| `text` | 后端→前端 | Agent 文字回复 |
| `tool_start` | 后端→前端 | 工具开始执行（附 tool + input） |
| `tool_done` | 后端→前端 | 工具执行完成（附 result + image_url） |
| `error` | 后端→前端 | 错误信息 |
| `done` | 后端→前端 | 本轮对话完成 |
| `conversation_created` | 后端→前端 | 新会话创建（附 conversation_id） |

### 2.2 API 路由层

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/comic-agent/models` | GET/PUT | 模型服务 CRUD（21个：南格4 + ComfyUI + AIPro 16） |
| `/api/v1/comic-agent/tools` | GET/PUT | 工具注册 CRUD（8个） |
| `/api/v1/comic-agent/workflows` | GET/PUT | 工作流模板 CRUD（~40个，自动扫描） |
| `/api/v1/comic-agent/conversations` | GET/POST/DELETE | 会话管理 |
| `/api/v1/comic-agent/ws/chat` | WebSocket | 流式 Agent 对话 |
| `/api/v1/comic/generate` | POST | HTTP 漫剧生成（非 Agent，直接执行） |
| `/api/v1/comic/tasks/{id}` | GET | 任务状态查询 |

### 2.3 Agent 核心层（双路径架构）

系统存在 **两条独立的执行路径**：

```
路径 A：WebSocket Agent 对话（前端 Agent 页面）
──────────────────────────────────────────────
用户消息 → websocket_agent_chat()
         → smart_agent_stream()          ← 基于关键词的意图分发
           ├─ chat: 直接文字回复
           ├─ t2i:  模拟工具调用 (picsum 占位图)
           ├─ comic: 模拟多格生成 (picsum 占位图)
           ├─ t2v:  模拟视频生成
           ├─ i2v:  提示上传图片
           ├─ edit: 提示上传图片
           └─ upscale: 提示上传图片
         → 保存消息到 agent_message 表
         → 发送 done 事件

路径 B：HTTP 漫剧生成（前端漫剧页面）
──────────────────────────────────────────────
POST /comic/generate → BackgroundTask
  → comic_agent.generate(ComicRequest)
    → intent_parser.parse_intent()     ← LLM 调用
    → story_planner.plan_storyboard()  ← LLM 调用
    → prompt_builder.build_all_prompts()← LLM 调用
    → workflow_selector.select_workflow()
    → comfyui_client.run_workflow()    ← GPU 执行
  → 保存结果到 comic_tasks 表
前端轮询 GET /comic/tasks/{id}
```

### 2.4 Smart Agent 意图分发引擎

```python
# smart_agent.py 意图检测逻辑（关键词匹配）
_INTENT_KW = [
    ("upscale", ["超分", "放大图", "高清放大", ...]),
    ("edit",    ["编辑图片", "修改图片", ...]),
    ("i2v",     ["图生视频", "动起来", ...]),
    ("t2v",     ["文生视频", "生成视频", ...]),
    ("t2i",     ["生成图片", "画一张", ...]),
    ("comic",   ["漫剧", "漫画", "故事", ...]),
    ("chat",    ["你好", "hello", ...]),
]
# 如果以上都不匹配且长度 > 10 → 默认 "comic"
```

```
意图识别  ───→  风格检测  ───→  工作流路由  ───→  Mock 生成
(关键词)       (关键词)       (硬编码映射)      (picsum占位)
```

### 2.5 ComicAgent 管线（HTTP 路径）

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ IntentParser │────→│ StoryPlanner │────→│ PromptBuilder│
│ 解析 JSON    │     │ 规划分镜文本 │     │ 生成英文提示 │
│ style/story/ │     │ [格1, 格2..] │     │ (pos, neg)   │
│ mood/face    │     │              │     │              │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │ LLM                │ LLM                │ LLM
       │ (qwen2.5-3b)       │ (qwen2.5-3b)       │ (qwen2.5-3b)
       ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│WorkflowSelect│────→│InjectParams  │────→│ ComfyUI GPU  │
│ 风格+人脸    │     │ prompt/seed/ │     │ submit_workflow│
│ → 工作流名   │     │ lora/image   │     │ wait_result   │
│              │     │              │     │ download_output│
└──────────────┘     └──────────────┘     └──────────────┘
```

### 2.6 外部服务层

| 服务 | 地址 | 用途 | 认证方式 |
|------|------|------|----------|
| **南格 AI 网关** | `192.168.0.246:5030` | Qwen3-32B / qwen2.5-3b / Qwen3-VL / bge-m3 | HMAC-SHA256 签名 |
| **AIPro 聚合** | `vip.aipro.love/v1` | Claude/GPT/Gemini 16 个模型 | Bearer API Key |
| **ComfyUI GPU** | AutoDL RTX 5090 | 图像/视频生成（40+ 工作流） | 无认证 |
| **Fish Audio** | `api.fish.audio` | TTS 语音合成 | API Key |
| **Soul AI Lab** | AutoDL 多实例 | FlashHead/Podcast/Singer | HF Token |

### 2.7 数据层

```
┌────────────────────────────────────────────────────────────┐
│                    MySQL (ttsapp 数据库)                     │
│                                                             │
│  ┌─────────────────┐  ┌──────────────────┐                 │
│  │  model_config   │  │  tool_registry   │  Agent 配置      │
│  │  21 models      │  │  8 tools         │                  │
│  │  (AIPro auto)   │  │                  │                  │
│  ├─────────────────┤  ├──────────────────┤                 │
│  │workflow_template│  │agent_conversation│  Agent 运行时     │
│  │  ~40 workflows  │  │agent_message     │                  │
│  │  (scan auto)    │  │                  │                  │
│  ├─────────────────┤  ├──────────────────┤                 │
│  │  comic_tasks    │  │  users           │  通用             │
│  │  (HTTP 任务)    │  │  voice_models    │                  │
│  └─────────────────┘  └──────────────────┘                 │
└────────────────────────────────────────────────────────────┘
```

---

## 三、请求完整链路追踪

### 3.1 WebSocket Agent 对话（用户说 "仙侠4格漫剧，剑客踏雪而来"）

```
1. 前端 ComicAgentWS.connect()
   → ws://localhost:3000/api/v1/comic-agent/ws/chat?token=xxx
   → Vite proxy → ws://localhost:8000/api/v1/comic-agent/ws/chat

2. 后端 websocket_agent_chat()
   → verify_token(token)              → user_id
   → 创建 AgentConversation           → conv_id
   → send_json({type: "conversation_created"})

3. 前端 ComicAgentWS.send("仙侠4格漫剧，剑客踏雪而来")

4. 后端接收消息
   → 保存 AgentMessage(role=user)
   → smart_agent_stream(message, style, frames)

5. SmartAgent 处理流
   → _detect_intent("仙侠4格漫剧...") = "comic"  (匹配 "漫剧")
   → _detect_style() = "xianxia"                   (匹配 "仙侠")
   → _detect_frames() = 4                           (匹配 "4格")
   → yield {type: "thinking", content: "🔍 意图：漫剧生成..."}
   → yield {type: "text", content: "开始生成 **仙侠古风** 4 格漫剧"}
   → for i in 0..3:
       yield {type: "tool_start", tool: "generate_image", input: {prompt, style}}
       yield {type: "tool_done", tool: "generate_image",
              image_url: "https://picsum.photos/seed/xxx/768/768"}  ← Mock!
   → yield {type: "text", content: "🎉 4格仙侠古风漫剧生成完毕！"}

6. 后端保存 AgentMessage(role=assistant, tool_calls=[...])
   → send_json({type: "done"})

7. 前端逐事件渲染
   → thinking → 思考气泡
   → text → Markdown 渲染
   → tool_start → 工具进度卡片（转圈 Loading）
   → tool_done → 图片缩略图 + 耗时
```

### 3.2 HTTP 漫剧生成（POST /comic/generate）

```
1. POST /api/v1/comic/generate {description, style, num_frames, face_image}

2. 创建 ComicTask(status=processing) → 返回 task_id

3. BackgroundTask 启动 comic_agent.generate()
   → IntentParser: LLM(qwen2.5-3b) → {style, story, mood, need_face}
   → StoryPlanner: LLM(qwen2.5-3b) → [格1描述, 格2描述, ...]
   → PromptBuilder: LLM(qwen2.5-3b) × N → [(pos, neg), ...]
   → WorkflowSelector: select_workflow(style, need_face) → workflow_name
   → if need_face: comfyui.upload_image(face) → face_filename
   → for each frame:
       load_workflow → inject_params → comfyui.run_workflow()
   → 保存结果图到 uploads/
   → 更新 ComicTask(status=completed, frame_urls=[...])

4. 前端轮询 GET /comic/tasks/{task_id} 直到 completed/failed
```

---

## 四、当前系统各模块评估

### 4.1 已完成（✅）

| 能力 | 状态 | 说明 |
|------|------|------|
| 前端对话界面 | ✅ 完成 | 消息流、工具卡片、图片内联、思考气泡、Markdown 渲染 |
| 配置管理 UI | ✅ 完成 | 工具/模型/工作流的启用/禁用管理 |
| WebSocket 对话通道 | ✅ 完成 | 鉴权、会话管理、消息持久化 |
| 模型自动发现 | ✅ 完成 | 启动时从 AIPro `/v1/models` 自动拉取 16 个模型 |
| 工作流自动扫描 | ✅ 完成 | 扫描 workflows/ 目录，自动分类入库 |
| ComfyUI 客户端 | ✅ 完成 | 提交/等待/下载/上传，支持图片和视频 |
| LLM 客户端 | ✅ 完成 | 南格 HMAC 签名 + 流式/非流式调用 |
| 数据库持久化 | ✅ 完成 | 模型/工具/工作流/会话/消息全量持久化 |
| ComicAgent 管线 | ✅ 完成 | 意图→分镜→提示词→工作流→GPU 生成 |

### 4.2 Mock 中（⚠️ 需升级）

| 模块 | 当前状态 | 问题 |
|------|----------|------|
| **SmartAgent 意图分发** | 关键词匹配 | 非 LLM 驱动，无法理解复杂/模糊意图 |
| **工具调用** | picsum 占位图 | 未真正调用 ComfyUI，生成的是随机网络图片 |
| **文生视频 / 图生视频** | 纯 Mock | 仅模拟延迟，无真实视频输出 |
| **图像编辑 / 超分** | 提示上传 | 未实现图片上传 + 编辑调用 |
| **多轮上下文** | 无状态 | 每轮独立处理，无历史对话感知 |
| **模型选择** | 未接入 | 前端可选模型，但后端 SmartAgent 未使用 |

### 4.3 缺失（❌ 需实现）

| 能力 | 说明 |
|------|------|
| **真正的 LLM Agent Loop** | 缺少 Claude/GPT 驱动的 ReAct 循环 |
| **Tool Use (Function Calling)** | 未接入 Claude/GPT 的 tool_use API |
| **图片上传到对话** | 前端无图片上传组件，后端无附件处理 |
| **实时 GPU 生成** | Agent 路径未调用 ComfyUI，仅 HTTP 路径调用 |
| **流式文字输出** | 文字一次性返回，非逐 token 流式 |
| **会话历史恢复** | 刷新页面后对话丢失，未从 DB 加载历史 |
| **进度/取消** | 长任务无进度反馈，不可取消 |
| **错误重试** | 工具失败后无自动重试机制 |
| **Memory / RAG** | 无长期记忆和知识检索增强 |
| **多 Agent 协作** | 单 Agent，无 Planner/Executor/Critic 分工 |

---

## 五、与一流 Agent 系统的差距分析

### 5.1 架构对比矩阵

| 维度 | 当前系统 | 一流 Agent (Claude Computer Use / Devin / Manus) | 差距等级 |
|------|----------|---------------------------------------------|----------|
| **推理引擎** | 关键词匹配 (`_detect_intent`) | LLM ReAct Loop (思考→行动→观察→再思考) | 🔴 核心差距 |
| **工具调用** | 硬编码分发 + Mock | Function Calling / Tool Use API，动态绑定 | 🔴 核心差距 |
| **上下文管理** | 无状态（每轮独立） | 滑动窗口 + Summary + Long-term Memory | 🔴 核心差距 |
| **规划能力** | 无显式规划 | Plan-Execute-Reflect 循环，多步任务分解 | 🟡 重要差距 |
| **错误恢复** | 单次尝试，失败降级 | 自动重试 + 替代方案 + 反思修正 | 🟡 重要差距 |
| **多模态** | 仅文字输入 | 图片/视频/音频输入输出 | 🟡 重要差距 |
| **流式体验** | 事件级流式 | Token 级流式 + 工具进度实时推送 | 🟢 可优化 |
| **配置管理** | DB + UI 管理 | 同等水平 | ✅ 已达标 |
| **工作流库** | 40+ ComfyUI JSON | 丰富（同等水平） | ✅ 已达标 |
| **模型接入** | 21 个多供应商 | 同等水平 | ✅ 已达标 |

### 5.2 核心差距详解

#### 🔴 差距 1：缺少 LLM ReAct 推理循环

**当前：**
```python
# smart_agent.py — 关键词匹配，线性执行
def _detect_intent(text):
    for intent, kws in _INTENT_KW:
        if any(kw in text for kw in kws):
            return intent     # ← 关键词命中即返回
    return "comic"            # ← 默认当漫剧处理
```

**一流 Agent：**
```python
# ReAct Loop — LLM 自主决策
while not done:
    # 1. Think: LLM 分析当前状态
    response = await llm.chat(messages, tools=TOOL_DEFS)
    
    # 2. Act: 如果 LLM 决定调用工具
    if response.tool_calls:
        for call in response.tool_calls:
            result = await execute_tool(call.name, call.input)
            messages.append(tool_result(call.id, result))
    
    # 3. Observe: LLM 看到工具结果，决定下一步
    else:
        yield response.text
        done = True
```

**影响：** 当前无法处理"画一张仙侠图，然后把背景换成夜晚，最后把第一张动态化"这种多步指令。

#### 🔴 差距 2：工具调用是 Mock 的

**当前：** SmartAgent 输出 picsum 随机图片 URL，未真正调用 ComfyUI。

**需要：** 将 `smart_agent_stream` 中的 Mock 逻辑替换为真实调用：
```
tool_start → comfyui_client.submit_workflow() → 等待 → tool_done(image_url=真实图片)
```

#### 🔴 差距 3：无上下文对话能力

**当前：** 每次 `smart_agent_stream(message)` 独立处理，不知道之前聊了什么。

**一流 Agent：** 维护完整消息历史 `messages[]`，LLM 能看到之前所有对话和工具结果，实现：
- "把刚才的第三张图改成夜景" — 需要引用之前的生成结果
- "重新生成，但风格改成水墨" — 需要记住之前的参数

#### 🟡 差距 4：缺少 Plan-Execute-Reflect

**一流 Agent 的漫剧生成流程：**
```
Plan:  "用户要4格仙侠漫剧 → 我需要：1)分析故事 2)规划分镜 3)逐格生成 4)检查质量"
Execute: 调用 LLM 分析 → 调用工具生成图片
Reflect: "第2格构图不够好 → 重新生成，调整提示词"
```

**当前：** 线性执行，无反思和自我修正能力。

### 5.3 改进路线图

```
Phase 1: 接入真实 LLM Agent Loop（优先级：最高）
──────────────────────────────────────────────────
□ 1.1 创建 AIPro LLM 客户端（OpenAI 兼容，支持 Claude/GPT）
□ 1.2 实现 ReAct Agent Loop：LLM 思考 → 工具调用 → 观察结果 → 继续
□ 1.3 将 tool_registry 的 JSON Schema 转为 Claude tool_use 格式
□ 1.4 工具执行器对接真实 ComfyUI（复用现有 comfyui_client）
□ 1.5 Token 级流式输出（Claude streaming + tool_use events）

Phase 2: 多轮上下文 + 多模态（优先级：高）
──────────────────────────────────────────────────
□ 2.1 消息历史管理：滑动窗口 + 摘要压缩
□ 2.2 图片上传：前端组件 + 后端 base64/URL 注入 LLM
□ 2.3 工具结果图片回注到消息历史（让 LLM 看到生成的图）
□ 2.4 会话恢复：从 DB 加载历史消息

Phase 3: 智能规划 + 错误恢复（优先级：中）
──────────────────────────────────────────────────
□ 3.1 Plan-Execute-Reflect 循环
□ 3.2 工具失败自动重试 + 替代工作流选择
□ 3.3 质量检查：用多模态 LLM 评估生成结果
□ 3.4 进度推送 + 任务取消

Phase 4: Memory + RAG（优先级：中低）
──────────────────────────────────────────────────
□ 4.1 用户偏好记忆（常用风格、角色设定）
□ 4.2 Embedding 向量检索增强（风格参考、提示词库）
□ 4.3 知识图谱（角色关系、故事连续性）
```

---

## 六、技术债务清单

| 编号 | 问题 | 影响 | 修复建议 |
|------|------|------|----------|
| TD-1 | `smart_agent.py` 和 `mock_agent.py` 两套 Mock 共存 | 代码混乱 | 统一为一个真实 Agent，删除 Mock |
| TD-2 | HTTP 路径 (`/comic/generate`) 和 WebSocket 路径 (`/ws/chat`) 逻辑割裂 | 能力不复用 | Agent 路径整合 ComicAgent 管线 |
| TD-3 | `llm_client.py` 只支持南格，不支持 AIPro | Agent 无法用 Claude | 增加 AIPro OpenAI 兼容客户端 |
| TD-4 | 工作流选择硬编码在 `T2I_STYLE_MAP` 字典中 | 新工作流需改代码 | 基于 DB `workflow_template` 动态查询 |
| TD-5 | API Key 明文存储在 `model_config.api_key` | 安全风险 | 加密存储 + 环境变量注入 |
| TD-6 | 前端 `Mock 模式` 标签硬编码 | 用户困惑 | 根据后端状态动态显示 |
| TD-7 | WebSocket 无心跳/重连 | 长时间空闲断连 | 添加 ping/pong + 自动重连 |
| TD-8 | `inject_params` 基于 `class_type` 字符串匹配 | 脆弱，新节点需手动适配 | 使用 `param_mapping` JSON 配置 |

---

## 七、总结

**当前系统定位：** 一个 **基础设施完善但智能层薄弱** 的漫剧生成平台。

- ✅ **底座扎实**：前后端框架、数据库、ComfyUI 工作流引擎、多模型接入都已就绪
- ⚠️ **Agent 是假的**：核心对话逻辑是关键词匹配 + Mock，不是 LLM 驱动的自主推理
- 🔑 **升级关键**：Phase 1（接入 Claude/GPT ReAct Loop + 真实工具调用）完成后，系统将从"Mock 演示"升级为"可用 Agent"

**用一句话概括差距：**  
> 当前系统有「手」（ComfyUI 40+ 工作流）和「耳朵」（21 个模型接入），但缺少「大脑」（LLM ReAct 推理循环）来协调它们。

