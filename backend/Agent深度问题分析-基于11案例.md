# Agent 深度问题分析（基于 11 个人工测试案例）

> 分析时间：2026-04-29  
> 分析范围：人工测试案例.md 全部 11 个案例 + 漫剧Agent全功能测试用例.md  
> 涉及文件：agent_runner.py / tool_executor.py / ComicAgentView.vue

---

## 一、问题汇总（按严重程度排序）

| # | 问题 | 严重度 | 涉及案例 | 现象 |
|---|------|--------|---------|------|
| 1 | **拒绝后无限重试** | 🔴 P0 | 案例2 | 用户拒绝 generate_image → force_tool_choice=required → LLM 再调同一工具 → 再被拒 → 循环 |
| 2 | **完成后被 force 重复操作** | 🔴 P0 | 案例4/6/10 | 任务已完成但没 [TASK_DONE] → is_mid_task → force → 重复执行已完成工具 |
| 3 | **任务拆解范式缺失** | 🔴 P0 | 案例1/4/6 | LLM 先输出文字计划不调工具 → 被 force → 浪费迭代 |
| 4 | **工具执行路径错误** | 🟡 P1 | 案例8/9 | find_files/python_exec cwd 不对，edit_file 精确匹配失败 |
| 5 | **TTS 空错误信息** | 🟡 P1 | 案例3 | TTS 返回 {"error": ""} → LLM 无法诊断 |
| 6 | **前端无图片上传** | 🟡 P1 | — | 无法给 Agent 传参考图 |
| 7 | **首轮幻觉回复** | 🟠 P2 | 案例4/6 | LLM 从历史上下文"回忆"出结果，不实际调工具 |

---

## 二、逐案例详细分析

### 案例1: 搜索+写入+生图 ✅ 基本成功
- web_search(自动) → write_file(确认) → generate_image(确认) ✅
- **问题**: 图片生成后 LLM 输出文字但没调工具 → "检测到计划未执行" → "强制续行" → 最终 read_file 回验
- **浪费**: 第4~7轮中有 3 轮空转
- **根因**: LLM 完成3步后想输出总结，但文字匹配到 `has_plan` → 被 force → 不该被 force

### 案例2: 拒绝后重试 🔴 最严重
- 用户拒绝 generate_image × 2 次
- 每次拒绝后 `is_mid_task` → `force_tool_choice=required` → LLM 被迫再调同一工具
- 第 3 次换了 seed 被批准，但 ComfyUI 报错
- **根因**: 拒绝事件后，`no_tool_streak` 不增加（因为有 tool_call），`force` 逻辑不知道工具被拒绝了
- **正确行为**: 用户拒绝 = 明确意愿，Agent 应停止该工具、询问用户或切换方案

### 案例3: 链式生图→视频→TTS ⚠️ 部分成功
- generate_image ✅ → image_to_video ✅（路径正确）→ TTS ❌❌
- TTS 连续 2 次返回 `{"status": "error", "error": ""}` — **空错误信息**
- LLM 无法判断失败原因，开始无意义的"检查系统""检查环境"循环
- **根因1**: TTS 工具未返回有意义的错误信息
- **根因2**: Agent 对连续失败没有熔断逻辑

### 案例4: 只读工具 ⚠️ 功能正确但低效
- LLM 第一轮直接输出了目录和 README 内容（凭上下文记忆），没调工具
- 系统 force → list_dir → find_files → read_file → 又 force → 又 find_files（重复）
- **浪费**: 7 轮迭代完成了 2 步简单操作
- **根因**: LLM 试图"直接回答"被 force 打回，然后被 force 过度导致重复调用

### 案例5: 写脚本+执行+写入 ⚠️ 截断
- 只记录到"检测到计划未执行"

### 案例6: bash 查看系统信息 ⚠️ 功能正确但浪费
- bash 命令成功返回 Python 版本和磁盘信息
- 之后 LLM 输出总结但没 [TASK_DONE] → force × 2
- **浪费**: 2 轮空转
- **根因**: 简单任务一步就能完成，但 LLM 不会主动加 [TASK_DONE]

### 案例7: python_exec 斐波那契 ⚠️ 截断
- 只记录到"检测到计划未执行"

### 案例8: 图片编辑 ❌ 失败
- find_files 搜索 `**/*.{png,jpg,...}` in `.` → matches: []
- **根因**: find_files 的 cwd 是 backend/，但图片在 uploads/agent_outputs/；glob 模式可能不匹配
- **更深根因**: 工作记忆中有图片绝对路径，但 LLM 选择用 find_files 搜索而不是直接使用

