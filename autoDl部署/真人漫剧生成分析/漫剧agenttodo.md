# 漫剧 Agent 第一期实施 TODO

> 基于《漫剧agent优化方案设计.md》+ 《漫剧agent优化方案实施计划.md》

---

## 补充需求：模型参数配置

**用户需求：** 每个模型可配置 max_tokens、temperature 等参数。

**方案：** 在 `model_config` 表新增 `model_params` JSON 列。

```
DB 变更: ALTER TABLE model_config ADD COLUMN model_params JSON DEFAULT NULL;
Model:   ModelConfig 新增 model_params = Column(JSON)
Schema:  ModelConfigSchema 新增 model_params
Update:  ModelConfigUpdate 新增 model_params
Runner:  agent_runner.py 读取 model_params 传给 LLM client
前端:    服务配置 Tab 中模型行新增参数编辑 popover
```

---

## 评估："一句话生成短剧"可行性

### 结论：**架构可行，但需完成三期 + 补齐 2 个工具实现**

### 短剧生成管线

```
用户: "仙侠4格动态短剧，白衣剑客踏雪寻剑"
  │
  ▼ Phase 1: 意图解析 (LLM)
  │  → style=xianxia, frames=4, story="白衣剑客踏雪寻剑"
  │
  ▼ Phase 2: 分镜规划 (LLM)
  │  → ["远景·雪山", "中景·拔剑", "近景·剑光", "远景·踏雪而去"]
  │
  ▼ Phase 3: 提示词构建 (LLM)
  │  → 4 个英文 prompt
  │
  ▼ Phase 4: 并行图片生成 (ComfyUI × 4) ← 需 Phase 2 并行能力
  │  → 4 张图片 (≈30s 并行)
  │
  ▼ Phase 5: 并行图生视频 (ComfyUI × 4) ← 需 Phase 2 并行能力
  │  → 4 段 3-5s 视频 (≈60s 并行)
  │
  ▼ Phase 6: 旁白 TTS (Fish Audio)
  │  → 4 段旁白音频 (≈5s)
  │
  ▼ Phase 7: 媒体合成 (merge_media) ← ⚠️ 当前未实现
  │  → 拼接 4 段视频 + 叠加音频
  │
  ▼ Phase 8: 字幕叠加 (add_subtitle) ← ⚠️ 当前未实现
  │  → 最终短剧视频
  │
  预计总耗时: ≈2-3 分钟（并行）/ ≈8-10 分钟（串行）
```

### 当前缺口

| 缺口 | 对应期 | 说明 |
|------|--------|------|
| merge_media 未实现 | 第一期可补 | FFmpeg 合成，本地执行 |
| add_subtitle 未实现 | 第一期可补 | FFmpeg 字幕叠加，本地执行 |
| 无并行执行 | 第二期 | 串行可用但慢 |
| Agent 循环不稳定 | 第一期 | 8 步管线易爆 token |

### 结论

- **第一期完成后**：可以串行实现（但慢，约 8-10 分钟）
- **第二期完成后**：可以并行实现（约 2-3 分钟）
- **前提**：需实现 merge_media + add_subtitle 的 FFmpeg 执行逻辑

---

## 第一期 TODO ✅ 已完成

### Step 1: 数据库 + 模型参数支持 ✅

- [x] 1.1 DB: `model_config` 表新增 `model_params` JSON 列
- [x] 1.2 Model: `agent_config.py` — `ModelConfig` 新增 `model_params` 字段
- [x] 1.3 Schema: `agent.py` — `ModelConfigSchema` + `ModelConfigUpdate` 新增字段
- [x] 1.4 API: `comic_agent.py` — `update_model()` 支持更新 `model_params`
- [x] 1.5 Runner: `agent_runner.py` — `create_llm_client()` 读取 `model_params`
- [x] 1.6 **补充**: `max_tokens` 按各模型官方最大输出限制设置（Claude 64K-128K / GPT 128K / Gemini 65K / Qwen 4K-8K）
- [x] 1.7 **补充**: 新增 `top_p` / `frequency_penalty` / `presence_penalty` 三个参数，共 5 个可配置参数

