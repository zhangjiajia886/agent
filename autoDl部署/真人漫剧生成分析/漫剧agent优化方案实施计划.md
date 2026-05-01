# 漫剧 Agent 优化方案 — 实施计划

> 基于《漫剧agent优化方案设计.md》的逐步落地实施计划  
> 2026-04-28

---

## 零、实施总览

### 工程约束

```
运行环境:     macOS / AutoDL (Linux)
Python 版本:  3.13 (conda env: ttsapp)
后端框架:     FastAPI + SQLAlchemy (MySQL)
前端框架:     Vue3 + ElementPlus + TypeScript
后端启动:     conda activate ttsapp && cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
前端启动:     cd frontend && npm run dev
日志路径:     /tmp/ttsapp_backend.log
数据库:       ttsapp@localhost (ttsapp / ttsapp123)
```

### 三期全局时间线

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  第一期: Agent 循环加固              4-6h    ← 本文核心              │
│  ├── Step 1: LLM 客户端升级         1.5-2h                          │
│  ├── Step 2: Agent Runner 加固      2-3h                             │
│  ├── Step 3: 工具执行器增强         0.5h                             │
│  └── Step 4: 集成测试               0.5-1h                          │
│                                                                      │
│  第二期: Multi-Agent 并行生成        6-8h                            │
│  ├── Step 5: ComicOrchestrator      3-4h                             │
│  ├── Step 6: WS 入口分发改造        1-2h                             │
│  ├── Step 7: 前端并行进度 UI        1-2h                             │
│  └── Step 8: 并行性能验证           1h                               │
│                                                                      │
│  第三期: 工作流 DAG 引擎            8-10h                            │
│  ├── Step 9:  DAG 核心模块迁移      2-3h                             │
│  ├── Step 10: 工作流执行引擎        3-4h                             │
│  ├── Step 11: 工作流 API 层         1-2h                             │
│  ├── Step 12: DAG 可视化前端        2-3h                             │
│  └── Step 13: 断点恢复验证          1h                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 文件变更清单（全局）

```
第一期 — 修改 3 个文件:
  [M] backend/app/core/comic_chat_agent/openai_client.py    ← LLM 客户端升级
  [M] backend/app/core/comic_chat_agent/agent_runner.py     ← Agent 循环加固
  [M] backend/app/core/comic_chat_agent/tool_executor.py    ← 工具别名 + 结果格式

第二期 — 新增 1 个文件 + 修改 2 个文件:
  [A] backend/app/core/comic_chat_agent/orchestrator.py     ← 漫剧并行调度器
  [M] backend/app/api/v1/comic_agent.py                     ← WS 入口分发
  [M] frontend/src/components/AgentChat.vue                 ← 并行进度 UI

第三期 — 新增 5 个文件 + 修改 2 个文件:
  [A] backend/app/core/comic_engine/dag.py                  ← DAG 拓扑排序
  [A] backend/app/core/comic_engine/context.py              ← 执行上下文
  [A] backend/app/core/comic_engine/checkpoint.py           ← 断点管理
  [A] backend/app/core/comic_engine/executor.py             ← 工作流引擎
  [A] backend/app/core/comic_engine/__init__.py             ← 包入口
  [M] backend/app/api/v1/comic_agent.py                     ← 工作流 API
  [M] frontend/src/pages/WorkflowEditor.vue                 ← DAG 编辑器

[M] = 修改  [A] = 新增
```

---

## 第一期：Agent 循环加固

### Step 1: LLM 客户端升级 (`openai_client.py`)

**目标：** 从"仅 OpenAI 非流式"升级为"多 provider + 流式 FC + Thinking + 降级"。

#### 1.1 新增流式 tool_calls 累积

**当前问题：** `chat()` 是非流式的，用户等 15s 看不到任何反馈。`chat_stream()` 不支持 tool_calls。

**改造方案：** 新增 `chat_stream_with_tools()` 方法，参考 `backend-myagent2/app/llm/client.py:317-407`。

```
来源文件: backend-myagent2/app/llm/client.py
来源方法: _openai_compat_stream() — 第 317-407 行
迁移到:   backend/app/core/comic_chat_agent/openai_client.py

关键逻辑:
  1. 流式读取 SSE 响应
  2. 累积 delta.tool_calls → tool_calls_accum 字典（按 index 分组）
  3. delta.content 逐片段 yield
  4. finish_reason 出现时，拼合完整 tool_calls 列表
  5. yield 最终 LLMStreamChunk(is_done=True, tool_calls=[...])
```

