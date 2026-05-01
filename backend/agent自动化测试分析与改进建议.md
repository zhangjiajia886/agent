# Agent 自动化测试分析与改进建议

> 基于 20 个自动化测试用例（编号 12-31），模型: claude-sonnet-4-6  
> 测试时间: 2026-04-29 17:56  
> 测试方式: WebSocket + auto_mode=True，全自动执行无人工审核

---

## 一、测试总览

| 指标 | 数值 |
|------|------|
| ✅ 通过 | 14/20 (70%) |
| ❌ 失败 | 6/20 (30%) |
| 💥 系统错误 | 0 |
| ⏰ 超时 | 0 |
| 总耗时 | 963.3s（平均 48.2s/用例）|

### 通过的 14 个用例

| 用例 | 类型 | 耗时 | 工具调用 |
|------|------|------|---------|
| 13 list_dir | 单工具-L0 | 16.9s | list_dir ×1 |
| 14 read_file | 单工具-L0 | 154.4s ⚠️ | read_file ×13, bash ×2 |
| 15 web_search | 单工具-L0 | 306.5s ⚠️ | web_search ×6, web_fetch ×3 |
| 16 python_exec | 单工具-L1 | 26.2s | python_exec ×2 |
| 17 write+read | 双工具链 | 25.4s | write_file ×2, read_file ×1 |
| 18 grep_search | 单工具-L0 | 22.6s | grep_search ×1 |
| 19 find_files | 单工具-L0 | 42.0s | find_files ×1, bash ×2 |
| 20 bash | 单工具-L2 | 29.5s | bash ×4 |
| 21 edit_file | 双工具链 | 39.1s | write_file ×2, edit_file ×2 |
| 22 http_request | 单工具-L2 | 39.3s | http_request ×2, bash ×2 |
| 25 读不存在文件 | 异常处理 | 17.9s | read_file ×1 |
| 26 编辑不存在内容 | 异常处理 | 26.5s | write_file ×2, edit_file ×2 |
| 27 模糊意图 | 纯聊天 | 12.5s | (无) |
| 29 bash 管道 | 单工具-L2 | 24.3s | bash ×2 |

### 失败的 6 个用例

| 用例 | 失败类型 | 预期工具 | 实际工具 |
|------|---------|---------|---------|
| 12 纯聊天 | 意图误判 | (无) | list_dir ×1 |
| 23 三工具链式 | 光说不做 | web_search→write_file→read_file | (无) |
| 24 python_exec | 光说不做 | python_exec | (无) |
| 28 python+write | 光说不做 | python_exec→write_file | (无) |
| 30 三步依赖传递 | 工具替代 | python_exec→write_file→read_file | python_exec→bash→bash |
| 31 双工具准确性 | 多步中断 | list_dir→grep_search | list_dir ×1 |

---

## 二、问题根因分析

### 问题 P1: "光说不做" —— 输出计划但不调工具 🔴 最严重

**涉及用例**: 23、24、28（3/20 = 15% 失败率）

**现象**:
- Agent 输出文字计划（"按你的要求分 3 步执行：1) ... 2) ... 3) ... 先进行第 1 步"）
- 事件序列: `thinking → delta×N → thinking → done`，**无任何 tool_start/tool_done 事件**
- `has_plan` 检测确实触发了，注入了 `[系统提示] 你列出了计划但没有调用工具` 并设置 `force_tool_choice="required"`
- 第二轮 LLM 调用后**仍然没有返回 tool_calls**，最终自然退出

**根因定位**:

```
agent_runner.py:448-460 → openai_client.py:170-172
```

`tool_choice="required"` 通过 `openai_client.py` 传递到 API payload：
```python
payload["tool_choice"] = tool_choice or "auto"  # line 172
```

但 API 代理 `vip.aipro.love/v1` 将请求转发给 Claude 时，**可能未正确翻译 `tool_choice: "required"` 为 Claude 原生的 `tool_choice: {"type": "any"}`**。

OpenAI 格式: `"tool_choice": "required"` → 强制调工具  
Claude 原生格式: `"tool_choice": {"type": "any"}` → 强制调工具  

如果代理层忽略了 `tool_choice` 参数，Claude 会按 `auto` 行为，在认为"先说计划再行动"更合理时选择不调工具。

**验证方式**: 查看后端日志中第二轮 LLM 的 HTTP 请求和响应，确认 `tool_choice` 是否被代理正确处理。

**影响范围**: 所有需要续执行机制触发 `force_tool_choice=required` 的场景。

---

### 问题 P2: 意图边界模糊 —— 纯聊天时多余调工具 🟡

**涉及用例**: 12

**现象**:
- 用户发送"你好，请简单介绍一下你自己？"（明显的纯聊天）
- Agent 正确介绍了自己（内容含"漫剧 Agent"等关键词 ✅）
- 但**额外调用了 `list_dir`** 来"确认当前工作环境"

**根因**:

System Prompt 中存在矛盾指令：
```
行 91: "2. **立即行动**: 拆解后直接调用第一个工具，不要只输出文字计划"
行 128: "如果用户只是聊天、问问题，直接友好回复，不要调用工具"
```

