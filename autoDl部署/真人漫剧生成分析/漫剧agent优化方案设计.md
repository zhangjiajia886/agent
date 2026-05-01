# 漫剧 Agent 优化方案设计：基于 MyAgent2 深度对比

> 深度对比分析 + 分阶段迁移方案  
> 2026-04-28

---

## 一、两套系统全景对比

### 1.1 架构层级对比

| 层级 | backend-myagent2 (通用 Agent) | 漫剧 Agent (当前系统) | 差距 |
|------|------------------------------|----------------------|------|
| **LLM 客户端** | 562 行，3 provider (southgrid/openai/ollama)，DB 动态解析 | 163 行，仅 OpenAI 兼容 | ⚠️ 缺南格 HMAC + ollama |
| **Agent 循环** | 884 行，ReAct + FC 双轨，20 轮，完整防护 | 296 行，仅 FC，8 轮，基础循环 | 🔴 缺 6 项关键机制 |
| **工具系统** | 40 个通用工具 + 80 别名 + MCP + BaseTool 抽象 | 8 个专用工具，硬编码执行器 | ⚠️ 不同定位，不可直接对比 |
| **Multi-Agent** | 375 行，sequential/parallel/supervisor 三模式 | ❌ 无 | 🔴 完全缺失 |
| **工作流引擎** | 530 行，DAG 拓扑 + 断点恢复 + 条件/循环 | ❌ 无（有 79 个 ComfyUI JSON 但无 DAG 编排） | 🔴 完全缺失 |
| **WebSocket** | 多连接管理器，按 execution_id 分组推送 | 单连接直推，无分组 | ⚠️ 够用但不优雅 |
| **前端** | React + TypeScript，完整 IDE 风格 | Vue3 + ElementPlus，对话式 UI | 不同方向 |

### 1.2 代码规模对比

```
backend-myagent2 核心代码：
  agent/loop.py          884 行  ← Agent 循环（核心）
  agent/orchestrator.py  375 行  ← Multi-Agent 调度
  llm/client.py          562 行  ← LLM 统一客户端
  engine/executor.py     530 行  ← 工作流 DAG 引擎
  engine/checkpoint.py   168 行  ← 断点恢复
  engine/context.py       68 行  ← 执行上下文
  engine/dag.py           56 行  ← 拓扑排序
  tools/registry.py      244 行  ← 工具注册中心
  tools/base.py           40 行  ← 工具基类
  tools/builtin.py     29185 行  ← 15 个基础工具实现
  ws/manager.py           65 行  ← WebSocket 管理器
  ────────────────────────────
  核心架构层合计      ≈ 3000 行
  工具实现层合计      ≈ 90000 行

漫剧 Agent 核心代码：
  comic_chat_agent/agent_runner.py   296 行  ← Agent 循环
  comic_chat_agent/openai_client.py  163 行  ← LLM 客户端
  comic_chat_agent/tool_executor.py  220 行  ← 工具执行器
  comic_chat_agent/smart_agent.py    304 行  ← 关键词分发（将废弃）
  comic_chat_agent/mock_agent.py     145 行  ← Mock（将废弃）
  api/v1/comic_agent.py             718 行  ← API + 种子 + WS
  ────────────────────────────
  核心架构层合计      ≈ 680 行
  含 API 路由层合计   ≈ 1850 行
```

---

## 二、六个关键差距深度分析

### 差距 ① — LLM 客户端：单一 vs 统一

#### MyAgent2 的 LLM 客户端（3 条通路）

```python
# llm/client.py — 核心路由逻辑
async def chat(self, model, messages, tools, ...):
    provider, base_url, api_key, ... = await self._resolve_model_config(model)  # DB 动态解析
    
    if provider == "southgrid":
        return self._southgrid_stream(...)    # HMAC 签名认证
    elif provider != "ollama":
        return self._openai_compat_stream(...)  # OpenAI / AIPro 直连
    else:
        return self._litellm_stream(...)       # Ollama via litellm
```