**输出数据结构：**

```python
@dataclass
class LLMStreamChunk:
    text: str = ""
    is_done: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""
    tool_calls: list[ToolCall] | None = None
    is_thinking: bool = False  # 标记是否为思考内容
```

**验证标准：**
- [ ] 调用 Claude-sonnet 带 tools → 逐 token 返回文字 + 最终返回 tool_calls
- [ ] 调用纯聊天（无 tool_calls）→ 逐 token 返回到结束

#### 1.2 新增 Thinking/Reasoning 支持

**当前问题：** Claude/Qwen3 的思考过程被吞掉，用户看不到推理链。

**改造方案：** 解析 `delta.reasoning_content` 和 `<think>` 标签。

```
来源文件: backend-myagent2/app/llm/client.py
来源逻辑: 第 362-377 行 (reasoning_content 检测) + 第 267-279 行 (southgrid think 检测)
迁移到:   openai_client.py 的 chat_stream_with_tools() 内

关键逻辑:
  if delta 有 reasoning_content 或 thinking 字段:
      if 不在 thinking 状态:
          yield LLMStreamChunk(text="<thinking>", is_thinking=True)
          进入 thinking 状态
      yield LLMStreamChunk(text=reasoning_text, is_thinking=True)
  if delta 有 content:
      if 在 thinking 状态:
          yield LLMStreamChunk(text="</thinking>")
          退出 thinking 状态
      yield LLMStreamChunk(text=content)
```

**验证标准：**
- [ ] 调用 Qwen3-32B → 返回 `<thinking>...</thinking>` 包裹的推理内容
- [ ] 前端能渲染折叠的思考过程

#### 1.3 新增模型降级机制

**当前问题：** 某些模型不支持流式 + tools 组合，直接报错。

**改造方案：** 参考 `backend-myagent2/app/llm/client.py:341-358`。

```
来源逻辑:
  全局集合 _MODELS_NO_TOOLS_STREAM: set[str] = set()
  
  try:
      response = await client.chat.completions.create(**kwargs)
  except Exception as e:
      if kwargs.get("tools") and "invalid_request_error" in str(e):
          _MODELS_NO_TOOLS_STREAM.add(model)  # 标记该模型
          kwargs.pop("tools")                   # 移除 tools
          response = await client.chat.completions.create(**kwargs)  # 重试
      else:
          raise

效果: 第一次失败后自动标记，后续请求跳过 tools → 模型只做纯聊天
```

**验证标准：**
- [ ] 对不支持 FC 的模型（如某些 DeepSeek）→ 第一次报错后自动降级
- [ ] 后续请求直接走无 tools 模式

#### 1.4 保留南格 HMAC 接口位置（暂不实现）

**说明：** 南格 HMAC 签名需要 `southgrid_auth.py`（约 40 行），依赖南格平台的 custcode 和签名算法。当前漫剧 Agent 主要用 AIPro 聚合平台，南格对接可以在 P1 阶段实现。

```
预留结构:
  openai_client.py 中保留 provider 路由入口：
    if provider == "southgrid":
        raise NotImplementedError("南格 HMAC 支持将在 P1 阶段实现")
    elif provider == "openai":
        return self._openai_stream(...)   # 当前实现
    elif provider == "ollama":
        raise NotImplementedError("Ollama 支持将在 P1 阶段实现")
```

---

### Step 2: Agent Runner 加固 (`agent_runner.py`)

**目标：** 加入 6 项关键防护机制，让 Agent 循环从"能跑"变"稳定跑"。

#### 2.1 Token 预算管理

**当前问题：** 长对话 10 轮后 token 爆炸，LLM 返回错误。

**改造方案：** 移植 3 个函数。

```
来源文件: backend-myagent2/app/agent/loop.py
来源函数/行号:
  _CHARS_PER_TOKEN = 2.5              (第 192 行)
  _estimate_tokens(messages)          (第 194-199 行)
  _compact_history_simple(messages)   (第 202-222 行)
  TOKEN_COMPACT_THRESHOLD = 10000     (第 225 行)

迁移到: agent_runner.py 顶部（作为模块级函数）

关键改造点:
  1. 每轮循环前调用 _estimate_tokens(messages)
  2. 超过 TOKEN_COMPACT_THRESHOLD → 调用 _compact_history_simple()
  3. 超 75% 时注入紧张提示到 system prompt

适配修改:
  TOKEN_COMPACT_THRESHOLD 可能需要调整为 8000（漫剧 prompt 更长，含风格词）
```

**在 `agent_stream()` 中的插入位置：**

