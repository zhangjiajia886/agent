# Agent 面临的问题与优化设计方案

> 2026-04-29 · 基于测试案例深度分析 + ComfyUI 实测验证

---

## 一、核心痛点总览

| # | 痛点 | 严重度 | 根因定位 | 实测验证 |
|---|------|--------|---------|---------|
| 1 | Agent 卡顿，需反复点"继续" | P0 | agent_runner.py:410-435 循环退出逻辑缺陷 | 测试案例中用户点了 20+ 次 |
| 2 | 图生视频完全失效 | P0 | tool_executor.py 未上传图片到远程 ComfyUI | ComfyUI 返回 400: Invalid image file |
| 3 | 审批疲劳 | P1 | AUTO_APPROVE_TOOLS 只有 6 个只读工具 | 一次任务 20+ 次批准点击 |
| 4 | Agent 过度执行 | P1 | System Prompt 执行边界约束不足 | 要求 1 张图却生了 20+ 张 |
| 5 | 跨轮上下文丢失 | P1 | _compact_history 截断媒体路径 | Agent 每轮重新 list_dir 找文件 |
| 6 | Thinking 噪音 | P2 | thinking chunk 直接透传 | 英文推理大段输出到前端 |

---

## 二、痛点 1: Agent 循环卡顿（P0）

### 2.1 现象

用户发一条消息后，Agent 经常执行 1-2 个工具就停下来，前端显示"工具执行完毕，分析结果中..."后卡住。用户必须手动发"继续"才能推进。一个 3 步任务（搜索 + 写文件 + 生图）实际需要用户介入 6+ 次。

### 2.2 根因分析

**核心代码: `agent_runner.py:410-435`**

```python
# 当前逻辑（有缺陷）
if not final_tool_calls:
    has_plan = bool(accumulated_text and (
        re.search(r"(?:第[1-9一二三四五六]步|步骤\s*[1-9]|^\s*\d+[\.\)、])", text, re.M)
        or re.search(r"(分\s*\d+\s*步|我来|开始执行|先.*然后)", text)
    ))
    if has_plan and iteration < MAX_ITERATIONS - 1:
        # 强制下轮调工具
        force_tool_choice = "required"
        continue
    break  # ← 致命: 不匹配 has_plan 就直接退出
```

**原理解释:**

ReAct 循环的每一轮: LLM 输出 → 检查是否有 tool_call → 有则执行工具 → 无则判断退出。

问题在于 LLM 在分析工具结果时，经常输出类似:

> "搜索结果已写入 search_result.md，接下来我来根据要点生成图片。"

这句话不匹配 `has_plan` 正则（不含"第X步"/"步骤X"/"分N步"），所以走到 `break` 直接退出循环。但实际上 Agent 还有下一步要做。

**根本矛盾:** 当前设计用正则匹配来判断"任务是否完成"——这是不可靠的。LLM 的自然语言输出千变万化，任何正则都无法覆盖所有情况。

### 2.3 设计方案: 显式完成信号 + 自动续行

**原理:** 不依赖正则猜测 LLM 意图，而是让 LLM 显式声明任务状态。同时引入"工具执行后自动续行"机制——如果本轮执行了工具但下一轮 LLM 没有调用新工具也没有声明完成，则自动续行。

**改动文件:** `agent_runner.py`

**改动 1: System Prompt 增加完成信号指令**

在 `DEFAULT_SYSTEM_PROMPT` 末尾新增:

```
## 执行规范
1. 每次工具返回结果后，立即检查结果:
   - 成功: 记录产出（文件路径/URL），继续执行下一步
   - 失败: 分析原因，尝试修复（最多重试 1 次），然后继续
2. 所有步骤完成后，必须输出完成标记: [TASK_DONE]
   并附上完成汇报（已完成的步骤 + 产出列表）
3. 只有在任务真正全部完成时才输出 [TASK_DONE]
4. 严格按用户要求的数量执行，不要多做。用户要 1 张图就生 1 张，完成后汇报并等待反馈
5. 记住每步产出的文件路径，后续步骤直接引用，不要重新查找
```

**改动 2: 替换 break 逻辑为显式完成检测 + 自动续行**