**关键能力：**
- `_resolve_model_config()` — 按 model_id 从 DB 查配置，自动切换 provider
- Southgrid HMAC 签名 — 南格推理平台专用认证
- 流式 tool_calls 累积 — 逐 chunk 拼接工具调用参数
- Thinking/Reasoning 支持 — Qwen3 `reasoning_content` / Claude `<thinking>`
- 模型降级 — stream+tools 失败自动重试无 tools 模式
- `_MODELS_NO_TOOLS_STREAM` — 运行时自动标记不支持流式工具的模型

#### 漫剧 Agent 的 LLM 客户端（1 条通路）

```python
# openai_client.py — 仅 OpenAI 兼容
async def chat(self, messages, tools, ...):
    async with httpx.AsyncClient() as c:
        resp = await c.post(f"{self.base_url}/chat/completions", ...)
    # 解析 tool_calls → 返回 LLMResponse
```

**缺失能力：**
| 能力 | MyAgent2 | 漫剧 Agent | 影响 |
|------|----------|-----------|------|
| 南格 HMAC 签名 | ✅ | ❌ | 无法使用南格模型（Qwen3-32B 等） |
| DB 动态模型解析 | ✅ | ❌ 硬传参 | 切换模型需改代码 |
| 流式工具调用 | ✅ | ❌ 非流式 | 用户等待时间长，无中间反馈 |
| Thinking 模式 | ✅ | ❌ | 无法展示 Claude/Qwen 的思考过程 |
| 模型降级 | ✅ | ❌ | 不支持工具的模型直接报错 |
| Ollama 本地模型 | ✅ | ❌ | 无法使用本地部署的模型 |

---

### 差距 ② — Agent 循环：6 项关键防护机制缺失

#### MyAgent2 的 Agent 循环（884 行）

```
┌─────── AgentLoop.run() ────────────────────────────────────────────┐
│                                                                     │
│  1. 直接工具命令 (/bash /python /search)  ← 跳过 LLM              │
│  2. Skill 斜杠命令 (/skillName)           ← 自定义 prompt + 工具   │
│  3. System Prompt 构建                                              │
│     ├── base prompt + 图表渲染规范 + 时间注入                       │
│     └── ReAct 调用指令注入                                          │
│  4. 历史加载 + 消息组装                                             │
│  5. Agent 循环 (最多 20+1 轮)                                       │
│     ├── [P1] Token 估算 → 超阈值自动压实历史                        │
│     ├── [P0] Token 预算感知提示注入 (50%/75%)                       │
│     ├── 最终轮强制摘要（移除工具，强制文字回答）                     │
│     ├── LLM 流式调用 → delta 事件推送                               │
│     ├── ReAct XML 降级解析 (<tool_call>{...}</tool_call>)           │
│     ├── Human-in-the-loop 确认 (120s 超时)                         │
│     │   └── 审批持久化 → approval_requests 表                       │
│     ├── 工具调用次数限制 (python_exec:3, bash:5)                    │
│     ├── 工具结果压缩 (_compact_tool_result → ~90% token 节省)       │
│     ├── 工具使用统计 (tool_usages 表)                               │
│     └── 完整工具调用日志 (tool_call_logs 表)                        │
│  6. 最终统计 (token 用量 / 延迟 / 工具调用清单)                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 漫剧 Agent 的 Agent 循环（296 行）

```
┌─────── agent_stream() ─────────────────────────────────────────────┐
│                                                                     │
│  1. 创建 LLM 客户端 + 加载工具定义 + 加载 system prompt             │
│  2. 构建消息列表 (system + 最近 20 条历史 + 当前消息)                │
│  3. yield thinking 事件（模型/工具/历史摘要）                        │
│  4. Agent 循环 (最多 8 轮)                                          │
│     ├── LLM 非流式调用（带 3s 心跳）                                │
│     ├── yield thinking（决策摘要）                                   │
│     ├── yield text（文字回复）                                       │
│     ├── 工具调用 → yield tool_start → execute_tool → yield tool_done│
│     └── 工具结果注入消息历史（完整 JSON，未压缩）                    │
│  5. 超过 8 轮 → yield 提示文字                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 逐项对比