```python
# agent_runner.py — agent_stream() 循环内，LLM 调用前
for iteration in range(MAX_ITERATIONS):
    # ── 新增: Token 预算管理 ──
    est_tokens = _estimate_tokens(messages)
    if est_tokens > TOKEN_COMPACT_THRESHOLD:
        messages = _compact_history_simple(messages)
        logger.info(f"[AgentRunner] Token 压实: {est_tokens} → {_estimate_tokens(messages)}")
    
    budget_pct = est_tokens / 32000
    if budget_pct >= 0.75:
        # 注入紧张提示
        messages[0]["content"] += (
            f"\n\n【⚠️ 上下文紧张: {est_tokens}/32000 tokens({budget_pct:.0%})】"
            "请立即输出最终结论，禁止再调用超过1次工具。"
        )
    
    # ── 原有: LLM 调用 ──
    ...
```

**验证标准：**
- [ ] 20 轮对话 → token 估算日志递增 → 超阈值后自动压实
- [ ] 压实后 LLM 仍能正常回复（不丢关键上下文）

#### 2.2 工具结果压缩

**当前问题：** 工具返回的完整 JSON 被注入对话历史，浪费 token。例如 `generate_image` 返回 `{"status": "success", "image_url": "/uploads/..."}` 是简单的，但未来工具返回可能很大。

**改造方案：** 移植 `_compact_tool_result()` 函数。

```
来源文件: backend-myagent2/app/agent/loop.py
来源函数: _compact_tool_result() — 第 145-188 行

迁移到: agent_runner.py 顶部

漫剧版适配:
  原版针对 bash/python/mysql 工具，漫剧版需要针对视觉工具：

  def _compact_tool_result(tool_name: str, result: dict) -> str:
      if "error" in result:
          return f"[{tool_name}] ❌ 错误: {str(result['error'])[:300]}"
      
      parts = [f"[{tool_name}] ✓"]
      
      if result.get("image_url"):
          parts.append(f"图片: {result['image_url']}")
      if result.get("video_url"):
          parts.append(f"视频: {result['video_url']}")
      if result.get("audio_url"):
          parts.append(f"音频: {result['audio_url']}")
      if result.get("status") == "not_implemented":
          parts.append("(功能尚未实现)")
      
      return "\n".join(parts)
```

**在 `agent_stream()` 中的修改位置：**

```python
# 当前代码（完整 JSON 注入）:
messages.append({
    "role": "tool",
    "tool_call_id": tc.id,
    "content": json.dumps(result, ensure_ascii=False),
})

# 改为（压缩后注入）:
messages.append({
    "role": "tool",
    "tool_call_id": tc.id,
    "content": _compact_tool_result(tc.name, result),
})
```

**验证标准：**
- [ ] `generate_image` 结果注入 → 仅 1 行 `[generate_image] ✓ 图片: /uploads/xxx.png`
- [ ] 错误结果注入 → `[generate_image] ❌ 错误: ComfyUI 连接失败`

#### 2.3 工具调用次数限制

**当前问题：** LLM 可能进入死循环，无限调用 `generate_image`。

**改造方案：**

```
来源文件: backend-myagent2/app/agent/loop.py
来源逻辑: MAX_TOOL_CALLS_PER_TOOL (第 115-119 行) + 检查逻辑 (第 536-542 行)

漫剧版配置:
  MAX_TOOL_CALLS_PER_TOOL = {
      "generate_image": 8,           # 最多 8 格漫剧
      "generate_image_with_face": 6,  # 人脸保持
      "edit_image": 4,               # 编辑
      "image_to_video": 3,           # 图生视频
      "upscale_image": 4,            # 超分
      "text_to_speech": 6,           # TTS
      "merge_media": 2,              # 合成
      "add_subtitle": 2,             # 字幕
  }
```

**在 `agent_stream()` 中的插入位置：**

```python
# agent_runner.py — 工具执行前
tool_call_counts: dict[str, int] = {}  # 循环外声明

# 在每次工具执行前:
tool_call_counts[tc.name] = tool_call_counts.get(tc.name, 0) + 1
limit = MAX_TOOL_CALLS_PER_TOOL.get(tc.name, 0)
if limit and tool_call_counts[tc.name] > limit:
    result = {"error": f"工具 {tc.name} 本次对话已调用 {limit} 次，已达上限"}
    yield {"type": "tool_done", "tool": tc.name, "result": json.dumps(result)}
    messages.append({"role": "tool", "tool_call_id": tc.id,
                     "content": _compact_tool_result(tc.name, result)})
    continue
```