"立即行动"的权重高于"纯聊天不调工具"，导致 LLM 在纯聊天场景也试图调用工具。且 `list_dir` 属于 L0 自动执行工具，没有确认卡拦截。

---

### 问题 P3: 工具替代 —— bash 万能替代专用工具 🟡

**涉及用例**: 30

**现象**:
- 预期使用 `write_file` 写入文件，实际使用 `bash` 执行 `echo ... > /tmp/file`
- 预期使用 `read_file` 读取文件，实际使用 `bash` 执行 `cat /tmp/file`
- 功能等价，结果正确，但不符合工具选择预期

**根因**:

1. `bash` 是"瑞士军刀"工具，LLM 倾向于用一个工具完成多步操作（一次 bash 可以同时写+读）
2. System Prompt 未明确工具优先级（"有专用工具时优先用专用工具，bash 仅作为兜底"）
3. 该问题也出现在通过的用例中（用例14用bash辅助read_file，用例19用bash辅助find_files，用例22用bash辅助http_request）

---

### 问题 P4: 多步中断 —— 链式任务只完成第一步 🟡

**涉及用例**: 31

**现象**:
- 用户要求两步：list_dir → grep_search
- Agent 正确执行了 list_dir（第一步）
- 输出文字说"接着执行第 2 步：递归搜索包含 `import asyncio` 的文件"
- 但**实际没有调用 grep_search**，经过 2-3 轮空转后自然退出

**根因**:

`agent_runner.py:506-552` 的续行逻辑流程：

```
iter=0: list_dir 执行成功 → tools_executed=True
iter=1: 纯文字（"接着执行第2步..."）→ no_tool_streak=1
        has_plan=True → force_tool_choice=required → continue
iter=2: 再次纯文字 → no_tool_streak=2
        has_plan 可能为 False（第二次回复文字不同）
        is_mid_task=True → force_tool_choice=required → continue
iter=3: 再次纯文字 → no_tool_streak=3 → 强制退出
```

核心问题仍然是 **`tool_choice=required` 不生效**（同 P1），导致续行机制虽然触发但无法迫使模型调用工具。

---

### 问题 P5: 过度调用 —— L0 工具无节制调用 🟠

**涉及用例**: 14（通过但低效）、15（通过但低效）

| 用例 | 工具调用次数 | 耗时 | 合理次数 |
|------|------------|------|---------|
| 14 read_file | 15 次 | 154.4s | 1-2 次 |
| 15 web_search | 10 次 | 306.5s | 1-3 次 |

**根因**:
- L0 工具（read_file、web_search 等）完全自动执行，无确认卡拦截
- `MAX_TOOL_CALLS_PER_TOOL` 仅限制了 8 个漫剧工具，**通用工具没有调用次数限制**
- 用例14: 可能 README.md 较大，Agent 反复用不同方式（offset/bash）读取
- 用例15: 搜索 query 模糊，Agent 反复搜索 + 抓取多个网页
- 即使最终"通过"了测试，但效率极低（read_file 用了 154s，web_search 用了 306s）

---

## 三、问题关联的通过用例隐患

除了 6 个失败用例，通过的用例中也暴露了隐患：

| 用例 | 现象 | 隐患 |
|------|------|------|
| 14 read_file | 调了 15 次工具 | 过度调用，浪费 token + 时间 |
| 15 web_search | 调了 10 次工具 | 过度调用，浪费 token + 时间 |
| 16 python_exec | 调了 2 次（应该 1 次就够） | 轻微冗余 |
| 17 write+read | write_file 调了 2 次 | 第一次可能失败或参数不对 |
| 19 find_files | 额外用了 bash ×2 | bash 替代 |
| 20 bash | 调了 4 次（应该 1-2 次） | 拆分过细 |
| 21 edit_file | write_file ×2, edit_file ×2 | 重复调用 |
| 22 http_request | 额外用了 bash ×2 | bash 替代 |

**总结**: 即使是通过的用例，也普遍存在**工具调用次数偏多、bash 替代专用工具**的问题。

---

## 四、改进方案

### 方案 A: tool_choice 兼容性修复（解决 P1 + P4）🔴 优先级最高

**目标**: 确保 `tool_choice=required` 在 Claude 模型上生效

**修改文件**: `openai_client.py`

**方案**:
1. 检测模型是否为 Claude（模型名包含 "claude"）
2. 将 `"required"` 转换为 Claude 原生格式 `{"type": "any"}`
3. 添加日志记录实际发送的 `tool_choice` 值
4. 如果 API 代理不支持任何 tool_choice 强制，**agent_runner.py 需要备选方案**：在 system message 中注入更强制的指令，如 "你必须在本次回复中调用至少一个工具，不允许只输出文字"

```python
# openai_client.py 修改
if tool_choice == "required" and "claude" in self.model.lower():
    payload["tool_choice"] = {"type": "any"}
else:
    payload["tool_choice"] = tool_choice or "auto"
```