| 防护机制 | MyAgent2 | 漫剧 Agent | 迁移优先级 |
|---------|----------|-----------|-----------|
| **Token 预算管理** | 估算 + 压实 + 紧张提示 | ❌ 完全没有 | 🔴 P0 — 长对话必爆 |
| **工具结果压缩** | 只保留关键信息，~90% 节省 | ❌ 完整 JSON 注入 | 🔴 P0 — 一次图片工具结果就消耗大量 token |
| **ReAct XML 降级** | 模型不支持 FC 时用 XML 解析 | ❌ 仅 FC | ⚠️ P1 — 南格模型不支持 FC |
| **Human-in-the-loop** | 高危工具需用户确认 | ❌ 直接执行 | ⚠️ P1 — 漫剧场景风险较低但应有 |
| **工具调用限制** | 单次 run 每工具最大调用次数 | ❌ 无限制 | 🔴 P0 — LLM 可能无限循环生成图片 |
| **强制摘要轮** | 最后一轮移除工具，强制文字回答 | ❌ 直接截断 | ⚠️ P1 — 用户体验差 |
| **工具使用统计** | tool_usages 表记录 | ❌ | ⚪ P2 — 运维用 |
| **完整调用日志** | tool_call_logs 表记录完整 I/O | ❌ | ⚪ P2 — 调试用 |
| **时间注入** | system prompt 注入当前时间 | ❌ | ⚪ P2 — 辅助 |
| **直接工具命令** | /bash /python 等斜杠命令 | ❌ | ❌ 不需要 — 漫剧场景无此需求 |
| **Skill 系统** | /skillName 自定义 prompt | ❌ | ❌ 不需要 — 漫剧有独立 prompt 管理 |

---

### 差距 ③ — 工具系统：通用 vs 专用

#### 两套工具系统的本质区别

```
MyAgent2 (通用 Agent):
  40 个工具 = 通用能力（bash/文件/网络/数据库/Office/Git...）
  定位：让 LLM 成为全能助手，能执行任意任务
  工具是"手段"，由 LLM 自主选择

漫剧 Agent (专用 Agent):
  8 个工具 = 视觉创作能力（生成图/编辑图/生成视频/TTS...）
  定位：让 LLM 成为视觉创作助手，专注图像/视频/音频
  工具是"创作能力"，由 LLM 根据用户创作意图调度
```

**不应照搬 MyAgent2 的 40 个工具**，但应该借鉴其工具系统架构：

| 架构特性 | MyAgent2 | 漫剧 Agent | 是否迁移 |
|---------|----------|-----------|---------|
| BaseTool 抽象基类 | ✅ `name/description/category/risk_level/schema/run()` | ❌ 纯函数 | ✅ 迁移 — 统一接口 |
| 别名映射 | ✅ 80+ 别名，LLM 幻觉兼容 | ❌ | ✅ 迁移 — LLM 经常输出非标准名 |
| MCP 动态工具 | ✅ 运行时注册外部工具 | ❌ | ⚪ 暂不需要 |
| 工具白名单 | ✅ `allowed_tools` 控制可用范围 | ❌ 全部开放 | ✅ 迁移 — 按场景限制工具 |

---

### 差距 ④ — Multi-Agent 调度：完全缺失

MyAgent2 有一个完整的 `MultiAgentOrchestrator`（375 行），支持三种编排模式：

```
Sequential（串行流水线）:
  Agent A (意图解析) → Agent B (分镜规划) → Agent C (提示词生成) → Agent D (图像生成)
  
  漫剧场景用途：当前 HTTP 漫剧管线（intent_parser → story_planner → prompt_builder → image_gen）
  本质上就是 sequential 模式，但用硬编码实现的。

Parallel（并行执行）:
  Agent A (第 1 格生成) ║ Agent B (第 2 格生成) ║ Agent C (第 3 格生成)
  
  漫剧场景用途：多格漫剧并行生成，大幅缩短总时间。

Supervisor（监督者路由）:
  Supervisor Agent 分析用户需求
    → <route>image_agent: 生成一张仙侠剑客图</route>
    → image_agent 完成
    → <route>video_agent: 把图片动态化</route>
    → video_agent 完成
    → Supervisor 汇总回复
  
  漫剧场景用途：复杂的跨媒体创作任务（图+视频+音频+字幕组合）。
```

#### 漫剧场景的 Multi-Agent 价值