**验证标准：**
- [ ] 让 LLM 连续生成 9 张图片 → 第 9 次返回限制错误
- [ ] LLM 收到错误后自行总结

#### 2.4 强制摘要轮

**当前问题：** 达到 MAX_ITERATIONS 后直接 yield 一行提示，用户不知道之前做了什么。

**改造方案：**

```
来源文件: backend-myagent2/app/agent/loop.py
来源逻辑: 第 338 行 range(MAX_TOOL_ROUNDS + 1) + 第 367-373 行

改造:
  MAX_ITERATIONS = 8  →  MAX_ITERATIONS = 10  (增加 2 轮余量)
  
  for iteration in range(MAX_ITERATIONS + 1):  # +1 for 摘要轮
      is_summary_round = iteration == MAX_ITERATIONS
      
      if is_summary_round:
          # 注入强制总结指令，移除工具
          messages.append({
              "role": "user",
              "content": "[系统提示] 已达到最大工具轮次，请根据已有结果给出完整的最终回答，不要再调用任何工具。"
          })
          # LLM 调用时 tools=None
```

**验证标准：**
- [ ] 设 MAX_ITERATIONS=3 进行测试 → 第 4 轮 LLM 输出总结性回答
- [ ] 总结中包含之前生成的图片/视频 URL 引用

#### 2.5 ReAct XML 降级

**当前问题：** 南格 Qwen3 不支持 OpenAI Function Calling 格式，需要文本解析工具调用。

**改造方案：**

```
来源文件: backend-myagent2/app/agent/loop.py
来源逻辑:
  REACT_CALL_INSTRUCTION (第 137-141 行) — 工具调用格式指令
  _parse_react_tool_calls() (第 758-802 行) — 文本解析工具调用

迁移到: agent_runner.py

关键逻辑:
  1. 如果 LLM 返回无 tool_calls（FC 方式为空）
  2. 检查回复文本中是否包含 <tool_call>...</tool_call>
  3. 解析 JSON → 构造 ToolCall 对象
  4. 继续正常工具执行流程

ReAct 指令注入:
  在 system prompt 末尾追加:
  """
  ## 工具调用
  如需使用工具，在回复中插入：
  <tool_call>{"name": "工具名", "arguments": {...}}</tool_call>
  ⚠️ 生成 </tool_call> 后立即停止，不要预测工具结果。
  """
```

**在 `agent_stream()` 中的插入位置：**

```python
# 在处理 LLM 响应后，检测 tool_calls 前:
if not response.tool_calls and response.content:
    # ReAct 降级解析
    parsed_calls = _parse_react_tool_calls(response.content)
    if parsed_calls:
        response.tool_calls = parsed_calls
        logger.info(f"[AgentRunner] ReAct 解析到 {len(parsed_calls)} 个工具调用")
```

**验证标准：**
- [ ] 使用不支持 FC 的模型 → LLM 输出 `<tool_call>` → 解析成功 → 工具执行
- [ ] 使用支持 FC 的模型 → 正常 FC 流程不受影响

#### 2.6 流式输出改造

**当前问题：** LLM 调用是非流式的，用户等 15s 看到心跳消息，然后一次性显示全文。

**改造方案：** 将 `_call_llm_with_heartbeat()` 替换为流式调用。

```
当前流程:
  _call_llm_with_heartbeat() → 非流式 llm.chat() → 心跳 → 一次性返回

改造后流程:
  llm.chat_stream_with_tools() → 逐 chunk yield → 最终返回 tool_calls

核心改动:
  1. 删除 _call_llm_with_heartbeat() 函数
  2. 在 agent_stream() 循环内直接调用 llm.chat_stream_with_tools()
  3. 逐 chunk yield {"type": "delta", "content": chunk.text}
  4. 累积文字用于后续处理
  5. 最终 chunk 中提取 tool_calls

注意: 
  前端需要新增 "delta" 事件类型处理（逐字追加到当前消息）
  原有 "text" 事件用于完整文字块（工具结果说明等）
```

**验证标准：**
- [ ] 前端接收 delta 事件 → 逐字显示 LLM 回复
- [ ] 流式结束后正确提取 tool_calls → 工具执行

#### 2.7 完成统计 (done 事件)

**改造方案：** 在 agent_stream() 结束前 yield 统计信息。

