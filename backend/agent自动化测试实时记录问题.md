# 漫剧 Agent 自动化测试实时记录与问题分析

> 测试时间: 2026-04-29 22:35 ~ 23:08
> 模型: claude-opus-4-6
> 用例总数: 80 | 通过: 33 (41%) | 失败: 6 | 错误: 41
> 有效测试(排除后端崩溃): 39 | 有效通过率: 33/39 = **84.6%**

---

## 一、测试执行时间线

| 时间 | 事件 | 影响 |
|------|------|------|
| 22:35 | 测试启动，登录成功 | - |
| 22:35~22:58 | 用例 12-50 顺利执行 (39个) | 33 pass / 6 fail |
| 22:58 | **用例 50 edit_image 耗时 185s**，Agent 找不到图片反复 list_dir+bash (11次工具调用) | 性能瓶颈 |
| 23:00 | **用例 51 image_to_video 触发 WS 1011 错误** | 后端连接崩溃 |
| 23:01~23:08 | 用例 52-91 全部 `timed out during opening handshake` (10s) | **40个用例作废** |
| 23:08 | 测试结束，生成报告 | 总耗时 1995s |

---

## 二、问题分类与根因分析

### 🔴 P0: 后端 WS 连接崩溃 (影响 40 个用例, 50%)

**现象**: 用例 51 (image_to_video) 执行后，后端 WebSocket 不再接受新连接。

**错误链**:
```
用例51: sent 1011 (internal error) keepalive ping timeout; no close frame received
用例52~91: timed out during opening handshake (每个 10s)
```

**后端日志**:
```
23:01:12 | ERROR | tool_executor:execute_image_to_video:215 - [ToolExec] image_to_video failed: (编码截断)
23:01:12 | INFO  | exec tool=image_to_video args={source_image: '/uploads/agent_outputs/test.png'}
```

**根因分析**:
1. `image_to_video` 工具执行失败（图片文件不存在）
2. 错误处理后 Agent 继续循环(iter=2 调 list_dir 查找图片)
3. WS 连接在 Agent 循环过程中因 keepalive ping 超时断开
4. **关键**: 断开后后端 uvicorn 单 worker 可能资源未释放（WS handler 未正常退出）
5. 后续所有 WS 握手请求在 10s 内无法完成

**修复建议**:
- 测试脚本: 每个用例执行前先做 HTTP 健康检查，连续失败时自动重启后端或跳过后续用例
- 后端: `websocket_agent_chat` 函数中增加更完善的异常恢复和资源释放
- 部署: 考虑使用多 worker (`uvicorn --workers 2`) 避免单点阻塞

---

### 🟡 P1: Agent 输出计划但不执行工具 (影响 6 个用例, 7.5%)

**失败用例**:

| 用例 | 名称 | Agent 回复特征 | 耗时 |
|------|------|---------------|------|
| 29 | bash 管道命令 | "分2步完成：1) 用 bash 执行..." | 18.8s |
| 33 | 英文指令 | "分2步完成：1) 用 bash 获取..." | 20.9s |
| 40 | 工具失败后正确处理 | "按你的要求直接执行这条命令..." | 22.0s |
| 43 | generate_image 动漫风格 | "分2步完成：1) 先生成 anime..." | 13.0s |
| 46 | generate_image 写实风格 | "分2步完成：1) 先生成写实风格..." | 24.1s |
| 48 | generate_image Flux风格 | "分2步完成：1) 按要求生成 Flux..." | 12.3s |

**共同模式**: Agent 输出类似 `"分2步完成"` 的文字计划，描述它将要做什么，但 LLM 以 `finish=stop` 结束，**没有实际发起工具调用**。

**后端日志证据**:
```
iter=0 tool_calls=0 text_len=83 force_was=None          ← 第1轮: 输出文字计划，0工具
检测到计划未执行，强制 tool_choice=required (iter=0)       ← 触发续行
iter=1 tool_calls=0 text_len=57 force_was=required       ← 第2轮: 仍然0工具！
```

**根因**: `tool_choice=required` 在 Opus 模型上偶发失效。Opus 有时会将"描述计划"视为已完成回答。

**修复建议**:
- System Prompt 强化: 添加 `"禁止输出纯文字计划，必须直接调用工具"` 类指令
- agent_runner: `no_tool_streak` 达到 2 时直接注入更强硬的系统提示
- 测试脚本: 对 `cont≥1` 且 `tools=[]` 的用例自动重试一次