```
当前（单 Agent）:
用户: "仙侠4格漫剧，白衣剑客踏雪而来"
→ 1 个 Agent 串行处理一切
→ 每次只能处理一件事
→ 4 格图片串行生成 = 4 × 30s = 120s

迁移后（Multi-Agent）:
用户: "仙侠4格漫剧，白衣剑客踏雪而来"
→ Supervisor Agent 规划:
  1. 分镜 Agent 生成 4 格分镜描述（LLM 调用，1次）
  2. 4 个 Image Agent 并行生成 4 格图片（ComfyUI 并行）
  3. TTS Agent 可选生成旁白语音
  4. Supervisor 汇总输出
→ 4 格图片并行生成 = max(30s) = 30s  ← 4 倍提速
```

---

### 差距 ⑤ — 工作流 DAG 引擎：完全缺失

MyAgent2 有一个完整的 `WorkflowEngine`（530 行）：

```python
# engine/executor.py — 节点类型支持
node_type == "start"      # 起始节点，注入输入变量
node_type == "end"        # 结束节点，收集输出
node_type == "llm"        # LLM 调用节点
node_type == "tool"       # 工具执行节点
node_type == "condition"  # 条件分支（if/else）
node_type == "loop"       # 循环（含子 DAG）
node_type == "variable"   # 变量赋值
node_type == "merge"      # 合并多路输出
node_type == "skill"      # 技能调用
node_type == "subflow"    # 子工作流

# 核心能力
- DAG 拓扑排序 + 同层节点并行执行
- 断点恢复（CheckpointManager）
- 模板变量渲染 {{variable.nested.path}}
- 取消令牌（CancellationToken）
- WebSocket 实时节点状态推送
```

**漫剧 Agent 已有 79 个 ComfyUI 工作流 JSON**，但这些是 ComfyUI 内部的节点图，不是 Agent 层的编排 DAG。

#### 两层工作流的区别

```
Agent 层 DAG（MyAgent2 有，漫剧 Agent 缺）:
  "先用 LLM 分析意图 → 再选工作流 → 再调 ComfyUI → 最后生成视频"
  这是 业务编排 层的工作流

ComfyUI 层 JSON（漫剧 Agent 有 79 个）:
  "KSampler → VAE Decode → Save Image"
  这是 GPU 执行 层的工作流

两层不冲突，Agent DAG 调用 ComfyUI JSON。
```

---

### 差距 ⑥ — 流式输出与用户体验

| 体验项 | MyAgent2 | 漫剧 Agent |
|--------|----------|-----------|
| **LLM 输出** | 逐 token 流式 (`delta` 事件) | 非流式，一次性返回全文 |
| **思考过程** | `<thinking>` 标签实时展示 | 仅心跳 `⏳ 推理中...` |
| **工具确认** | 高危工具弹出确认卡片 | 直接执行无预览 |
| **执行预览** | 命令/代码/文件修改预览 | 无预览 |
| **Token 统计** | `done` 事件含 input/output tokens + 延迟 | 无统计 |
| **模型元数据** | 返回使用的模型名 + skill 名 | 仅 thinking 中提及 |

---

## 三、迁移方案：分三期实施

### 3.1 总体策略

```
                      MyAgent2 (通用 Agent)
                           │
                    ┌──────┴──────┐
                    │  提取架构层   │
                    │  丢弃通用工具 │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ 漫剧 Agent   │
                    │ + 架构升级   │
                    │ + 保留专用工具│
                    └─────────────┘

不是替换，是移植骨架。保留漫剧 Agent 的：
  ✅ 8 个专用工具执行器（ComfyUI / TTS）
  ✅ 79 个 ComfyUI 工作流 JSON
  ✅ workflow_selector / workflow_registry
  ✅ 前端 Vue3 对话 UI
  ✅ 数据库 model_config / tool_registry / agent_conversation

从 MyAgent2 移植的：
  ✅ LLM 客户端统一架构（多 provider + DB 解析 + 流式 FC）
  ✅ Agent 循环防护机制（token 管理 + 工具压缩 + 调用限制）
  ✅ Multi-Agent 调度（漫剧并行生成）
  ✅ 工具别名映射
```

### 3.2 第一期：Agent 循环加固（预计 4-6h）

