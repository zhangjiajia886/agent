# 当前漫剧 Agent 面临的问题与优化方案

> 基于 测试案例1.md 深度分析 - 2026-04-29

---

## 一、测试案例复盘

### 任务描述
用户要求: 先用 web_search 搜索"退婚流短剧"的流行元素，然后把搜索结果要点写入 search_result.md，最后根据要点生成一张退婚场景的仙侠风格图片。

### 实际表现（时间线）
| 时间 | 用户操作 | Agent 状态 | 问题 |
|------|---------|-----------|------|
| 14:30 | 发送任务 | 完成搜索+写文件+生图（第1轮） | 核心任务完成 |
| 14:30-14:34 | 无 | Agent 自行多做4次 web_search + 重写文件 + 重复生图 | 过度执行 |
| 14:34 | "继续" | Agent 生成3张变体版 | 每张都要点"批准" |
| 14:36 | "继续" | 又生成3张竖版精修 | 又要3次批准 |
| 14:39 | "继续" | Agent 重新 find_files/list_dir/ls 验证文件 | 重复劳动 |
| 14:42 | "继续" | 又生成2张终版 | 又要2次批准 |
| 14:44 | "一次性全部执行" | 又生成2张底图 | 还是逐个批准 |
| 14:47 | "直接生成短视频" | Agent 开始 list_dir 找文件 | 不直接用刚生成的图 |
| 14:48-14:49 | "继续" x3 | 反复 list_dir/bash ls/验证文件 | 死循环找文件 |
| 14:51 | "视频生成了吗" | Agent 又 list_dir | 无结果反馈 |
| 14:52-14:55 | "继续" x2 | image_to_video 调了2次但无结果 | 视频未生成 |

### 核心数据
- 用户手动操作"继续/批准": 至少 20+ 次
- Agent 总迭代轮次: 跨6轮对话，每轮10次迭代 约 60 轮 LLM 调用
- 有效工具调用: web_search(4) + write_file(2) + generate_image(约12) + image_to_video(2) = 约20次
- 浪费的工具调用: list_dir(5) + bash ls(4) + find_files(2) + python_exec(1) = 约12次
- image_to_video 成功率: 0/2 = 0%
- 生成图片数: 20+张（用户只需要1张）

---

## 二、问题分析（按严重程度排序）

### P0-致命: Agent 不能自主完成多步任务

**问题描述:** Agent 在执行完一个工具后，经常输出"思考文字"但不调用下一个工具，导致前端显示"工具执行完毕，分析结果中..."后卡住，用户必须手动发"继续"才能推进。

**根因 - agent_runner.py:411-435 "无工具调用"分支逻辑:**

当 LLM 返回文本但不包含 tool_call 时:
1. 检测文本是否包含"计划模式"关键词（"第X步"/"步骤X"等）
2. 如果有 -> 注入系统提示 + 强制 tool_choice=required，继续下一轮
3. 如果没有 -> 直接 break，结束整个 agent 循环

致命缺陷: LLM 在工具执行后常输出分析性文字（如"已完成搜索，接下来..."），这些文字不匹配"计划模式"正则，导致 agent_runner 误判为"任务完成"直接退出循环。

**核心矛盾:** Agent 的 ReAct 循环是"单消息驱动"的 -- 一条用户消息触发一次 agent_stream() 调用，最多 10 轮迭代。当 10 轮用完但任务未完成时，Agent 被迫停止。这本质上把"自主 Agent"退化成了"半自动助手"。

**优化方案:**
1. 改进"任务完成检测" -- 不能仅靠计划正则，需要 LLM 显式输出完成信号
2. 增加"任务未完成自动续行" -- 如果 Agent 输出了中间结果但还有待办步骤，自动注入续行提示
3. 在 System Prompt 中加入明确指令: "每次工具返回结果后，你必须检查结果并决定下一步，不要停下来等待用户"

---

### P0-致命: image_to_video 完全失效

**问题描述:** 用户明确要求生成短视频，Agent 调用 image_to_video 至少 2 次，前端始终没有显示视频结果。

**根因分析（多个可能原因叠加）:**

原因1 - ComfyUI 连接/工作流问题:
- tool_executor.py:161-169 调用 load_workflow("wan_i2v")
- wan_i2v 工作流可能不存在或未正确配置
- ComfyUI 可能未启动或不可达
- run_workflow_video() 可能超时但错误被吞掉

原因2 - 结果未正确传递:
- agent_runner.py:520-527 的 yield 中 video_url 可能为 None
- 如果 ComfyUI 返回 error，前端只能看到 JSON 文本，不友好

原因3 - Agent 没有检查工具结果:
- Agent 调用 image_to_video 后，下一轮没有分析返回结果（成功/失败）
- 直接进入 thinking 阶段，浪费迭代
- 用户问"视频生成了吗"才暴露问题

**优化方案:**
1. tool_executor.py 的 image_to_video 增加详细错误日志和超时处理
2. 工具执行后，agent_runner 应自动验证结果状态（成功/失败/超时）
3. 失败时自动重试或给出明确错误信息，不要让用户猜
4. 增加 ComfyUI 连接状态检查，在调用前先验证服务可用性