```python
# 在 agent_stream() 最后 return 前:
yield {
    "type": "done",
    "metadata": {
        "model": model_name,
        "iterations": iteration + 1,
        "total_tool_calls": sum(tool_call_counts.values()),
        "tools_used": list(tool_call_counts.keys()),
        "input_tokens": total_input_tokens,    # 从流式 chunk 累积
        "output_tokens": total_output_tokens,   # 从流式 chunk 累积
    },
}
```

---

### Step 3: 工具执行器增强 (`tool_executor.py`)

#### 3.1 工具别名映射

**目标：** LLM 经常输出非标准工具名，需要别名映射。

```python
# tool_executor.py 顶部新增

TOOL_ALIASES: dict[str, str] = {
    # 图片生成
    "gen_image": "generate_image",
    "create_image": "generate_image",
    "text_to_image": "generate_image",
    "t2i": "generate_image",
    "draw": "generate_image",
    "paint": "generate_image",
    
    # 人脸保持
    "face_gen": "generate_image_with_face",
    "face_image": "generate_image_with_face",
    "instantid": "generate_image_with_face",
    
    # 图像编辑
    "image_edit": "edit_image",
    "modify_image": "edit_image",
    
    # 图生视频
    "img2video": "image_to_video",
    "i2v": "image_to_video",
    "animate_image": "image_to_video",
    
    # 超分
    "upscale": "upscale_image",
    "super_resolution": "upscale_image",
    "enhance_image": "upscale_image",
    
    # TTS
    "tts": "text_to_speech",
    "speak": "text_to_speech",
    "voice": "text_to_speech",
    
    # 媒体合成
    "merge": "merge_media",
    "combine": "merge_media",
    
    # 字幕
    "subtitle": "add_subtitle",
    "add_sub": "add_subtitle",
}
```

**修改 `execute_tool()` 函数：**

```python
async def execute_tool(tool_name: str, params: dict) -> dict:
    # 别名解析
    canonical_name = TOOL_ALIASES.get(tool_name, tool_name)
    if canonical_name != tool_name:
        logger.info(f"[ToolExec] 别名解析: {tool_name} → {canonical_name}")
    
    executor = TOOL_EXECUTORS.get(canonical_name)
    if not executor:
        return {"status": "error", "error": f"未知工具: {tool_name}（也不在别名映射中）"}
    return await executor(params)
```

#### 3.2 统一结果格式

**目标：** 确保所有工具返回包含 `file_urls` 字段（用于压缩函数识别）。

```python
# 在每个 execute_xxx 函数的返回值中，添加 file_urls 字段:

# execute_generate_image:
return {
    "status": "success", 
    "image_url": url,
    "file_urls": [{"type": "image", "url": url}],  # 新增
}

# execute_image_to_video:
return {
    "status": "success", 
    "video_url": url,
    "file_urls": [{"type": "video", "url": url}],  # 新增
}

# execute_text_to_speech:
return {
    "status": "success", 
    "audio_url": url,
    "file_urls": [{"type": "audio", "url": url}],  # 新增
}
```

---

### Step 4: 集成测试

#### 4.1 启动验证

```bash
# 1. 启动后端
conda activate ttsapp && cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. 检查日志无报错
tail -f /tmp/ttsapp_backend.log

# 3. 启动前端
cd frontend && npm run dev
```

#### 4.2 测试用例

| 编号 | 测试场景 | 期望结果 | 验证命令/操作 |
|------|---------|---------|--------------|
| T1 | 简单聊天 | 流式逐字返回，无工具调用 | 发送 "你好" |
| T2 | 单图生成 | 流式文字 + tool_start + tool_done + image_url | 发送 "画一张仙侠剑客" |
| T3 | 长对话稳定性 | 10 轮后自动压实，不爆 token | 连续发送 10 条创作请求 |
| T4 | 工具限制 | 第 9 次 generate_image 返回限制错误 | 发送 "画 9 张不同的图" |
| T5 | 强制摘要 | 超过 MAX_ITERATIONS 后给出完整总结 | 设 MAX=3，连续创作 |
| T6 | 别名解析 | `t2i` → `generate_image` 正常执行 | 修改 tools 让 LLM 看到 t2i |
| T7 | 模型降级 | 不支持 FC 的模型自动降级 | 选择一个不支持 FC 的模型 |
| T8 | Thinking 展示 | Qwen3 思考过程正确显示 | 使用 Qwen3 模型 |

#### 4.3 回归检查

- [ ] 前端原有功能（模型/工具/工作流/提示词管理）不受影响
- [ ] WebSocket 连接稳定，无断连
- [ ] 历史对话加载正常
- [ ] 工具执行（ComfyUI / TTS）功能正常

---