```python
# 新逻辑（替换 agent_runner.py:410-435）
if not final_tool_calls:
    text = accumulated_text.strip()
    
    # 1. 检测显式完成信号
    task_done = "[TASK_DONE]" in text
    
    # 2. 检测是否有未执行的计划
    has_plan = bool(text and (
        re.search(r"(?:第[1-9一二三四五六]步|步骤\s*[1-9]|^\s*\d+[\.\)、])", text, re.M)
        or re.search(r"(分\s*\d+\s*步|我来|开始执行|先.*然后|接下来)", text)
    ))
    
    # 3. 检测是否在分析工具结果（中间状态）
    #    如果上一轮执行了工具，且本轮 LLM 只是分析结果没有调用新工具，
    #    这通常意味着 Agent 还在"思考下一步"，应该自动续行
    tools_executed_before = sum(tool_call_counts.values()) > 0
    is_mid_task = tools_executed_before and not task_done and iteration < MAX_ITERATIONS - 2
    
    if task_done:
        # 真正完成，退出循环
        logger.info(f"[AgentRunner] TASK_DONE after {iteration + 1} iters")
        break
    elif has_plan or is_mid_task:
        # 自动续行
        inject_msg = (
            "[系统提示] 请继续执行下一步。如果所有任务已完成，请输出 [TASK_DONE] 并汇报结果。"
            if is_mid_task else
            "[系统提示] 你列出了计划但没有调用工具。请立即执行第一步，直接调用工具。"
        )
        messages.append({"role": "user", "content": inject_msg})
        force_tool_choice = "required" if has_plan else None
        yield {"type": "thinking", "content": "🔄 自动续行: Agent 继续执行..."}
        continue
    else:
        # 没有工具调用、没有计划、也没有完成信号 → 可能是纯聊天回复
        logger.info(f"[AgentRunner] 自然结束 after {iteration + 1} iters")
        break
```

**原理:** 引入三层判断:
1. **显式完成** (`[TASK_DONE]`): 最可靠的信号，LLM 自己声明任务完成
2. **计划续行** (`has_plan`): 保留原有逻辑，Agent 有计划但没执行时强制调工具
3. **中间状态续行** (`is_mid_task`): 新增关键逻辑——如果之前执行过工具，且现在既不是完成也不是计划，很可能是 Agent 在分析结果。注入续行提示让它继续

这样就解决了"Agent 输出分析文字后卡住"的问题——分析文字会被识别为中间状态，自动续行。

**改动 3: 提升 MAX_ITERATIONS**

```python
MAX_ITERATIONS = 15  # 从 10 提升到 15
```

理由: 一个典型的多步任务（搜索 + 写文件 + 生图 + 转视频）至少需要 8 轮有效迭代（4 次工具调用 + 4 次结果分析）。加上偶尔的续行开销，10 轮太紧。15 轮给足余量。

---

## 三、痛点 2: 图生视频失效（P0）

### 3.1 现象

Agent 调用 image_to_video 工具后，前端无视频返回。Agent 不知道成功还是失败，也不主动检查。

### 3.2 根因（已通过测试确认）

**运行诊断脚本输出:**
```
ComfyUI 健康检查... ✅ 在线
wan_i2v 工作流... ✅ 加载成功，14 个节点
提交到 ComfyUI:
  ComfyUI 400: Prompt outputs failed validation
  9(LoadImage): ['image - Invalid image file: /Users/zjj/.../cfeacdb47678.png']
```

**根因确认:** `tool_executor.py` 的 `execute_image_to_video()` 把**本地文件路径**直接注入到 ComfyUI 工作流的 `LoadImage` 节点。但 ComfyUI 运行在**远程 AutoDL 服务器**上，无法读取本地路径。

**同一 BUG 影响的全部 4 个工具:**

| 工具 | 代码位置 | 受影响参数 |
|------|---------|-----------|
| `execute_image_to_video` | tool_executor.py:154-174 | `source_image` → LoadImage |
| `execute_generate_image_with_face` | tool_executor.py:103-125 | `face_image` → LoadImage |
| `execute_edit_image` | tool_executor.py:130-149 | `source_image` → LoadImage |
| `execute_upscale_image` | tool_executor.py:179-192 | `source_image` → LoadImage |

**对比正确实现:** `agent.py:146` 的 `animate_image()` 方法先调用 `comfyui_client.upload_image(source_image_bytes)` 上传图片到 ComfyUI 服务器，再用返回的文件名注入工作流。

### 3.3 设计方案: 新增图片上传步骤

**改动文件:** `tool_executor.py`

**改动 1: 新增 `_upload_image_to_comfyui()` 辅助函数**