---

### 🟢 P2: ComfyUI 工具执行错误 (影响 3 个用例)

| 用例 | 工具 | 错误 |
|------|------|------|
| 50 | edit_image | 图片文件不存在: /uploads/agent_outputs/test.png |
| 51 | image_to_video | 图片文件不存在 (同上) |
| (后端日志) | upscale_image | ComfyUI 400: Node 'Note' not found |

**根因**:
1. **文件路径问题**: Agent 使用虚构路径 `/uploads/agent_outputs/test.png`，该文件不存在。测试环境中没有预置图片。
2. **ComfyUI 节点缺失**: `upscale_image` 工作流中引用了 `Note` 节点，远程 ComfyUI 未安装对应自定义节点。

**修复建议**:
- 测试环境: 预置一张测试图片到 `/uploads/agent_outputs/test_sample.png`
- 测试用例: 图片相关用例提供真实存在的图片路径 (如 `image_paths` 字段)
- ComfyUI: 确认远程服务器已安装所有必需的自定义节点

---

### 🔵 P3: 性能问题 (5 个用例 > 60s)

| 用例 | 名称 | 耗时 | 工具数 | 续行数 | 原因 |
|------|------|------|--------|--------|------|
| 15 | web_search | 153.6s | 6 | 3 | 搜索6次才满意 |
| 23 | 多工具链式组合 | 104.4s | 5 | 1 | web_search+write+read 链路长 |
| 30 | 多步依赖传递 | 66.7s | 6 | 2 | python→write→read 多步 |
| 50 | edit_image | 185.5s | 11 | 7 | 找不到图片，反复 list_dir+bash |
| 51 | image_to_video | 70.0s | 2 | 2 | 工具失败后继续尝试 |

**用例 50 详情**: Agent 被要求编辑图片，但测试环境没有图片文件。Agent 先调 `edit_image` 失败，然后调 `list_dir` 搜索 → `bash find` 搜索 → 反复 7 轮，最终仍未找到，触发 MAX_TOOL_CALLS_ABORT。

---

## 三、通过用例效率分析

### 高效用例 (效率 = 1.0, 一次调对工具)

| 用例 | 名称 | 耗时 | 工具 |
|------|------|------|------|
| 12 | 纯聊天 | 11.6s | - (正确不调工具) |
| 14 | read_file | 26.4s | read_file |
| 18 | grep_search | 20.1s | grep_search |
| 24 | 复杂 Python 数据处理 | 17.1s | python_exec |
| 25 | 异常处理-读不存在文件 | 24.3s | read_file |
| 27 | 模糊意图识别 | 18.8s | - (正确不调工具) |
| 32 | 中文问答不调工具 | 6.5s | - |
| 36 | web_search 简短查询 | 35.3s | web_search |
| 38 | 闲聊后提问不调工具 | 9.8s | - |
| 39 | 超长消息处理 | 26.1s | python_exec |
| 42 | generate_image 仙侠风格 | 48.3s | generate_image |
| 44 | generate_image 盲盒Q版 | 26.2s | generate_image |
| 45 | generate_image 水墨风 | 47.1s | generate_image |
| 47 | generate_image 自定义尺寸 | 25.0s | generate_image |

### 效率偏低用例 (调了多余工具)

| 用例 | 名称 | 预期工具 | 实际调用 | 多余行为 |
|------|------|---------|---------|---------|
| 13 | list_dir | list_dir | list_dir + bash×2 | 多调了2次 bash |
| 15 | web_search | web_search | web_search×6 | 搜索6次 |
| 19 | find_files | find_files | find_files + bash×2 | 多调了2次 bash |
| 22 | http_request | http_request | http_request×2 | 多调了1次 |
| 37 | write_file 安全路径 | write_file | write_file×2 | 多写了1次 |
| 50 | edit_image | edit_image | edit_image + list_dir×5 + bash×4 | 严重偏离 |

**Agent "多调 bash" 倾向**: Opus 模型在某些场景下偏好用 `bash` 替代专用工具，或者在工具完成后用 `bash` 做额外验证。

---

## 四、测试框架问题

### 4.1 WS 握手超时过短
- 默认 `websockets.connect()` 的 `open_timeout=10s`
- 后端负载较高时 10s 不够完成握手
- **建议**: 显式设置 `open_timeout=30`