### Step 2: LLM 客户端升级 (`openai_client.py`) ✅

- [x] 2.1 新增 `LLMStreamChunk` 数据类
- [x] 2.2 新增 `chat_stream_with_tools()` — 流式 + tool_calls 累积
- [x] 2.3 Thinking 支持 — 解析 `reasoning_content`
- [x] 2.4 模型降级 — stream+tools 失败自动重试 + `_MODELS_NO_TOOLS_STREAM` 运行时标记
- [x] 2.5 `chat()` / `chat_stream_with_tools()` / `chat_stream()` 支持 5 个 model_params

### Step 3: Agent Runner 加固 (`agent_runner.py`) ✅

- [x] 3.1 Token 预算管理 — `_estimate_tokens()` + `_compact_history()`
- [x] 3.2 工具结果压缩 — `_compact_tool_result()`
- [x] 3.3 工具调用次数限制 — `MAX_TOOL_CALLS_PER_TOOL`（8 个工具各有上限）
- [x] 3.4 强制摘要轮 — 最后一轮移除工具强制文字回答
- [x] 3.5 ReAct XML 降级 — `_parse_react_tool_calls()` 解析 `<tool_call>` 标签
- [x] 3.6 流式输出 — 替换心跳为流式 `delta` 事件
- [x] 3.7 done 事件 — 含 model / iterations / tool_calls / tokens / tools_used

### Step 4: 工具执行器增强 (`tool_executor.py`) ✅

- [x] 4.1 工具别名映射 — `TOOL_ALIASES`（20+ 别名覆盖所有工具）
- [x] 4.2 统一结果格式 — `file_urls` 字段汇总所有产出文件

### Step 5: 前端适配 ✅

- [x] 5.1 `delta` 事件处理 — 流式逐字追加到当前 assistant 消息
- [x] 5.2 `done` 事件处理 — 标记 `isFinished` + metadata
- [x] 5.3 模型参数编辑 — Popover（340px）含 5 个控件：max_tokens / temperature / top_p / freq_penalty / pres_penalty
- [x] 5.4 `tool_done` 支持 `video_url` / `audio_url` 直接媒体 URL

### Step 6: DB 迁移 + 集成测试 ✅

- [x] 6.1 DB 迁移: `ALTER TABLE model_config ADD COLUMN model_params JSON`
- [x] 6.2 API 测试: Login → GET models → PUT model_params（5 参数）→ Restore → 全通过
- [x] 6.3 所有 18 个模型的 `max_tokens` 按官方文档设置并验证

---

## 第一期总结

### 改造范围

| 文件 | 改动类型 | 核心变更 |
|------|---------|---------|
| `models/agent_config.py` | M | `model_params` JSON 列 |
| `schemas/agent.py` | M | Schema 新增 `model_params` |
| `api/v1/comic_agent.py` | M | `update_model()` + WS `done` 事件 |
| `openai_client.py` | M | `LLMStreamChunk` + `chat_stream_with_tools()` (流式FC + Thinking + 降级) + 5 参数传透 |
| `agent_runner.py` | M | Token 管理 + 压实 + 压缩 + 限制 + 摘要轮 + ReAct降级 + 流式 + done事件 |
| `tool_executor.py` | M | 别名映射 + `file_urls` 统一结果格式 |
| `comic-agent.ts` | M | `delta`/`done` 事件 + `model_params` 类型 |
| `ComicAgentView.vue` | M | `delta`/`done` 处理 + 模型参数 Popover（5 控件）|

### 关键指标改进

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| LLM 输出体验 | 非流式，等 15s 一次性显示 | 逐 token 流式显示 |
| 长对话稳定性 | 10 轮爆 token | Token 预算管理 + 自动压实 |
| 工具调用安全 | 无限制，可能死循环 | 每工具独立上限 + 强制摘要轮 |
| 模型兼容性 | 仅 FC 模式 | FC + ReAct XML 双轨降级 |
| Thinking 展示 | 无 | 实时解析 `reasoning_content` |
| 模型参数配置 | 硬编码 | 5 个参数可视化编辑（DB 持久化）|
| 工具名容错 | 严格匹配 | 20+ 别名映射 |