## 第二期：Multi-Agent 并行生成

### Step 5: ComicOrchestrator (`orchestrator.py`)

#### 5.1 文件结构

```python
# backend/app/core/comic_chat_agent/orchestrator.py

"""
漫剧并行生成调度器 —— 多格漫剧并行生成，4 倍提速。

架构:
  Phase 1: 分镜规划 Agent（单次 LLM 调用）
  Phase 2: 并行图像生成（asyncio.gather + ComfyUI）
  Phase 3: 可选 TTS 旁白

来源: backend-myagent2/app/agent/orchestrator.py 简化版
"""
```

#### 5.2 核心类设计

```python
class ComicOrchestrator:
    """漫剧多格并行调度"""
    
    async def generate_comic_parallel(
        self,
        user_message: str,
        model_config: ModelConfig,
        db: AsyncSession,
        num_frames: int = 4,
        style: str = "auto",
    ) -> AsyncIterator[dict]:
        """主入口: 分镜 → 并行生成 → 汇总"""
    
    async def _plan_frames(
        self,
        llm: OpenAICompatClient,
        user_message: str,
        num_frames: int,
        style: str,
    ) -> list[dict]:
        """Phase 1: LLM 生成分镜描述 (JSON)"""
    
    async def _generate_frame(
        self,
        frame_desc: dict,
        style: str,
        frame_idx: int,
        queue: asyncio.Queue,
    ) -> dict:
        """Phase 2 单任务: 生成单格图片"""
    
    async def _merge_events(
        self,
        queue: asyncio.Queue,
        total: int,
    ) -> AsyncIterator[dict]:
        """合并多个并行任务的事件"""
```

#### 5.3 分镜规划 Prompt

```python
FRAME_PLANNING_PROMPT = """你是分镜规划师。根据用户的故事描述，生成 {num_frames} 格分镜。

输出 JSON 数组，每格包含:
- frame_number: 格号 (1-{num_frames})
- scene: 场景描述（中文）
- prompt: 英文绘图提示词（含质量词 + 风格词）
- camera: 镜头类型（close-up/medium/wide/panoramic）

风格: {style_name}
风格词: {style_keywords}

示例输出:
```json
[
  {{"frame_number": 1, "scene": "白衣剑客站在雪山之巅", "prompt": "masterpiece, best quality, xianxia style, white-robed swordsman standing on snowy mountain peak, epic sky, cinematic", "camera": "wide"}}
]
```

直接输出 JSON，不要其他文字。"""
```

#### 5.4 并行执行逻辑

```
来源参考: backend-myagent2/app/agent/orchestrator.py — _run_parallel() 方法

核心逻辑:
  1. 创建 asyncio.Queue() 用于事件合并
  2. 每个 frame 创建独立 asyncio.Task
  3. Task 内: 
     a. queue.put({"type": "tool_start", "frame": idx})
     b. 调用 execute_generate_image(params)
     c. queue.put({"type": "tool_done", "frame": idx, "image_url": url})
  4. 主循环 await asyncio.gather(*tasks)
  5. 同时从 queue 读取事件 yield 给前端

与 MyAgent2 的区别:
  - MyAgent2 的并行是多个 AgentLoop 并行（每个含 LLM 调用）
  - 漫剧版的并行是多个 ComfyUI 调用并行（图片生成，无 LLM）
  - 更简单，但效果更显著（图片生成是瓶颈，每张 20-30s）
```

**验证标准：**
- [ ] 4 格漫剧 → 4 张图并行生成 → 总时间 ≈ 单张时间 + 规划时间
- [ ] 前端能实时看到每格的 tool_start/tool_done 事件
- [ ] 某一格失败不影响其他格

---

### Step 6: WS 入口分发改造 (`comic_agent.py`)

**改造位置：** WebSocket 端点，根据意图分发到不同处理路径。

```python
# 在 websocket_agent_chat() 中

# 判断是否走并行模式
use_parallel = (
    model_config is not None  # 有模型配置
    and agent_mode == "agent"  # Agent 模式（非 smart/mock）
    and num_frames > 1         # 多格漫剧
    and intent in ("comic", "t2i")  # 漫剧或多图意图
)

if use_parallel:
    from app.core.comic_chat_agent.orchestrator import ComicOrchestrator
    orch = ComicOrchestrator()
    async for event in orch.generate_comic_parallel(
        message, model_config, db, num_frames, style
    ):
        await websocket.send_json(event)
else:
    # 原有逻辑：标准 Agent 循环
    async for event in agent_stream(message, model_config, db, history):
        await websocket.send_json(event)
```