```python
async def _upload_image_to_comfyui(local_path: str) -> str:
    """读取本地图片文件并上传到 ComfyUI 服务器，返回 ComfyUI 端文件名"""
    local_path = _resolve_media_path(local_path)
    if not local_path or not os.path.exists(local_path):
        raise FileNotFoundError(f"图片文件不存在: {local_path}")
    
    image_bytes = Path(local_path).read_bytes()
    filename = os.path.basename(local_path)
    
    # 上传到 ComfyUI 并获取服务器端文件名
    comfyui_filename = await comfyui_client.upload_image(image_bytes, filename)
    logger.info(f"[ToolExec] 已上传图片到 ComfyUI: {filename} -> {comfyui_filename}")
    return comfyui_filename
```

**改动 2: 修复 4 个受影响的工具函数**

以 `execute_image_to_video` 为例:

```python
async def execute_image_to_video(params: dict) -> dict:
    source_image = _resolve_media_path(params.get("source_image", ""))
    motion_prompt = params.get("motion_prompt", "gentle camera movement, cinematic")

    logger.info(f"[ToolExec] image_to_video source={source_image} motion={motion_prompt[:40]}...")
    try:
        # 关键修复: 先上传图片到 ComfyUI 服务器
        comfyui_filename = await _upload_image_to_comfyui(source_image)
        
        wf = load_workflow("wan_i2v")
        wf = inject_params(
            wf,
            positive_prompt=motion_prompt,
            negative_prompt="色调艳丽，过曝，静态，细节模糊不清，字幕，静止，最差质量",
            seed=random.randint(0, 2**31),
            source_image=comfyui_filename,  # 使用 ComfyUI 端文件名
        )
        video_bytes = await comfyui_client.run_workflow_video(wf)
        url, fpath = _save_bytes(video_bytes, "mp4")
        return {"status": "success", "video_url": url, "video_path": fpath}
    except Exception as e:
        logger.error(f"[ToolExec] image_to_video failed: {e}")
        return {"status": "error", "error": str(e)}
```

同样修复 `execute_generate_image_with_face`、`execute_edit_image`、`execute_upscale_image`。

**原理:** ComfyUI 的 `LoadImage` 节点只能读取 ComfyUI 服务器 `input/` 目录下的文件。通过 `POST /upload/image` API 将本地文件上传到 ComfyUI，返回的文件名（如 `cfeacdb47678.png`）就是 LoadImage 可以识别的值。

**改动 3: 增加 ComfyUI 可用性前置检查**

在每个涉及 ComfyUI 的工具函数开头加:

```python
if not settings.COMFYUI_ENABLED:
    return {"status": "error", "error": "ComfyUI 未启用"}
if not await comfyui_client.check_health():
    return {"status": "error", "error": "ComfyUI 服务不可达，请检查 AutoDL 实例是否开机"}
```

---

## 四、痛点 3: 审批疲劳（P1）

### 4.1 现象

每个 generate_image / write_file / bash / image_to_video 调用都需要用户手动点"批准"。一次含 3 张图的任务，用户至少点击 5-6 次批准。用户明确说"一次性全部执行"但仍然逐个弹窗。

### 4.2 根因

```python
# agent_runner.py:37-40
AUTO_APPROVE_TOOLS = {
    "read_file", "list_dir", "find_files", "grep_search",
    "web_search", "web_fetch",
}
```

只有 6 个只读工具自动执行，其余全部需要确认。没有批量审批机制，也没有用户主动选择"信任模式"的入口。

### 4.3 设计方案: 分级审批 + 会话级信任模式

**原理:** 将工具按风险等级分为三级:
- **L0 无风险** (自动执行): 只读工具（read_file, list_dir, web_search 等）
- **L1 低风险** (创作模式下自动执行): 创作类工具（generate_image, image_to_video, text_to_speech, write_file 限 agent_outputs 目录）
- **L2 高风险** (始终需要确认): 系统命令（bash 写操作）、编辑用户文件（edit_file 非 agent_outputs）

**改动 1: `agent_runner.py` — 三级审批策略**