---

## 第二期 TODO — Multi-Agent 并行生成 ✅ 已完成

> 目标：多格漫剧从串行变并行，4 格 120s → 40s

### Step 7: ComicOrchestrator (`orchestrator.py`) ✅

- [x] 7.1 新建 `backend/app/core/comic_chat_agent/orchestrator.py`（~310 行）
- [x] 7.2 `ComicOrchestrator` 类：`generate_comic_parallel()` 主入口（AsyncIterator 事件流）
- [x] 7.3 `_plan_frames()` — LLM 分镜规划（单次调用，输出 JSON 数组，含 markdown 清理）
- [x] 7.4 `_generate_single_frame()` — 单格生成（带 120s 超时保护）
- [x] 7.5 `asyncio.Queue` 流式事件推送 — 帧完成一个立即推送，替代 gather 阻塞方案
- [x] 7.6 `FRAME_PLANNING_PROMPT` — 6 种风格关键词 + 镜头类型
- [x] 7.7 `tool_start` × N → 并行 worker → queue → `tool_done` 逐个 yield
- [x] 7.8 容错: 单格失败/超时不影响其他格（测试验证通过）

### Step 8: WS 入口分发改造 (`comic_agent.py`) ✅

- [x] 8.1 分发条件: `use_parallel = (frames > 1 and style != "auto")`
- [x] 8.2 分发逻辑: 并行 → `ComicOrchestrator`，其他 → `agent_stream()`
- [x] 8.3 事件兼容: `tool_start` / `tool_done` 均携带 `frame` 索引
- [x] 8.4 导入: `from ...orchestrator import ComicOrchestrator`

### Step 9: 前端并行进度 UI ✅

- [x] 9.1 `tool_done` frame 精确匹配: 解析 result JSON 的 `frame` 字段定位对应 `tool_start`
- [x] 9.2 多格图片网格: 复用 `inline-images` CSS grid（2-6 格自适应）
- [x] 9.3 实时进度: thinking 事件显示 "🖼️ 进度: 2/4 格完成"
- [x] 9.4 fallback: 无 frame 字段时按 tool 名匹配（向后兼容标准模式）

### Step 10: 集成测试 ✅

- [x] 10.1 分镜规划 JSON 解析测试 — 通过
- [x] 10.2 事件流完整性测试（thinking → text → tool_start → tool_done → done）— 通过
- [x] 10.3 容错测试（1 格失败，2 格成功）— 通过
- [x] 10.4 WS 分发逻辑测试（6 种条件组合）— 通过
- [x] 10.5 前端 + 后端构建验证 — 通过

### 第二期改造文件清单

| 文件 | 改动类型 | 核心变更 |
|------|---------|---------|
| `orchestrator.py` | **新建** | ComicOrchestrator 并行调度器（分镜规划 + Queue 流式 + 容错）|
| `comic_agent.py` | M | WS 分发: frames > 1 → 并行模式 |
| `ComicAgentView.vue` | M | tool_done frame 精确匹配 |

---

## 第三期 TODO — 工作流 DAG 引擎 ✅ 已完成

> 目标：可视化编排复杂漫剧生产管线，支持断点恢复

### Step 11: DAG 核心模块迁移 ✅

- [x] 11.1 新建 `backend/app/core/comic_engine/` 包
- [x] 11.2 `dag.py` — Kahn 拓扑排序（原样迁移，56 行）
- [x] 11.3 `context.py` — 执行上下文 + 模板渲染（原样迁移，68 行）
- [x] 11.4 `checkpoint.py` — 断点管理（改用 SQLAlchemy ORM）
- [x] 11.5 DB 模型: `WorkflowDefinition` / `WorkflowExecution` / `ExecutionCheckpoint`