---

### Step 7: 前端并行进度 UI

**目标：** 前端显示多格并行生成的进度。

```
改造文件: frontend/src/components/AgentChat.vue (或对应组件)

新增 UI 元素:
  1. 并行进度条: 显示 "已完成 2/4 格"
  2. 多格缩略图网格: 已完成的格显示缩略图，生成中的显示 loading
  3. 整体进度动画

事件处理:
  case "tool_start":
    if event.input?.frame:
      markFrameLoading(event.input.frame)
  case "tool_done":
    if event.image_url && event.input?.frame:
      setFrameImage(event.input.frame, event.image_url)
      updateProgress()
```

---

### Step 8: 并行性能验证

| 编号 | 测试场景 | 期望结果 |
|------|---------|---------|
| T9 | 4 格仙侠漫剧 | 总时间 < 单格时间 × 2 |
| T10 | 6 格动漫漫剧 | 6 张图并行生成 |
| T11 | 单格超时 | 其他格不受影响，超时格返回错误 |
| T12 | 单图生成 | 走标准 Agent 路径，不走并行 |
| T13 | 对话+漫剧交替 | 模式切换正确，历史不混乱 |

---

## 第三期：工作流 DAG 引擎

### Step 9: DAG 核心模块迁移

#### 9.1 目录结构

```
backend/app/core/comic_engine/
  __init__.py          ← 包入口
  dag.py               ← 拓扑排序（原样迁移自 backend-myagent2）
  context.py           ← 执行上下文（原样迁移）
  checkpoint.py        ← 断点管理（改用 SQLAlchemy）
  executor.py          ← 工作流引擎（适配漫剧工具）
```

#### 9.2 dag.py — 原样迁移

```
来源: backend-myagent2/app/engine/dag.py (56 行)
改动: 无，直接复制
功能: Kahn 拓扑排序 → 返回可并行执行的 batch 列表
```

#### 9.3 context.py — 原样迁移

```
来源: backend-myagent2/app/engine/context.py (68 行)
改动: 无，直接复制
功能: 变量存储 + 模板渲染 ({{variable.path}})
```

#### 9.4 checkpoint.py — 改用 SQLAlchemy

```
来源: backend-myagent2/app/engine/checkpoint.py (168 行)
改动: 
  - 将 aiosqlite 直接 SQL 改为 SQLAlchemy ORM
  - 新增 ExecutionCheckpoint SQLAlchemy 模型
  - save/load/delete 方法改用 db.execute() + session.commit()
```

**需要新增数据库表：**

```sql
CREATE TABLE execution_checkpoints (
    id VARCHAR(64) PRIMARY KEY,
    execution_id VARCHAR(64) NOT NULL,
    node_id VARCHAR(64),
    state JSON,
    completed_nodes JSON,
    checkpoint_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_execution_id (execution_id)
);
```

---

### Step 10: 工作流执行引擎 (`executor.py`)

```
来源: backend-myagent2/app/engine/executor.py (530 行)
改动:
  - 精简节点类型: 保留 start/end/llm/tool/condition/loop/variable/merge
  - 移除 skill/subflow（漫剧场景暂不需要）
  - _exec_tool() 改为调用漫剧 tool_executor.execute_tool()
  - _exec_llm() 改为调用漫剧 openai_client
  - WebSocket 推送改为漫剧的 WS 通道
  - DB 操作改用 SQLAlchemy
```

---

### Step 11: 工作流 API 层

**新增 API 端点：**

```python
# 在 comic_agent.py 或新建 workflow_api.py

@router.get("/workflows/dag")              # 列表
@router.post("/workflows/dag")             # 创建
@router.get("/workflows/dag/{id}")         # 详情
@router.put("/workflows/dag/{id}")         # 更新
@router.delete("/workflows/dag/{id}")      # 删除
@router.post("/workflows/dag/{id}/execute")  # 执行
@router.get("/workflows/dag/{id}/status")   # 执行状态
@router.post("/workflows/dag/{id}/resume")  # 断点恢复
```

**需要新增数据库表：**

```sql
CREATE TABLE workflow_definitions (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    definition JSON NOT NULL,     -- nodes + edges + variables
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE workflow_executions (
    id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64) NOT NULL,
    status ENUM('running', 'done', 'error', 'cancelled') DEFAULT 'running',
    inputs JSON,
    outputs JSON,
    node_statuses JSON,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    FOREIGN KEY (workflow_id) REFERENCES workflow_definitions(id)
);
```

---