**目标：** 让现有 agent_runner.py 从"能跑"变成"稳定跑"。

#### 修改文件 1: `comic_chat_agent/openai_client.py`

| 改造项 | 内容 | 来源 |
|--------|------|------|
| 流式 tool_calls | 支持流式输出中的工具调用累积 | `llm/client.py:_openai_compat_stream` |
| Thinking 支持 | 解析 `reasoning_content` / `<thinking>` | `llm/client.py:269-279` |
| 模型降级 | stream+tools 失败自动重试 | `llm/client.py:341-358` |
| 南格 HMAC | 添加 `SouthgridProvider` | `llm/client.py:149-313` + `southgrid_auth.py` |

预计新增 ≈ 250 行，改造现有 ≈ 50 行。

#### 修改文件 2: `comic_chat_agent/agent_runner.py`

| 改造项 | 内容 | 来源 |
|--------|------|------|
| Token 预算管理 | 估算 + 压实 + 紧张提示 | `loop.py:192-226, 343-364` |
| 工具结果压缩 | `_compact_tool_result()` | `loop.py:145-188` |
| 工具调用限制 | 单次 run 每工具最大调用次数 | `loop.py:113-119, 536-542` |
| 强制摘要轮 | 最后一轮移除工具 | `loop.py:367-373` |
| ReAct XML 降级 | 文本解析 `<tool_call>` | `loop.py:758-802` |
| 流式输出 | 逐 token delta 事件 | `loop.py:390-393` |
| 统计日志 | done 事件含 token 用量 | `loop.py:584-602` |

预计改造 ≈ 300 行。

#### 修改文件 3: `comic_chat_agent/tool_executor.py`

| 改造项 | 内容 | 来源 |
|--------|------|------|
| 工具别名映射 | LLM 常见幻觉名 → 标准名 | `registry.py:23-145` |
| 统一结果格式 | `{"status", "output", "file_urls", "error"}` | `base.py` 接口 |

预计新增 ≈ 40 行。

#### 第一期改造后效果

```
改造前：
  用户: "画一张仙侠剑客"
  → LLM 非流式调用（用户等 15s 无反馈）
  → 一次性返回全文 + 工具调用
  → 工具结果完整 JSON 注入历史（浪费 token）
  → 聊 10 轮后 token 爆炸，LLM 报错

改造后：
  用户: "画一张仙侠剑客"
  → LLM 流式输出（逐字显示 "好的，我来帮你..."）
  → 工具调用流式累积 → tool_start 事件
  → 工具结果压缩后注入（"[generate_image] ✓ 生成文件: [/uploads/xxx.png]"）
  → Token 预算监控，超 75% 自动压实历史
  → 工具调用次数限制，防止 LLM 无限生成
  → 达到最大轮次 → 强制摘要轮，给出完整总结
```

---

### 3.3 第二期：Multi-Agent 漫剧并行生成（预计 6-8h）

**目标：** 多格漫剧从串行变并行，4 格 120s → 40s。

#### 新增文件: `comic_chat_agent/orchestrator.py`

从 MyAgent2 `agent/orchestrator.py` 迁移，适配漫剧场景：

```python
# 漫剧版 Orchestrator — 简化版
class ComicOrchestrator:
    """漫剧多格并行生成调度器"""
    
    async def generate_comic_parallel(
        self,
        user_message: str,
        model_config: ModelConfig,
        db: AsyncSession,
        num_frames: int = 4,
        style: str = "xianxia",
    ) -> AsyncIterator[dict]:
        """
        Phase 1: LLM 分镜规划（单次调用）
        Phase 2: 多格并行生成（asyncio.gather）
        Phase 3: 可选 TTS 旁白
        """
        # Phase 1: 分镜
        llm = create_llm_client(model_config)
        frames_desc = await self._plan_frames(llm, user_message, num_frames, style)
        
        # Phase 2: 并行生成
        tasks = [
            self._generate_single_frame(frame_desc, style, i)
            for i, frame_desc in enumerate(frames_desc)
        ]
        
        queue = asyncio.Queue()
        async def run_with_events(task_fn, frame_idx):
            yield {"type": "tool_start", "tool": "generate_image", "input": {"frame": frame_idx + 1}}
            result = await task_fn
            yield {"type": "tool_done", "tool": "generate_image", "image_url": result["image_url"]}
        
        # 并行执行，事件通过 queue 合并推送
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Phase 3: 汇总
        yield {"type": "text", "content": f"🎉 {num_frames} 格漫剧全部生成完毕！"}
```