```python
# L0: 始终自动执行
AUTO_APPROVE_TOOLS: set[str] = {
    "read_file", "list_dir", "find_files", "grep_search",
    "web_search", "web_fetch",
}

# L1: 创作模式下自动执行
CREATIVE_AUTO_APPROVE_TOOLS: set[str] = {
    "generate_image", "generate_image_with_face", "edit_image",
    "image_to_video", "upscale_image", "text_to_speech",
    "merge_media", "add_subtitle",
    "write_file",  # 仅限 agent_outputs 目录
    "python_exec",
}

# L1 中 write_file 的安全路径（限制自动写入范围）
_SAFE_WRITE_DIRS = {"agent_outputs", "uploads"}

def needs_approval(tool_name: str, args: dict, auto_mode: bool = False) -> bool:
    """判断工具是否需要用户审批"""
    if tool_name in AUTO_APPROVE_TOOLS:
        return False
    if auto_mode and tool_name in CREATIVE_AUTO_APPROVE_TOOLS:
        # write_file 额外检查路径安全性
        if tool_name == "write_file":
            path = args.get("path", "")
            return not any(safe in path for safe in _SAFE_WRITE_DIRS)
        # bash 检查是否只读
        if tool_name == "bash":
            cmd = args.get("command", "")
            readonly_prefixes = ("ls ", "pwd", "cat ", "head ", "tail ", "file ", "wc ", "find ", "grep ")
            return not any(cmd.strip().startswith(p) for p in readonly_prefixes)
        return False
    return True
```

**改动 2: WebSocket 协议增加 `auto_mode` 参数**

前端发送消息时附带:
```json
{"message": "帮我生成一张图", "auto_mode": true}
```

后端 `comic_agent.py` 透传给 `agent_stream()`:
```python
async for event in agent_stream(
    user_message=message,
    model_config=model_config,
    db=db,
    conversation_history=history,
    approval_queue=approval_queue,
    auto_mode=auto_mode,  # 新增参数
):
```

**改动 3: 前端增加"自动执行"开关**

在 ComicAgentView.vue 的输入框旁添加 toggle:

```vue
<el-switch v-model="autoMode" active-text="自动执行" />
```

开启后创作类工具无需逐个审批。

**原理:** 分级审批的核心思想是: 创作类工具（生图/转视频/TTS）的"风险"只是消耗 API 额度，不会破坏用户数据。在用户明确选择"自动执行"后，这些工具可以直接运行，大幅减少交互次数。而 bash 写操作、编辑用户非创作文件等真正有破坏性的操作仍然需要确认。

---

## 五、痛点 4: Agent 过度执行（P1）

### 5.1 现象

用户要求"搜索 + 写文件 + 生 1 张图"，Agent 搜了 4 次、写了 2 次、生了 20+ 张图。

### 5.2 根因

System Prompt 的"每次只做用户要求的事"约束力不够。LLM 倾向于"过度服务"。Agent 没有"任务完成检测"机制——完成了用户要求的步骤后不知道该停。

### 5.3 设计方案: Prompt 强化 + 完成检测

**改动: System Prompt 增加执行边界指令**

这与痛点 1 的 `[TASK_DONE]` 机制配合:

```
## 执行边界
1. 分析用户请求，识别明确的步骤列表
2. 逐步执行，每步完成后记录产出
3. 用户说"生成 1 张图"就只生 1 张，不要自作主张多做
4. 所有步骤完成后输出 [TASK_DONE] + 完成汇报
5. 如果用户的请求有歧义（如"生成图片"未指定数量），默认生成 1 张
6. 完成后询问用户是否满意或需要调整，不要自动生成变体
```

**原理:** 通过在 Prompt 中建立"任务边界"概念，让 LLM 明确知道什么时候该停。配合 `[TASK_DONE]` 显式完成信号，形成闭环: 用户下达任务 → Agent 识别步骤 → 逐步执行 → 检查结果 → 全部完成 → 输出 [TASK_DONE] → 循环退出。

---

## 六、痛点 5: 跨轮上下文丢失（P1）

### 6.1 现象

用户发"继续"后，Agent 忘记上一轮生成的图片路径，重新 list_dir 查找。消耗大量迭代在文件发现上。

### 6.2 根因

```python
# agent_runner.py:96-112 _compact_history()
for m in middle:
    if m.get("role") == "tool":
        content = m.get("content", "")
        result.append({
            **m,
            "content": content[:200] + "...(已截断)" if len(content) > 200 else content
        })
```

工具结果被截断到 200 字符。图片路径如 `/uploads/agent_outputs/5beaf4c0c4fc.png` 在截断后可能丢失。

### 6.3 设计方案: 媒体路径永久保留 + 工作记忆注入

**改动 1: `_compact_history()` 对媒体路径特殊处理**