### Step 12: 工作流执行引擎 (`executor.py`) ✅

- [x] 12.1 节点类型: start / end / llm / tool / condition / loop / variable / merge（8 种）
- [x] 12.2 `_exec_tool()` 调用漫剧 `tool_executor.execute_tool()` + 错误 dict 检测
- [x] 12.3 `_exec_llm()` 调用漫剧 `openai_client.chat_stream()`
- [x] 12.4 DAG 拓扑排序 → 同层节点 `asyncio.gather` 并行执行
- [x] 12.5 事件回调 `on_event` 推送 node_status / llm_stream / execution_finished

### Step 13: 工作流 API 层 ✅

- [x] 13.1 CRUD: GET/POST/PUT/DELETE `/api/v1/workflows/dag`
- [x] 13.2 同步执行: POST `/api/v1/workflows/dag/{id}/execute`
- [x] 13.3 执行记录: GET `/api/v1/workflows/dag/{id}/executions`
- [x] 13.4 断点查询: GET `/api/v1/workflows/executions/{id}/checkpoint`
- [x] 13.5 断点恢复: POST `/api/v1/workflows/executions/{id}/resume`
- [x] 13.6 WebSocket 实时执行: WS `/api/v1/workflows/dag/{id}/ws`
- [x] 13.7 DB 迁移: 3 张表 + 种子数据（仙侠4格漫剧示例工作流）

### Step 14: DAG 可视化前端 ✅

- [x] 14.1 安装 `@vue-flow/core` + background + controls + minimap
- [x] 14.2 `WorkflowEditorView.vue` — 8 种自定义节点 + 拖拽添加 + 连线
- [x] 14.3 属性面板: LLM(model/prompt)/Tool(toolName/paramMapping)/Condition(branches)/Variable(expression)
- [x] 14.4 CRUD: 新建/加载/保存/删除工作流
- [x] 14.5 实时执行: WS 推送节点状态 → 画布高亮(running/done/error) + 右侧日志
- [x] 14.6 路由: `/workflow` + 侧边栏「工作流编排」菜单

### Step 15: 综合验证 ✅

- [x] 15.1 拓扑排序 + 环检测 — 通过
- [x] 15.2 ExecutionContext 变量存储 + 模板渲染 — 通过
- [x] 15.3 断点恢复: 跳过已完成节点，从中间继续 — 通过
- [x] 15.4 3 路并行 → merge → end — 通过
- [x] 15.5 条件分支 fast/quality/default — 通过
- [x] 15.6 错误节点 onError=continue — 通过
- [x] 15.7 API CRUD + 执行全流程 — 通过
- [x] 15.8 前端 Vite build — 通过

### 第三期改造文件清单

| 文件 | 改动类型 | 核心变更 |
|------|---------|---------|
| `comic_engine/__init__.py` | **新建** | 包初始化 |
| `comic_engine/dag.py` | **新建** | Kahn 拓扑排序 (56行) |
| `comic_engine/context.py` | **新建** | 变量存储 + 模板渲染 (68行) |
| `comic_engine/checkpoint.py` | **新建** | 断点管理 SQLAlchemy (170行) |
| `comic_engine/executor.py` | **新建** | 工作流引擎 8 种节点 (280行) |
| `models/workflow.py` | **新建** | 3 个 ORM 模型 |
| `schemas/workflow.py` | **新建** | Pydantic schemas |
| `api/v1/workflow.py` | **新建** | CRUD + WS 执行 + 断点恢复 |
| `main.py` | M | 注册 workflow 路由 |
| `workflow.ts` (前端API) | **新建** | REST + WS 客户端 |
| `WorkflowEditorView.vue` | **新建** | Vue Flow DAG 编辑器 |
| `router/index.ts` | M | 添加 /workflow 路由 |
| `MainLayout.vue` | M | 添加侧边栏菜单项 |
| DB 迁移 | **新建** | 3 张表 + 种子数据 |
