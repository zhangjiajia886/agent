# Agent 第六期优化 (num1) 实施计划

> 基于: agent自动化测试分析与改进建议.md（20 用例自动化测试，通过率 70%）  
> 目标: 通过率 70% → 90%+，平均耗时 48s → 30s  
> 涉及文件: `openai_client.py` / `agent_runner.py` / `test_agent_auto.py`

---

## 评估结论

分析文档识别了 5 个问题（P1-P5），方案整体可行，但需要以下调整：

| 原方案 | 评估 | 调整 |
|--------|------|------|
| A: tool_choice 兼容 | ✅ 核心修复，必须做 | 增加日志诊断 + 双格式探测 |
| B: 意图边界强化 | ✅ 低成本高收益 | 调整措辞，放在 Prompt 最前面（最高优先级位置） |
| C: 工具优先级 | ✅ 可行 | 合并到 System Prompt 修改中一并完成 |
| D: 通用工具调用限制 | ✅ 可行 | 数值微调（read_file 5→6，bash 6→8） |
| E: 续行韧性增强 | ⚠️ 需改设计 | 不仅用 ReAct XML fallback，还要在 prompt 中嵌入具体工具名 |

**新增**: 方案 F —— 测试框架增强（更多日志、案例、评测维度）

---

## 实施步骤

### 步骤 1: openai_client.py — tool_choice 兼容性修复 + 日志增强

**文件**: `backend/app/core/comic_chat_agent/openai_client.py`

**修改点 1.1**: `chat_stream_with_tools` 方法中 tool_choice 处理（约 line 170-176）

```python
# 修改前
if tools and not skip_tools:
    payload["tools"] = tools
    payload["tool_choice"] = tool_choice or "auto"

# 修改后
if tools and not skip_tools:
    payload["tools"] = tools
    # Claude 通过 OpenAI 兼容代理时，"required" 可能需要转为 {"type": "any"}
    effective_choice = tool_choice or "auto"
    if effective_choice == "required":
        # 尝试 OpenAI 原生格式 "required"
        # 某些代理（如 AIPRO）可能需要 {"type": "any"} 格式
        payload["tool_choice"] = "required"
    else:
        payload["tool_choice"] = effective_choice
    logger.info(
        f"[OpenAI-Stream] tool_choice={payload['tool_choice']} "
        f"(requested={tool_choice})"
    )
```

**修改点 1.2**: 增加响应中 tool_calls 的诊断日志

在流式响应解析完成处（is_done chunk yield 前），增加：
```python
logger.info(
    f"[OpenAI-Stream] done: tool_calls={len(final_tool_calls or [])} "
    f"text_len={len(accumulated_text)} "
    f"tool_choice_was={payload.get('tool_choice', 'N/A')}"
)
```

---

### 步骤 2: agent_runner.py — System Prompt 重写

**文件**: `backend/app/core/comic_chat_agent/agent_runner.py`

**修改 DEFAULT_SYSTEM_PROMPT**，核心变更：

1. **在最前面新增"意图判定"节**（最高优先级位置）：
```
## 意图判定（最高优先级）
- 用户在打招呼、问你是谁、闲聊、问问题 → 直接文字回复，**禁止调用任何工具**
- 用户要求搜索/生成/编辑/读写/执行 → 立即调工具，不要先输出计划
- 不确定时 → 先询问用户意图
```

2. **在"执行策略"节后新增"工具选择优先级"**：
```
## 工具选择优先级
有专用工具时必须优先使用，禁止用 bash 替代：
- 读文件 → read_file（禁止 bash cat）
- 写文件 → write_file（禁止 bash echo >）
- 搜索文件内容 → grep_search（禁止 bash grep）
- 查找文件 → find_files（禁止 bash find）
- HTTP 请求 → http_request（禁止 bash curl）
bash 仅用于: 系统命令、管道操作、或确实没有专用工具的场景
```

3. **调整"执行策略"措辞**，避免与意图判定冲突：
```
## 执行策略（仅当判定为需要工具的任务时）
收到需要工具的任务后：
1. 直接调用第一个工具（不要先输出文字计划）
2. 每个工具返回后，立即调用下一个工具
3. 所有步骤完成后输出 [TASK_DONE] 并汇报
```

---

### 步骤 3: agent_runner.py — 通用工具调用次数限制

**修改 MAX_TOOL_CALLS_PER_TOOL**：

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
    # 通用工具
    "read_file": 6,
    "write_file": 5,
    "edit_file": 4,
    "bash": 8,
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

### 步骤 4: agent_runner.py — 续行机制韧性增强

**修改 `agent_stream` 中 has_plan 分支**（约 line 526-537）：