预计新增 ≈ 250 行。

#### 修改 WebSocket 入口

```python
# comic_agent.py — 新增分发逻辑
if model_id and intent == "comic" and frames > 1:
    # 多格漫剧 → 并行生成模式
    orchestrator = ComicOrchestrator()
    async for event in orchestrator.generate_comic_parallel(
        message, model_config, db, frames, style
    ):
        await websocket.send_json(event)
else:
    # 单图/对话 → 标准 Agent 循环
    async for event in agent_stream(message, model_config, db, history):
        await websocket.send_json(event)
```

---

### 3.4 第三期：工作流 DAG 引擎（预计 8-10h）

**目标：** 可视化编排复杂的漫剧生产管线。

#### 从 MyAgent2 迁移的模块

| 文件 | 行数 | 适配改造 |
|------|------|---------|
| `engine/dag.py` | 56 | 原样迁移 |
| `engine/context.py` | 68 | 原样迁移 |
| `engine/checkpoint.py` | 168 | 改用 SQLAlchemy (现用 aiosqlite) |
| `engine/executor.py` | 530 | 精简节点类型，保留 llm/tool/condition/loop |
| `ws/manager.py` | 65 | 原样迁移 |

#### 漫剧场景的工作流示例

```json
{
  "name": "仙侠4格漫剧生产线",
  "nodes": [
    {"id": "start", "type": "start", "data": {"outputs": ["description", "style"]}},
    {"id": "intent", "type": "llm", "data": {
      "model": "claude-sonnet-4-6",
      "systemPrompt": "分析用户需求...",
      "userPromptTemplate": "{{description}}",
      "outputVariable": "intent_result"
    }},
    {"id": "plan", "type": "llm", "data": {
      "model": "claude-sonnet-4-6",
      "systemPrompt": "生成分镜描述...",
      "userPromptTemplate": "风格:{{style}} 故事:{{intent_result.story}}",
      "outputVariable": "frames"
    }},
    {"id": "gen_frame_1", "type": "tool", "data": {
      "toolName": "generate_image",
      "paramMapping": {"prompt": "frames[0]", "style": "style"}
    }},
    {"id": "gen_frame_2", "type": "tool", "data": {
      "toolName": "generate_image",
      "paramMapping": {"prompt": "frames[1]", "style": "style"}
    }},
    {"id": "end", "type": "end", "data": {"outputs": ["frame_1_url", "frame_2_url"]}}
  ],
  "edges": [
    {"source": "start", "target": "intent"},
    {"source": "intent", "target": "plan"},
    {"source": "plan", "target": "gen_frame_1"},
    {"source": "plan", "target": "gen_frame_2"},
    {"source": "gen_frame_1", "target": "end"},
    {"source": "gen_frame_2", "target": "end"}
  ]
}
```

**gen_frame_1 和 gen_frame_2 在同一拓扑层级 → 自动并行执行。**

---

## 四、迁移优先级总览

```
优先级排序（按投入产出比）:

🔴 P0 — 必须立即做（影响可用性）
  1. Token 预算管理 + 工具结果压缩     ← 长对话必爆，修复成本低
  2. 工具调用次数限制                   ← 防 LLM 死循环，一行配置
  3. 流式 LLM 输出                     ← 用户体验质变，改造量适中

⚠️ P1 — 尽快做（影响体验质量）
  4. ReAct XML 降级                    ← 南格模型不支持 FC
  5. 强制摘要轮                        ← 超限时体验优雅降级
  6. LLM 南格 HMAC + 多 provider       ← 使用内网模型
  7. Thinking 模式展示                 ← Claude/Qwen 思考可视化

⚪ P2 — 规划做（影响平台能力）
  8. Multi-Agent 并行生成              ← 4 倍提速，但架构改动大
  9. 工具别名映射                      ← 提高 LLM 调用鲁棒性
  10. 工具使用统计 + 调用日志           ← 运维观测

🔵 P3 — 远期规划（影响平台天花板）
  11. 工作流 DAG 引擎                  ← 可视化编排，最大改动
  12. 断点恢复                         ← 长任务容错
  13. MCP 动态工具                     ← 外部能力扩展
```