---

### P1-严重: 审批疲劳（Approval Fatigue）

**问题描述:** 每个非只读工具都需要用户手动点"批准"。一次简单任务中，用户点击了 20+ 次批准按钮。

**当前审批策略 (agent_runner.py:36-40):**
- 自动执行: read_file, list_dir, find_files, grep_search, web_search, web_fetch
- 需要批准: generate_image, write_file, bash, image_to_video, 等等

**问题:** 
- generate_image 需要批准 -> 生成3张图需点3次
- write_file 需要批准 -> 写一个文件要点1次
- bash 需要批准 -> 即使只是 pwd/ls 也要点
- 用户明确说"一次性全部执行"（line 453），Agent 仍然逐个请求批准

**优化方案:**
1. 新增"批量审批"模式 -- 用户点"全部批准"后，本轮所有工具自动执行
2. 新增"会话级自动审批" -- 用户可以在会话开始时选择信任模式
3. 扩大自动审批工具集 -- generate_image/write_file 等创作类工具改为默认自动执行
4. bash 根据命令内容智能判断: 只读命令(ls/pwd/cat/file) 自动执行

---

### P1-严重: Agent 过度执行 + 迭代浪费

**问题描述:** 用户只要求"搜索+写文件+生1张图"，但 Agent 搜了4次、写了2次文件、生成了20+张图。

**根因:**
1. System Prompt "每次只做用户要求的事"约束力不够
2. LLM 倾向于"过度服务"（多搜几次更全面、多生成几张供选择）
3. 缺乏"任务完成检测" -- Agent 不知道何时该停

**优化方案:**
1. System Prompt 强化: "严格按用户要求的数量执行。用户说生成1张图就只生成1张。完成后询问用户是否需要更多，而不是自动多做。"
2. 增加任务边界检测: Agent 完成了用户明确列出的所有步骤后，必须停止并汇报结果
3. 在每轮迭代开始时回顾: "用户要求了X步，已完成Y步，还剩Z步"

---

### P1-严重: 跨轮上下文丢失

**问题描述:** 当用户发"继续"时，Agent 经常忘记上一轮生成的文件路径，重新 list_dir 查找。

**根因:**
1. agent_runner.py:96-112 的 _compact_history() 会截断工具结果到200字
2. 图片路径在压缩后可能丢失
3. 对话历史中的 tool_calls/tool_result 信息没有被完整保留

**测试案例证据:**
- line 317: "我这边没有检索到历史图片文件"
- line 339: 重新 find_files 搜索 agent_outputs
- line 549: "先在当前环境定位最新封面图"（第N次了）

**优化方案:**
1. _compact_tool_result() 对媒体类结果（image_url/video_url）永远保留完整路径
2. 新增"工作记忆" -- 维护一个上下文摘要（已生成的文件列表），每轮自动注入
3. 在消息历史中保留最近 N 条工具结果的关键字段不被截断

---

### P2-中等: Thinking 输出噪音

**问题描述:** LLM 的 thinking/reasoning 内容大量输出到前端，包括英文思考:
- "Generating image prompts - I'm planning to use..."
- "Considering tool calls - I need to ensure that..."
- "Executing tool calls - I need to respond using..."

**根因:** agent_runner.py:382-384 所有 thinking 直接透传给前端。

**优化方案:**
1. 后端过滤: thinking 内容不 yield 给前端（只用于调试日志）
2. 或者前端默认折叠 thinking，只显示 "正在思考..."

---

### P2-中等: 错误处理不透明

**问题描述:**
- image_to_video 失败后，用户看不到具体错误
- Agent 自己"编造"错误原因（说文件无效，实际验证全部 OK）
- 前端对 error 状态没有醒目展示

**优化方案:**
1. tool_executor 返回标准化错误格式: {status: "error", error: "具体原因", suggestion: "建议操作"}
2. agent_runner 对错误结果自动注入修复提示
3. 前端对 tool_done 的 error 状态用红色卡片展示

---

## 三、优化方案总览

### 第一优先级（解决"卡顿"和"不能自主执行"）

#### 3.1 改造 Agent 循环: 任务完成检测 + 自动续行

核心改动文件: agent_runner.py

改动要点:
1. "无工具调用"时不再简单 break，而是检测任务是否真正完成
2. 增加续行机制: 如果当前轮输出了中间结果但还有未完成步骤，自动注入续行提示
3. 把 MAX_ITERATIONS 从 10 提升到 15-20（或动态调整）
4. 在最终轮强制要求 LLM 输出结构化完成报告

具体方案:
```
# 替代当前 line 411-435 的逻辑
if not final_tool_calls:
    # 1. 检测是否输出了"任务完成"信号
    task_done = bool(re.search(r'(已完成|全部完成|任务完成|以上就是|希望满意)', text))
    
    # 2. 检测是否有未执行的计划
    has_plan = bool(re.search(r'(第[1-9]步|步骤\s*[1-9]|先.*然后|接下来)', text))
    
    # 3. 检测是否在分析工具结果（中间状态）
    is_analyzing = bool(re.search(r'(已.*完成|成功|失败|报错|结果)', text)) and iteration < MAX_ITERATIONS - 2
    
    if task_done and not has_plan:
        break  # 真正完成
    elif has_plan or is_analyzing:
        # 自动续行
        messages.append({"role": "user", "content": "[系统] 请继续执行下一步"})
        force_tool_choice = "required" if has_plan else None
        continue
    else:
        break
```