### 4.2 缺少后端健康检查
- 测试脚本在后端崩溃后仍然逐个尝试连接，浪费时间
- **建议**: 每个用例前 `GET /docs` 检测后端存活，连续 3 次失败则跳过或重启

### 4.3 缺少测试图片预置
- 漫剧工具测试 (edit_image, i2v, upscale 等) 需要真实图片
- 当前测试只发文字消息，Agent 被迫先生成/查找图片
- **建议**: 在测试初始化阶段预生成一张图片，后续用例引用其路径

---

## 五、下一步行动计划

| 优先级 | 行动项 | 预计效果 |
|--------|--------|---------|
| P0 | 测试脚本增加健康检查 + 后端崩溃自动跳过 | 避免 40 个用例浪费 |
| P0 | WS `open_timeout` 改为 30s | 减少误判 |
| P1 | 漫剧工具测试预置一张图片 | edit/i2v/upscale 可正常执行 |
| P1 | System Prompt 强化禁止纯计划输出 | 减少 6 个 "计划但不执行" 失败 |
| P2 | ComfyUI 检查 Note 节点安装 | upscale_image 可用 |
| P2 | 多 worker 部署 (`--workers 2`) | 避免单点阻塞 |
| P3 | 失败用例自动重试 1 次 | 应对 LLM 随机性 |

---

---

# 第二部分：ComfyUI 远程 Workflow 可用性测试

> 测试时间: 2026-04-30 08:38~08:48
> GPU: NVIDIA GeForce RTX 5090 (cuda:0)
> ComfyUI: https://u982127-7772b8fbe6d9.bjb2.seetacloud.com:8443
> 测试方式: 绕过 Agent，直接调用 ComfyUI HTTP API
> 测试素材: `uploads/agent_outputs/03f0159d9099.png` (1323KB)
> 完整 Excel: `/tmp/comfyui_workflow_test_report.xlsx` (5 Sheets)
> 完整 MD 报告: `/tmp/comfyui_workflow_test_report.md`

## 七、远程 Workflow 测试总览

| 指标 | 数值 |
|------|------|
| 已启用工作流总数 | 69 |
| ✅ 通过 | **7 (10.1%)** |
| ❌ 失败 | 46 (66.7%) |
| ⏭ 跳过(JSON未找到) | 16 (23.2%) |

### 按分类统计

| 分类 | 总数 | ✅ | ❌ | ⏭ | 通过率 | 平均耗时 |
|------|------|-----|-----|-----|--------|---------|
| t2i (文生图) | 34 | 5 | 23 | 6 | 14.7% | 15.7s |
| edit (图像编辑) | 17 | 1 | 13 | 3 | 5.9% | 30.9s |
| i2v (图生视频) | 6 | 1 | 1 | 4 | 16.7% | 468.7s |
| t2v (文生视频) | 5 | 0 | 2 | 3 | 0% | - |
| face (人脸保持) | 5 | 0 | 5 | 0 | 0% | - |
| upscale (超分) | 1 | 0 | 1 | 0 | 0% | - |
| audio (音频) | 1 | 0 | 1 | 0 | 0% | - |

---

## 八、✅ 可用工作流清单 (7个)

| 工作流 | 分类 | 风格 | 耗时 | 输出 |
|--------|------|------|------|------|
| **动漫基础文生图** (anime_basic) | t2i | anime | 12.65s | 442KB PNG |
| **盲盒Q版文生图** (blindbox_q) | t2i | blindbox | 3.51s | 394KB PNG |
| **水墨风文生图** (moxin_ink) | t2i | ink | 6.55s | 348KB PNG |
| **仙侠基础文生图** (xianxia_basic) | t2i | xianxia | 18.66s | 434KB PNG |
| **Z-Image 通用文生图** (z_image_t2i) | t2i | realistic | 36.99s | 385KB PNG |
| **Qwen 图像编辑** (qwen_edit) | edit | - | 30.89s | 448KB PNG |
| **Wan 图生视频** (wan_i2v) | i2v | - | 468.66s | 4424KB MP4 |

**共同特征**: 这 7 个都是根目录的旧格式 JSON（`xxx.json`），不依赖 MarkdownNote/Note/Reroute 等自定义注释节点。

---

## 九、❌ 失败原因分类 (46个)

### 9.1 节点缺失 — 占失败的 93.5%