---

## 五、不应迁移的部分

| MyAgent2 功能 | 原因 |
|--------------|------|
| 40 个通用工具 (bash/文件/数据库/Git/Office) | 漫剧场景不需要，徒增攻击面 |
| Human-in-the-loop 确认 | 漫剧工具都是安全的（生成图片/视频），无需确认 |
| /bash /python 直接命令 | 漫剧 Agent 不执行任意代码 |
| Skill 系统 | 漫剧 Agent 有独立的 agent_prompt 管理 |
| SQLite (aiosqlite) | 漫剧 Agent 用 MySQL + SQLAlchemy，更成熟 |
| 前端 React 架构 | 漫剧 Agent 用 Vue3 + ElementPlus，已成型 |

---

## 六、实施路线图

```
第一期（4-6h）: Agent 循环加固
────────────────────────────────
  Week 1, Day 1-2:
  ├── [1] openai_client.py 升级（流式 FC + thinking + 降级）
  ├── [2] agent_runner.py 加固（token 管理 + 压缩 + 限制 + 摘要轮）
  ├── [3] tool_executor.py 别名映射
  └── [4] 验证：选 claude-sonnet-4-6 → 长对话 10 轮 → 不爆 token

第二期（6-8h）: Multi-Agent 并行
────────────────────────────────
  Week 1, Day 3-4:
  ├── [5] 新增 orchestrator.py（漫剧并行调度）
  ├── [6] 修改 comic_agent.py WS 入口分发
  ├── [7] 前端：多格并行进度展示
  └── [8] 验证：4 格漫剧 → 并行生成 → 时间减半

第三期（8-10h）: 工作流 DAG 引擎
────────────────────────────────
  Week 2:
  ├── [9]  迁移 dag.py + context.py + checkpoint.py
  ├── [10] 适配 executor.py（SQLAlchemy + 漫剧工具）
  ├── [11] API: 工作流 CRUD + 执行入口
  ├── [12] 前端：DAG 可视化编辑器（基于 Vue Flow）
  └── [13] 验证：可视化编排漫剧管线 → 执行 → 断点恢复
```

---

## 七、总结

### 核心发现

**MyAgent2 是一个成熟的通用 Agent 平台**，经历过多轮迭代，积累了大量生产级防护机制。**漫剧 Agent 的 Agent Runner 已搭好基本骨架**（LLM 调用 + 工具执行 + ReAct 循环），但缺少 6 项关键防护，无法应对真实使用场景。

### 移植策略

```
从 MyAgent2 取其「骨」:
  ✅ LLM 多 provider 统一调度
  ✅ Agent 循环 6 项防护机制
  ✅ Multi-Agent 并行调度
  ✅ 工作流 DAG 引擎

在漫剧 Agent 保留其「肉」:
  ✅ 8 个专用工具执行器（ComfyUI / TTS）
  ✅ 79 个 ComfyUI 工作流 JSON + 自动扫描
  ✅ workflow_selector 智能选择
  ✅ Vue3 对话 UI + 事件协议
  ✅ MySQL + SQLAlchemy 数据层
```

### 预期收益

| 指标 | 当前 | 第一期后 | 第三期后 |
|------|------|---------|---------|
| 长对话稳定性 | 10 轮后爆 token | 50+ 轮稳定 | 100+ 轮稳定 |
| 4 格漫剧耗时 | 120s（串行） | 120s（无变化） | 30s（并行） |
| 模型兼容 | 仅 AIPro | + 南格 + Ollama | + 任意 OpenAI 兼容 |
| LLM 输出体验 | 等 15s 后一次性显示 | 逐字流式显示 | 逐字 + 思考过程 |
| 工具调用鲁棒性 | FC 失败就挂 | FC + ReAct XML 双轨 | + DAG 编排 |
| 可扩展性 | 改代码加工具 | 别名映射 + 热加载 | + 可视化编排 |