#### 3.2 改造审批模式: 批量审批 + 智能自动审批

核心改动文件: agent_runner.py, comic_agent.py (WS handler), 前端 ComicAgentView.vue

改动要点:
1. 新增"自动执行模式"开关（前端 toggle，后端参数透传）
2. 扩大 AUTO_APPROVE_TOOLS 集合:
   - generate_image -> 自动（创作类，无破坏性）
   - write_file -> 限定在 agent_outputs 目录下时自动
   - image_to_video -> 自动
   - bash -> 只读命令自动，写命令需要确认
3. 前端增加"全部批准"快捷按钮

#### 3.3 修复 image_to_video

核心改动文件: tool_executor.py, comfyui_client.py

改动要点:
1. image_to_video 调用前先检查 ComfyUI 连接状态
2. 增加详细超时处理和错误日志
3. 失败时返回明确的错误信息和建议

---

### 第二优先级（提升质量和效率）

#### 3.4 优化 System Prompt

改动要点:
1. 增加"任务边界"指令: 严格按用户数量执行，完成后停止并汇报
2. 增加"结果检查"指令: 每次工具执行后必须检查结果，成功则继续，失败则尝试修复
3. 增加"工作记忆"格式: Agent 每轮维护一个 [已完成/待办] 列表

新增 System Prompt 段落:
```
## 执行规范
1. 严格执行用户要求的任务，不做多余操作。用户说生成1张图就只生成1张。
2. 每次工具执行后，立即检查结果:
   - 成功: 记录产出（文件路径等），继续下一步
   - 失败: 分析错误原因，尝试修复（最多重试1次）
3. 所有步骤完成后，输出完整汇报:
   - 已完成的步骤
   - 产出文件路径
   - 是否有问题
4. 不要自作主张生成更多变体，除非用户明确要求
5. 保持工作记忆: 记住每一步的产出路径，后续步骤直接引用，不要重复查找文件
```

#### 3.5 增加工作记忆（Working Memory）

核心改动文件: agent_runner.py

改动要点:
1. 维护一个 artifacts 列表（生成的文件路径、URL）
2. 每轮开始时把 artifacts 作为系统消息注入
3. _compact_tool_result() 对媒体路径永远保留完整信息

#### 3.6 Thinking 输出过滤

核心改动文件: agent_runner.py

改动要点:
- thinking 事件只保留中文部分或关键摘要
- 英文推理过程写入 debug 日志但不发给前端

---

### 第三优先级（体验优化）

#### 3.7 前端改进
1. 增加"自动执行"开关（toggle 按钮）
2. 增加"全部批准"快捷按钮（在多个 tool_confirm 时出现）
3. 错误卡片红色高亮显示
4. 进度条: 显示"第 X/Y 步" 

#### 3.8 错误恢复机制
1. 工具失败后 Agent 自动诊断 + 重试
2. 连续失败 2 次后通知用户并给出建议
3. ComfyUI 不可用时给出明确提示而非静默失败

---

## 四、实施建议

| 阶段 | 内容 | 预估工作量 | 影响 |
|------|------|-----------|------|
| 第一阶段 | 3.1 循环改造 + 3.2 审批改造 + 3.3 i2v修复 | 2-3天 | 解决核心卡顿问题 |
| 第二阶段 | 3.4 Prompt优化 + 3.5 工作记忆 + 3.6 Thinking过滤 | 1-2天 | 提升执行效率和质量 |
| 第三阶段 | 3.7 前端改进 + 3.8 错误恢复 | 1-2天 | 体验优化 |

建议从第一阶段开始，重点解决 3.1（Agent 循环改造）— 这是所有问题的根源。

---

## 五、关键代码定位

| 问题 | 文件 | 行号 | 说明 |
|------|------|------|------|
| Agent 循环退出逻辑 | agent_runner.py | 411-435 | 无工具调用时的处理 |
| 计划检测正则 | agent_runner.py | 413-416 | 过于狭窄，漏判多 |
| 审批工具集 | agent_runner.py | 37-40 | AUTO_APPROVE_TOOLS |
| 工具结果压缩 | agent_runner.py | 115-163 | _compact_tool_result |
| 历史压实 | agent_runner.py | 96-112 | _compact_history |
| Thinking 透传 | agent_runner.py | 382-384 | 直接 yield 无过滤 |
| image_to_video | tool_executor.py | 154-174 | ComfyUI 调用 |
| WS 审批分发 | comic_agent.py | 762-815 | approval_queue 机制 |
| 前端审批按钮 | ComicAgentView.vue | 297-327 | tool_confirm 模板 |
| 前端 tool_done 处理 | ComicAgentView.vue | 864-927 | 媒体URL提取 |