| 缺失节点 | 影响数量 | 影响工作流 |
|----------|---------|-----------|
| **MarkdownNote** | 30 | Flux/HiDream/Qwen/SD/SDXL/Z-Image/LBM/双截棍/音频分离 |
| **Note** | 7 | 双截棍QwenImage/Flux-fill/SD15面部/SeedVR2超分 |
| **Reroute** | 4 | Flux-fill画面清除/扩图 (fp4+int4) |
| **PrimitiveNode** | 2 | Flux-fp16四件套/Flux2图像编辑 |
| **GetNode** | 1 | LTX-2图像加音频到视频 |

**根因**: 这些都是 **ComfyUI 注释/辅助节点**，用于在 ComfyUI 编辑器中添加说明文字。它们不参与实际计算，但提交 workflow 时 ComfyUI 会校验所有节点是否存在。

**修复方案（二选一）**:
1. **在 ComfyUI 安装缺失节点**（推荐）:
   - `ComfyUI-Custom-Scripts` → 含 MarkdownNote, Note, Reroute, PrimitiveNode
   - `rgthree-comfy` → 含 GetNode/SetNode
2. **从 workflow JSON 中删除注释节点**:
   - 写脚本遍历所有 JSON，删除 `class_type` 为 MarkdownNote/Note 的节点
   - 优点: 不依赖额外安装
   - 缺点: 在 ComfyUI 编辑器中丢失注释

### 9.2 参数校验失败 — 2个

| 工作流 | 错误 |
|--------|------|
| SD15-简单文生图 | `scheduler: 'euler' not in ['simple','sgm_uniform','karras',...]` |
| SD15-简单图生图 | `method: '8' not in ['lanczos','bicubic',...]` |

**根因**: ComfyUI 版本更新后部分参数值被移除。旧 JSON 中硬编码的 `euler` scheduler 不再被支持。

### 9.3 ComfyUI 执行错误 — 1个

| 工作流 | 错误 |
|--------|------|
| 仙侠人脸保持 (xianxia_instantid) | 执行开始后崩溃（推测 InstinaID 模型未加载） |

---

## 十、⏭ JSON 未找到分析 (16个)

**根因**: `load_by_name()` 函数在 DB name → 文件路径的转换中：
- `__` → `/` 和 `_` → ` ` 的转换规则无法处理中文文件名中嵌入的 `_`
- 例如: `Wan视频系列__Wan2_2-14B图生视频_4步` 无法正确映射到 `Wan视频系列/Wan2.2-14B图生视频 4步.json`
- `Wan2_2` 被替换为 `Wan2 2` 而实际文件名是 `Wan2.2`

**修复方案**: 需要修改 `workflow_registry.py` 的 `_make_name()` 和 `load_by_name()` 的编码/解码规则，或在 DB 中存储实际文件的相对路径。

---

## 十一、下一步行动计划（更新）

| 优先级 | 行动项 | 预计效果 |
|--------|--------|---------|
| **P0** | ComfyUI 安装 `ComfyUI-Custom-Scripts` + `rgthree-comfy` | 解锁 44 个工作流 (MarkdownNote+Note+Reroute+PrimitiveNode+GetNode) |
| **P0** | 修复 `load_by_name` 路径解析 | 解锁 16 个跳过的工作流 |
| **P1** | 修复 SD15 参数校验（euler→simple） | 解锁 2 个 SD15 工作流 |
| **P1** | 检查 InstinaID 模型是否已加载 | 解锁 face 类工作流 |
| **P2** | Agent 测试脚本增加健康检查 + 后端崩溃自动跳过 | 避免 40 个用例浪费 |
| **P2** | System Prompt 强化禁止纯计划输出 | 减少 6 个 "计划但不执行" 失败 |
| **P3** | 多 worker 部署 | 避免单点阻塞 |

---

## 六、Sonnet vs Opus 对比

在本轮测试之前，曾用 `claude-sonnet-4-6` 执行过一轮:

| 指标 | Sonnet | Opus |
|------|--------|------|
| 前 10 个用例通过率 | 2/10 (20%) | 10/10 (100%) |
| 工具正确传递 | ❌ tools=0 (工具定义丢失) | ✅ tools=19 |
| 根因 | `_MODELS_NO_TOOLS_STREAM` 误标记 | 正常 |

**Sonnet 问题**: `openai_client.py` 中 `_MODELS_NO_TOOLS_STREAM` 集合在单次流式+工具报错后**永久标记模型不支持工具**，后续所有请求 `skip_tools=True`，导致 `tools=0`。这是一个严重的后端 bug，需要修复（改为带过期时间的临时标记或直接移除该机制）。