### Step 12: DAG 可视化前端

**技术选型：** Vue Flow (vue-flow.js) — Vue3 的节点图编辑器。

```
前端新增页面: frontend/src/pages/WorkflowEditor.vue

功能:
  1. 节点拖拽 — 从侧边栏拖入 LLM/Tool/Condition/Loop 节点
  2. 连线 — 可视化定义 edges（数据流向）
  3. 节点配置面板 — 点击节点弹出配置表单
  4. 保存/加载 — 对接 workflow_definitions API
  5. 执行 — 点击运行 → 实时高亮正在执行的节点
  6. 断点恢复 — 从最后一个 checkpoint 恢复

依赖安装:
  npm install @vue-flow/core @vue-flow/background @vue-flow/controls @vue-flow/minimap
```

---

### Step 13: 断点恢复验证

| 编号 | 测试场景 | 期望结果 |
|------|---------|---------|
| T14 | 4 节点工作流正常执行 | 全部节点依次/并行完成 |
| T15 | 执行中断（kill 后端） | 重启后从 checkpoint 恢复 |
| T16 | 条件分支 | if/else 正确路由 |
| T17 | 循环节点 | 指定次数循环 + 退出条件 |
| T18 | 并行节点 | 同层 2 个 tool 节点并行执行 |

---

## 附录 A: 前端事件协议（第一期需适配）

### 新增/修改事件类型

```typescript
// 现有事件（保持不变）
type AgentEvent =
  | { type: "thinking"; content: string }
  | { type: "text"; content: string }
  | { type: "tool_start"; tool: string; input: Record<string, unknown> }
  | { type: "tool_done"; tool: string; result: string; image_url?: string; video_url?: string; audio_url?: string }
  | { type: "error"; content: string }

// 新增事件（第一期）
  | { type: "delta"; content: string }       // 流式文字增量（逐 token）
  | { type: "done"; metadata: {              // 完成统计
      model: string;
      iterations: number;
      total_tool_calls: number;
      tools_used: string[];
      input_tokens: number;
      output_tokens: number;
    }}

// 前端处理 "delta" 事件:
//   将 content 追加到当前 assistant 消息的末尾（而非替换）
//   与 "text" 的区别: "text" 是完整段落，"delta" 是增量片段
```

---

## 附录 B: 数据库迁移脚本

### 第一期：无数据库变更

第一期的所有改动都在 Python 代码层面，不涉及数据库变更。

### 第二期：无数据库变更

并行调度通过内存状态管理，不需要额外表。

### 第三期：新增 2 张表

```sql
-- 工作流定义表
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    definition JSON NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 工作流执行记录表
CREATE TABLE IF NOT EXISTS workflow_executions (
    id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64) NOT NULL,
    status ENUM('running', 'done', 'error', 'cancelled') DEFAULT 'running',
    inputs JSON,
    outputs JSON,
    node_statuses JSON,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    FOREIGN KEY (workflow_id) REFERENCES workflow_definitions(id),
    INDEX idx_workflow_id (workflow_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 执行断点表
CREATE TABLE IF NOT EXISTS execution_checkpoints (
    id VARCHAR(64) PRIMARY KEY,
    execution_id VARCHAR(64) NOT NULL,
    node_id VARCHAR(64),
    state JSON,
    completed_nodes JSON,
    checkpoint_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_execution_id (execution_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 附录 C: 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 流式改造破坏现有前端 | 🔴 高 | 中 | 保留原 "text" 事件兼容，"delta" 为新增 |
| Token 压实丢失关键上下文 | 🔴 高 | 低 | 保留最近 6 条完整，只压缩中间 |
| 并行生成 ComfyUI 并发限制 | ⚠️ 中 | 高 | 限制最大并行数为 ComfyUI GPU 数量 |
| ReAct 解析误触发 | ⚠️ 中 | 低 | 仅在 FC 返回空时启用解析 |
| 工具别名冲突 | ⚪ 低 | 极低 | 别名 → 标准名映射是单射 |
| DAG 引擎 SQLAlchemy 适配 | ⚠️ 中 | 中 | 第三期重点测试 |

---

## 附录 D: 回滚方案

每一期改造前，创建 Git 分支：

```bash
# 第一期
git checkout -b feature/agent-hardening

# 第二期
git checkout -b feature/parallel-comic

# 第三期
git checkout -b feature/dag-engine
```

如果某一期出现无法修复的问题，直接切回 main 分支：

```bash
git checkout main
```

所有改动都限制在明确的文件范围内（见文件变更清单），不影响其他模块。