```python
def _compact_history(messages: list[dict]) -> list[dict]:
    if len(messages) <= 8:
        return messages
    result = [messages[0]]
    middle = messages[1:-6]
    recent = messages[-6:]
    for m in middle:
        if m.get("role") == "tool":
            content = m.get("content", "")
            # 提取媒体路径（永远保留）
            media_paths = re.findall(
                r'(?:图片|视频|音频)(?:URL|路径): (\S+)',
                content
            )
            if len(content) > 200:
                truncated = content[:200] + "...(已截断)"
                # 追加媒体路径保证不丢失
                if media_paths:
                    truncated += "\n关键产出: " + ", ".join(media_paths)
                result.append({**m, "content": truncated})
            else:
                result.append(m)
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            result.append({
                "role": "assistant",
                "content": m.get("content", "")[:100] + "...",
                "tool_calls": m["tool_calls"],
            })
        else:
            result.append(m)
    result.extend(recent)
    return result
```

**改动 2: 工作记忆注入**

在 `agent_stream()` 中维护一个 artifacts 列表，每轮开始注入:

```python
# 在 agent_stream 循环体中，工具执行后收集产出
artifacts: list[str] = []

# 每次工具执行后:
if result.get("image_url"):
    artifacts.append(f"图片: {result['image_url']}")
if result.get("video_url"):
    artifacts.append(f"视频: {result['video_url']}")
if result.get("audio_url"):
    artifacts.append(f"音频: {result['audio_url']}")

# 在 messages 末尾追加工作记忆
if artifacts:
    memory_text = "[工作记忆] 当前已生成的资源:\n" + "\n".join(artifacts)
    # 注入为 system 消息（不消耗 user 轮次）
    messages.append({"role": "system", "content": memory_text})
```

**原理:** 工作记忆解决了"短期记忆丢失"问题。即使历史被压缩截断，每轮注入的工作记忆始终包含最新的产出列表。Agent 不需要重新查找文件，直接引用工作记忆中的路径即可。

---

## 七、痛点 6: Thinking 噪音（P2）

### 7.1 现象

Claude 的 thinking/reasoning 内容大段输出到前端:
```
**Generating image prompts** I'm planning to use the commentary channel...
**Executing tool calls** I need to respond using the necessary tools...
```

### 7.2 根因

```python
# agent_runner.py:382-384
if chunk.thinking:
    accumulated_thinking += chunk.thinking
    yield {"type": "thinking", "content": chunk.thinking}
```

所有 thinking 直接透传，无过滤。

### 7.3 设计方案: 后端过滤 + 前端折叠

**改动 1: agent_runner.py — Thinking 过滤**

```python
def _should_yield_thinking(text: str) -> bool:
    """判断 thinking 内容是否值得展示给用户"""
    # 含中文字符 → 可能是有用的分析
    if re.search(r'[\u4e00-\u9fff]', text):
        return True
    # 系统状态信息（🔧🔍🎨等 emoji 开头）
    if text.strip() and text.strip()[0] in '🔧🔍🎨🎬📝🔄💻📁📄':
        return True
    return False

# 在流式循环中:
if chunk.thinking:
    accumulated_thinking += chunk.thinking
    if _should_yield_thinking(chunk.thinking):
        yield {"type": "thinking", "content": chunk.thinking}
    # 英文推理只写日志
    logger.debug(f"[AgentRunner] thinking: {chunk.thinking[:100]}")
```

**原理:** Claude 的 thinking 分两类: (1) 英文内部推理（对用户无价值），(2) 中文分析和状态信息（有价值）。按语言过滤，只保留中文和系统状态。

**改动 2: 前端默认折叠 thinking**

```vue
<!-- 默认 expanded = false -->
<template v-if="msg.type === 'thinking'">
  <div class="thinking-bubble" @click="msg.expanded = !msg.expanded">
    <span>🤔 {{ msg.expanded ? '收起' : '正在思考...' }}</span>
    <div v-show="msg.expanded" class="thinking-content">{{ msg.content }}</div>
  </div>
</template>
```

---

## 八、实施计划

### 阶段 1: 修复 P0（1-2 天）

| 任务 | 文件 | 改动量 | 说明 |
|------|------|--------|------|
| 修复图片上传 BUG | tool_executor.py | 约 30 行 | 新增 _upload_image_to_comfyui + 修复 4 个工具 |
| ComfyUI 前置健康检查 | tool_executor.py | 约 10 行 | 每个 ComfyUI 工具开头加 check |
| Agent 循环改造 | agent_runner.py:410-435 | 约 25 行 | 替换 break 逻辑为显式完成检测 |
| System Prompt 增加执行规范 | agent_runner.py:53-85 | 约 15 行 | 新增执行边界 + [TASK_DONE] 指令 |
| MAX_ITERATIONS 提升 | agent_runner.py:18 | 1 行 | 10 → 15 |