```python
elif has_plan and iteration < MAX_ITERATIONS - 1:
    if no_tool_streak >= 2:
        # tool_choice=required 已尝试但无效
        # 降级: 用 ReAct XML 提示 + 不设 force（依赖 XML 降级解析）
        logger.warning(
            f"[AgentRunner] force 无效 (streak={no_tool_streak})，"
            f"切换 ReAct XML 降级 (iter={iteration})"
        )
        messages.append({
            "role": "user",
            "content": (
                "[系统提示] 你之前只输出了文字计划，没有实际调用工具。\n"
                "请立即用以下格式调用工具:\n"
                '<tool_call>{"name": "工具名", "arguments": {...}}</tool_call>\n'
                "直接行动，不要再解释。"
            ),
        })
        # 不设 force_tool_choice，让 ReAct XML 降级解析兜底
        yield {"type": "thinking", "content": "🔄 tool_choice 无效，切换 ReAct XML 降级..."}
    else:
        logger.info(f"[AgentRunner] 检测到计划未执行，强制 tool_choice=required (iter={iteration})")
        messages.append({
            "role": "user",
            "content": (
                "[系统提示] 你列出了计划但没有调用工具。"
                "请立即执行下一步，直接调用工具。"
            ),
        })
        force_tool_choice = "required"
        yield {"type": "thinking", "content": "🔄 检测到计划未执行，强制 Agent 调用工具..."}
    continue
```

---

### 步骤 5: agent_runner.py — 日志增强

在关键决策点增加诊断日志：

**5.1** 循环退出时记录完整上下文：
```python
# 自然结束处
logger.info(
    f"[AgentRunner] 自然结束 after {iteration + 1} iters | "
    f"no_tool_streak={no_tool_streak} tools_executed={tools_executed} "
    f"has_plan={has_plan} is_mid_task={is_mid_task} task_done={task_done}"
)
```

**5.2** 每轮 LLM 调用后记录 tool_calls 数量：
```python
logger.info(
    f"[AgentRunner] iter={iteration} tool_calls={len(final_tool_calls or [])} "
    f"text_len={len(accumulated_text)} force={current_tool_choice}"
)
```

---

### 步骤 6: test_agent_auto.py — 测试框架全面增强

**6.1 新增评测维度**

当前仅有: 工具选择正确性、关键词匹配、异常处理、系统错误  
新增:
- **效率评分**: 工具调用次数 / 预期最少次数（越接近 1.0 越好）
- **耗时评分**: 实际耗时 / 30s 基准（<1.0 为优秀）
- **工具精准率**: 调用的工具中，预期工具的占比
- **bash 替代率**: bash 调用次数 / 总工具调用次数（越低越好）
- **续行触发次数**: 统计 thinking 事件中"强制"/"续行"关键词出现次数

**6.2 新增日志**

- 每个测试用例的完整事件序列写入 JSON（已有）
- 新增: 按事件类型统计（tool_start/tool_done/tool_confirm/thinking/delta/done 各多少个）
- 新增: 每个 thinking 事件内容输出到日志
- 新增: 工具执行结果摘要（成功/失败/被拒绝）
- 新增: 首次工具调用延迟（从发送消息到第一个 tool_start 的时间）

**6.3 新增测试用例（10 个，编号 32-41）**

| 编号 | 名称 | 目标 |
|------|------|------|
| 32 | 中文问答（不调工具） | 验证意图判定：纯问答不调工具 |
| 33 | 英文指令 | 验证非中文指令也能正确调工具 |
| 34 | 同时读两个文件 | 验证并行/顺序工具调用 |
| 35 | python_exec 写文件+读 | 验证不用 bash 替代（工具优先级） |
| 36 | web_search 限制验证 | 验证调用次数限制生效 |
| 37 | write_file 到 /tmp 路径 | 验证 auto_mode 下非安全路径处理 |
| 38 | 连续两个独立任务 | 验证 TASK_DONE 后能接新任务 |
| 39 | 超长用户消息 | 验证 token 管理和压实 |
| 40 | 工具执行失败后重试 | 验证错误处理+最多重试1次 |
| 41 | 三步链式（必须全完成） | 验证续行机制修复后能否完成 |

**6.4 报告增强**

- 新增"效率评分"列
- 新增"优化前 vs 优化后"对比表（读取上一次报告数据）
- 新增"工具调用热力图"（哪些工具被调用最多）
- 新增"耗时分布图"（text 描述）

---

## 执行顺序

```
1. 修改 openai_client.py (步骤1)        ← 5 min
2. 修改 agent_runner.py (步骤2+3+4+5)   ← 15 min
3. 重启后端                              ← 1 min
4. 增强 test_agent_auto.py (步骤6)       ← 15 min
5. 运行测试                              ← ~20 min
6. 分析结果，生成对比报告                  ← 5 min
```

## 预期结果

| 指标 | 优化前 | 目标 |
|------|--------|------|
| 通过率 | 70% (14/20) | 90%+ (27/30，含新增10例) |
| 平均耗时 | 48.2s | < 35s |
| "光说不做"失败 | 3 例 | 0 例 |
| 过度调用（>10次） | 2 例 | 0 例 |
| bash 替代率 | ~30% | < 10% |

## 回滚方案

所有修改仅涉及 3 个文件，均可通过 git 回滚：
```bash
git checkout -- backend/app/core/comic_chat_agent/openai_client.py
git checkout -- backend/app/core/comic_chat_agent/agent_runner.py
```
测试脚本为独立文件，不影响生产代码。