### 案例9: 文件编辑 ❌ 失败
- read_file 成功读到内容
- edit_file 提交的 old_string 被截断 → "old_string 在文件中未找到"
- python_exec 替换 → FileNotFoundError（cwd=/tmp，不是 backend/）
- **根因1**: edit_file 的 old_string 是 LLM 从 read_file 结果截取的，不精确
- **根因2**: python_exec 默认 cwd 是 /tmp

### 案例10: HTTP 请求 ✅ 成功但浪费
- http_request 成功获取 httpbin 响应
- 之后 force 又发了一次完全相同的请求
- **浪费**: 1 轮重复
- **根因**: 同案例 6，LLM 不输出 [TASK_DONE]

### 案例11: 端到端短剧 — 进行中
- generate_image ✅ → image_to_video 执行中

---

## 三、根因归类

### A. 循环控制逻辑缺陷（agent_runner.py）

1. **拒绝后 force 循环** — 用户拒绝工具后，`no_tool_streak` 不增加（因为有 tool_call 进入了工具分支），但工具被拒绝了 → 下一轮 `is_mid_task=true` → force
2. **完成检测过于依赖 [TASK_DONE]** — LLM 很少主动输出 [TASK_DONE]，导致几乎每次任务结束都被 force
3. **has_plan 误匹配** — `"如果你要"、"接下来"` 等词被误判为"有计划"，但可能只是收尾建议

### B. System Prompt 不够结构化

1. 没有明确的"任务拆解范式"——用户期望以工具调用为维度拆分任务
2. 没有强调 [TASK_DONE] 的重要性
3. 没有告诉 LLM"拒绝后应该怎么做"
4. 没有告诉 LLM"工具失败后的策略"（重试1次 vs 换方案 vs 放弃）

### C. 工具层面问题

1. **python_exec cwd** = /tmp，LLM 生成的路径是相对路径 → FileNotFoundError
2. **edit_file 精确匹配** 对 LLM 来说很难做到（LLM 看到的内容可能被截断）
3. **TTS 空错误信息** 无法帮助 LLM 诊断
4. **find_files glob 模式** 限制较大

---

## 四、优化方案

### P0: 循环控制修复

#### 修复1: 拒绝感知
- 在工具拒绝后设置 `rejected_tool` 标记
- 如果同一工具连续被拒绝 2 次 → 自动结束该工具链，询问用户
- 拒绝后注入消息："用户已拒绝该操作，请不要重试同一工具，转而询问用户或调整方案。"

#### 修复2: 完成检测增强
- 扩展完成信号：除 [TASK_DONE] 外，增加"任务完成"、"已完成"、"以上是"等中文信号
- 检测"收尾性文字"模式：如果 LLM 输出包含"如果你需要"+"已完成"等组合 → 视为完成
- 简单任务快速退出：如果只有 1 个工具调用 + LLM 输出了总结 → 不 force

#### 修复3: has_plan 误匹配修正
- 排除收尾建议性文字（"如果你要"、"你也可以"、"我还可以"）
- 只匹配真正的执行计划

### P0: System Prompt 优化

#### 任务拆解范式
```
## 执行策略
1. 收到任务后，按"一个工具调用=一个子任务"拆分
2. 每个子任务直接调用工具，不要只说计划
3. 最后一步纯文字汇报结果，输出 [TASK_DONE]
4. 如果某步不需要工具 → 执行后对比用户需求 → 不满足则继续拆分
5. 用户拒绝某工具 → 停止该路线，询问是否换方案
6. 工具失败 → 最多重试1次，仍失败则汇报并建议替代方案
```

### P1: 工具修复

1. **python_exec cwd**: 改为 backend/ 目录
2. **edit_file**: 改为 sed/regex 替换模式，不依赖精确匹配
3. **TTS 错误信息**: 确保返回有意义的错误描述

### P1: 前端图片上传
- 输入框左侧添加📎上传按钮
- 支持拖拽/粘贴图片
- 上传到后端 /api/v1/comic-agent/upload
- WS 消息中携带 image_paths 数组
- System prompt 注入用户附件路径

---

## 五、实施优先级

| 优先级 | 内容 | 预估影响 |
|--------|------|---------|
| P0-1 | 修复拒绝后无限重试 | 解决案例2 |
| P0-2 | 增强完成检测 + 减少 force 误触 | 解决案例4/6/10 |
| P0-3 | 优化 System Prompt 任务拆解范式 | 解决案例1/4/6 首轮空转 |
| P1-1 | 前端图片上传 | 新功能 |
| P1-2 | 工具路径修复 (python_exec/edit_file) | 解决案例8/9 |
| P1-3 | TTS 错误信息 | 解决案例3 |