### 阶段 2: 优化体验（1 天）

| 任务 | 文件 | 改动量 | 说明 |
|------|------|--------|------|
| 三级审批策略 | agent_runner.py | 约 30 行 | 新增 CREATIVE_AUTO_APPROVE + needs_approval |
| auto_mode 参数透传 | comic_agent.py | 约 5 行 | WS 消息中解析 auto_mode |
| 前端自动执行开关 | ComicAgentView.vue | 约 10 行 | toggle 组件 + sendRaw 传参 |
| 媒体路径保留 | agent_runner.py:96-112 | 约 10 行 | _compact_history 媒体特殊处理 |
| 工作记忆注入 | agent_runner.py:461-533 | 约 15 行 | artifacts 收集 + 注入 |

### 阶段 3: 精细优化（0.5 天）

| 任务 | 文件 | 改动量 | 说明 |
|------|------|--------|------|
| Thinking 过滤 | agent_runner.py:382-384 | 约 15 行 | 中文判断 + logger |
| 前端 thinking 折叠 | ComicAgentView.vue:262-273 | 约 5 行 | 默认折叠 |

---

## 九、验证方案

### 测试用例 1: 图生视频修复验证

```
用户: "用 agent_outputs 目录下最新的图片生成一个 5 秒短视频"
预期:
1. Agent 调用 image_to_video
2. tool_executor 读取本地文件 → 上传到 ComfyUI → 获得 ComfyUI 文件名 → 注入工作流
3. ComfyUI 正常执行，返回视频 bytes
4. 前端显示视频
```

### 测试用例 2: Agent 自主多步执行

```
用户: "搜索退婚流短剧的流行元素，写入 search_result.md，然后生成 1 张退婚场景仙侠风格图片"
预期:
1. Agent 自动完成: web_search → write_file → generate_image
2. 中间不需要用户点"继续"
3. 每步结果自动检查
4. 最后输出 [TASK_DONE] + 完成汇报
5. 总耗时: 3 个工具 + 3 次结果分析 = 约 6 轮迭代
```

### 测试用例 3: 审批模式

```
用户: 开启"自动执行"后发 "生成 3 张不同风格的图片"
预期:
1. 3 次 generate_image 全部自动执行，无审批弹窗
2. Agent 逐个生成并汇报
```

### 测试用例 4: 上下文保持

```
用户: 第一轮 "生成一张仙侠图片"
用户: 第二轮 "把刚才的图片转成视频"
预期:
1. Agent 直接引用工作记忆中的图片路径
2. 不会重新 list_dir 查找
3. 直接调用 image_to_video
```

---

## 十、关键代码修改对照表

| 文件 | 当前行号 | 修改类型 | 说明 |
|------|---------|---------|------|
| tool_executor.py:47-65 | _resolve_media_path 后 | 新增函数 | _upload_image_to_comfyui() |
| tool_executor.py:103-125 | execute_generate_image_with_face | 修改 | 增加 upload 步骤 |
| tool_executor.py:130-149 | execute_edit_image | 修改 | 增加 upload 步骤 |
| tool_executor.py:154-174 | execute_image_to_video | 修改 | 增加 upload 步骤 |
| tool_executor.py:179-192 | execute_upscale_image | 修改 | 增加 upload 步骤 |
| agent_runner.py:18 | MAX_ITERATIONS | 修改 | 10 → 15 |
| agent_runner.py:37-40 | AUTO_APPROVE_TOOLS | 新增 | CREATIVE_AUTO_APPROVE_TOOLS |
| agent_runner.py:53-85 | DEFAULT_SYSTEM_PROMPT | 追加 | 执行规范 + [TASK_DONE] |
| agent_runner.py:96-112 | _compact_history | 修改 | 媒体路径保留 |
| agent_runner.py:286-292 | agent_stream 签名 | 新增参数 | auto_mode: bool |
| agent_runner.py:410-435 | 无工具调用分支 | 重写 | 显式完成检测 + 自动续行 |
| agent_runner.py:382-384 | thinking 透传 | 修改 | 中文过滤 |
| agent_runner.py:461-533 | 工具执行循环 | 新增 | artifacts 收集 |
| comic_agent.py:762-815 | WS handler | 修改 | auto_mode 透传 |
| ComicAgentView.vue:297-327 | 审批区域 | 新增 | 自动执行 toggle |