**备选强化**: 如果 tool_choice 仍无效，在 agent_runner.py 的 force 分支中增加更强的 system prompt 注入：
```python
# agent_runner.py 修改
messages.append({
    "role": "user",
    "content": (
        "[系统提示] 你列出了计划但没有调用工具。"
        "你必须在本次回复中直接调用工具。"
        "不要输出任何文字说明，直接返回 tool_call。"
        "这是强制要求。"
    ),
})
```

---

### 方案 B: System Prompt 意图边界强化（解决 P2）

**修改文件**: `agent_runner.py` DEFAULT_SYSTEM_PROMPT

**修改内容**:

在"## 重要"节增加更明确的判定规则：
```
## 意图判定（最高优先级）
- **纯聊天/问答**: 用户在打招呼、问你是谁、闲聊 → 直接文字回复，禁止调用任何工具
- **需要工具的任务**: 用户要求搜索/生成/编辑/读写 → 立即调工具
- 判定标准: 用户消息是否包含动作意图（"生成"、"搜索"、"读取"、"写入"、"编辑"等）
- 不确定时 → 先询问用户意图，不要主动探索环境
```

---

### 方案 C: 工具优先级与 bash 限制（解决 P3）

**修改文件**: `agent_runner.py` DEFAULT_SYSTEM_PROMPT

**修改内容**:

在"## 执行规范"节增加：
```
## 工具选择优先级
- 有专用工具时，优先使用专用工具，不要用 bash 替代
  - 读文件 → read_file（不要用 bash cat）
  - 写文件 → write_file（不要用 bash echo >）
  - 搜索文件 → find_files / grep_search（不要用 bash find/grep）
  - HTTP 请求 → http_request（不要用 bash curl）
- bash 仅用于: 系统命令、管道操作、无专用工具的操作
```

---

### 方案 D: 通用工具调用次数限制（解决 P5）

**修改文件**: `agent_runner.py` MAX_TOOL_CALLS_PER_TOOL

**修改内容**:

```python
MAX_TOOL_CALLS_PER_TOOL: dict[str, int] = {
    # 漫剧工具
    "generate_image": 8,
    "generate_image_with_face": 6,
    "edit_image": 4,
    "image_to_video": 3,
    "upscale_image": 4,
    "text_to_speech": 6,
    "merge_media": 2,
    "add_subtitle": 2,
    # 通用工具 —— 新增限制
    "read_file": 5,
    "write_file": 5,
    "edit_file": 4,
    "bash": 6,
    "python_exec": 5,
    "web_search": 4,
    "web_fetch": 4,
    "grep_search": 4,
    "find_files": 4,
    "list_dir": 4,
    "http_request": 4,
}
```

---

### 方案 E: 续行机制韧性增强（解决 P1/P4 的 fallback）

**修改文件**: `agent_runner.py`

当 `force_tool_choice=required` 连续失败 2 次后（no_tool_streak >= 2 且 has_plan），切换策略：
1. 移除 `force_tool_choice`，改为注入更详细的 system prompt 指令
2. 显式列出下一个应调用的工具名
3. 如果仍然失败（no_tool_streak >= 3），承认限制，生成最终摘要

```python
# 续行强化逻辑
elif has_plan and iteration < MAX_ITERATIONS - 1:
    if no_tool_streak >= 2:
        # force 已尝试过但无效，改用 prompt 引导
        messages.append({
            "role": "user",
            "content": (
                "[系统提示] tool_choice 强制无效，请你必须在回复中包含"
                " <tool_call>{...}</tool_call> 格式的工具调用。"
                "直接行动，不要解释。"
            ),
        })
        # 不设 force_tool_choice，依赖 ReAct XML 降级解析
    else:
        force_tool_choice = "required"
        messages.append({...})
    continue
```

---

## 五、改进优先级排序

| 优先级 | 方案 | 解决问题 | 预期收益 | 工作量 |
|--------|------|---------|---------|--------|
| 🔴 P0 | A: tool_choice 兼容 | P1+P4 光说不做 + 多步中断 | +15% 通过率 (3个用例) | 小 |
| 🟡 P1 | D: 通用工具调用限制 | P5 过度调用 | 性能提升 50%+ | 小 |
| 🟡 P1 | B: 意图边界强化 | P2 纯聊天调工具 | +5% 通过率 | 小 |
| 🟡 P1 | C: 工具优先级 | P3 bash 替代 | +5% 通过率 + 规范化 | 小 |
| 🟠 P2 | E: 续行韧性增强 | P1/P4 fallback | 鲁棒性 | 中 |

**执行顺序**: A → D → B → C → E

---

## 六、预期优化后结果

| 指标 | 当前 | 优化后（预估） |
|------|------|--------------|
| 通过率 | 70% (14/20) | 90%+ (18/20) |
| 平均耗时 | 48.2s | ~30s |
| 过度调用 | 2 个用例 | 0 |
| 光说不做 | 3 个用例 | 0-1 |
| bash 替代 | 普遍 | 偶发 |

优化后仍可能失败的场景：
- 用例30（多步依赖传递）：即使限制 bash，LLM 也可能选择其他替代方式
- API 代理的 tool_choice 兼容性如果完全不支持，需要依赖方案 E 的 fallback
