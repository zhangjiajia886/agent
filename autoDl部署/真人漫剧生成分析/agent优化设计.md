# 漫剧 Agent 优化设计：给系统装上「大脑」

> 深度分析 + 可执行改造方案  
> 2026-04-28

---

## 一、你的质疑完全正确

> "我选择了哪个模型，哪个模型就是大脑。"

这句话完全正确。你有 21 个模型（Claude Sonnet 4.6 / GPT 5.x / Gemini 3.x / Qwen3-32B...），每一个都可以作为大脑。**问题不是没有大脑，而是大脑和身体之间的「神经」被切断了。**

---

## 二、精准病灶诊断：四条断裂的「神经」

### 断裂全景图

```
前端用户选择了模型                后端 WebSocket 接收消息
┌──────────────┐               ┌──────────────────────┐
│ selectedModel│               │ websocket_agent_chat()│
│ = "claude-   │──── WS ──→   │                       │
│   sonnet-4-6"│   send()      │ style = data["style"] │
│              │               │ frames= data["frames"]│
│              │               │ model = ??? ← 没读！  │ ← 断裂 ①
└──────────────┘               └──────────┬───────────┘
                                          │
                               ┌──────────▼───────────┐
                               │ smart_agent_stream()  │
                               │                       │
                               │ intent = 关键词匹配    │ ← 断裂 ② 没调LLM
                               │ 生成   = picsum 占位图 │ ← 断裂 ③ 没调ComfyUI
                               │ 上下文 = 无状态        │ ← 断裂 ④ 没传历史
                               └───────────────────────┘
```

### 断裂 ① — 前端传了 model，后端没接

**前端发送：**
```typescript
// ComicAgentView.vue:606-609
agentWS.send(text, {
  style: selectedStyle.value,
  frames: selectedFrames.value,
  model: selectedModel.value,    // ← 用户选的模型传了
  tts: ttsEnabled.value,
  autoVideo: autoVideo.value,
})
```

**后端接收：**
```python
# comic_agent.py:427-433
data = await websocket.receive_json()
message = data.get("message", "").strip()
style = data.get("style", "auto")
frames = data.get("frames", 0)
# model = data.get("model") ← 这行不存在！被丢弃了
```

**结论：** 用户选了 Claude Sonnet 4.6，前端也传了，但后端直接无视。

### 断裂 ② — 意图识别用关键词，没调 LLM

**当前 smart_agent.py：**
```python
def _detect_intent(text: str) -> str:
    t_low = text.lower()
    for intent, kws in _INTENT_KW:
        if any(kw.lower() in t_low for kw in kws):
            return intent        # ← 关键词命中即返回
    if len(text.strip()) > 10:
        return "comic"           # ← 10字以上默认漫剧
    return "chat"
```

**对比 ComicAgent（HTTP路径）：**
```python
# comic_agent/intent_parser.py — 正确地调用了 LLM
intent = await parse_intent(request.description, self.llm)
```

**结论：** HTTP 路径用 LLM 理解用户意图，WebSocket 路径却用关键词硬匹配。同一个系统两套脑子，一个聪明一个傻。

### 断裂 ③ — 工具调用是 Mock 的，没调 ComfyUI

**当前 smart_agent.py：**
```python
# 漫剧生成 — 用的是 picsum 随机图片！
seed = random.randint(100, 99999)
yield {
    "type": "tool_done",
    "tool": "generate_image",
    "image_url": f"https://picsum.photos/seed/{seed}/768/768",  # ← 网络占位图
}
```

**对比 ComicAgent（HTTP路径）：**
```python
# comic_agent/agent.py — 真正调用 ComfyUI GPU
frame_bytes = await self.comfyui.run_workflow(workflow)
```

**结论：** HTTP 路径调用真实 GPU 生成图片，WebSocket 路径返回随机猫狗照片。

### 断裂 ④ — 无对话历史，每轮独立

```python
# 每条消息独立处理，不传递历史
async for event in smart_agent_stream(message, style, frames):
    # message 只有当前这一条，没有之前的对话
```

**结论：** 用户说"把刚才那张图改成夜景"，Agent 不知道"刚才哪张图"。

---

## 三、为什么会这样？— 系统演化路径分析

```
阶段1: Mock 原型（已完成）
─────────────────────────────────
目标: 先让前端 UI 能跑起来
做法: mock_agent.py → 用 sleep + picsum 模拟事件流
效果: ✅ 前端对话框 + 工具卡片 + 图片显示 全部联通

阶段2: ComicAgent 管线（已完成）
─────────────────────────────────
目标: 先让 HTTP 路径能真实生成图片
做法: agent.py → LLM + ComfyUI 完整管线
效果: ✅ POST /comic/generate 能生成真实漫剧

阶段3: SmartAgent 升级（已完成一半）
─────────────────────────────────
目标: 比 mock_agent 更智能一点
做法: smart_agent.py → 关键词意图分发
效果: ⚠️ 比 Mock 强一些，但仍然是假的

■ 你现在在这里 ■

阶段4: 大脑接入（← 需要做的）
─────────────────────────────────
目标: 用户选的模型作为大脑驱动整个流程
做法: 本文档的设计方案
```

**核心原因：** 阶段 2 的 ComicAgent（HTTP路径）和阶段 3 的 SmartAgent（WebSocket路径）是独立开发的，没有合并。**ComicAgent 有 LLM + GPU 但没有对话能力；SmartAgent 有对话能力但没有 LLM + GPU。**

---

## 四、修复设计：「接通神经」

### 4.1 设计理念

**不是重写，而是接线。** 所有零部件已经存在：

| 零部件 | 状态 | 位置 |
|--------|------|------|
| 21 个 LLM 模型 | ✅ 已入库 | `model_config` 表 |
| ComfyUI 客户端 | ✅ 已实现 | `comfyui_client.py` |
| ComicAgent 管线 | ✅ 已实现 | `comic_agent/agent.py` (generate/edit/animate/t2v/upscale) |
| 工作流选择器 | ✅ 已实现 | `workflow_selector.py` |
| 工具注册表 | ✅ 已入库 | `tool_registry` 表 |
| 前端对话 UI | ✅ 已实现 | `ComicAgentView.vue` |
| WebSocket 通道 | ✅ 已实现 | `ws/chat` |
| 消息持久化 | ✅ 已实现 | `agent_conversation` + `agent_message` |

**缺的只是一个 LLM Agent Runner**，把用户选的模型作为大脑，让它调度现有工具。

### 4.2 新增核心文件：`agent_runner.py`

```
backend/app/core/comic_chat_agent/
├── mock_agent.py        # 保留，Mock 模式
├── smart_agent.py       # 保留，关键词模式
└── agent_runner.py      # ★ 新增：LLM Agent Runner
```

### 4.3 架构设计

```
                    用户消息 + 对话历史 + 用户选的模型
                              │
                    ┌─────────▼──────────┐
                    │   AgentRunner      │
                    │                    │
                    │ 1. 查 DB 获取模型   │
                    │    的 base_url +   │
                    │    api_key         │
                    │                    │
                    │ 2. 构造 LLM 客户端  │
                    │    (OpenAI 兼容)   │
                    │                    │
                    │ 3. 构造 system     │
                    │    prompt + tools  │
                    │                    │
                    │ 4. ReAct 循环      │
                    │    ┌──────────┐    │
                    │    │ LLM 思考 │◄───┤
                    │    └────┬─────┘    │
                    │         │          │
                    │    ┌────▼─────┐    │
                    │    │ 返回文字? ├─yes─► yield text 事件
                    │    └────┬─────┘    │
                    │         │no        │
                    │    ┌────▼─────┐    │
                    │    │ 工具调用? │    │
                    │    └────┬─────┘    │
                    │         │yes       │
                    │    ┌────▼──────────┐│
                    │    │ yield tool_   ││
                    │    │ start 事件    ││
                    │    │              ││
                    │    │ 执行工具:    ││
                    │    │ ComfyUI /    ││
                    │    │ ComicAgent / ││
                    │    │ TTS / HTTP   ││
                    │    │              ││
                    │    │ yield tool_  ││
                    │    │ done 事件    ││
                    │    └──────┬───────┘│
                    │           │        │
                    │    观察结果回注历史  │
                    │    继续 ReAct 循环  │
                    └────────────────────┘
```

### 4.4 关键设计细节

#### (A) 动态 LLM 客户端 — 用户选啥模型就用啥

```python
# agent_runner.py 核心逻辑（伪代码）

async def create_llm_client(model_config: ModelConfig):
    """根据 DB 中的模型配置，动态创建 LLM 客户端"""
    if model_config.provider == "aipro":
        # AIPro 是 OpenAI 兼容接口
        return OpenAICompatClient(
            base_url=model_config.base_url,  # https://vip.aipro.love/v1
            api_key=model_config.api_key,    # sk-2NiOQEm...
            model=model_config.model_id,     # claude-sonnet-4-6
        )
    elif model_config.provider == "southgrid":
        # 南格需要 HMAC 签名
        return SouthgridClient(
            base_url=model_config.base_url,
            secret_key=model_config.api_key,
            model=model_config.model_id,
            extra_auth=model_config.extra_auth,
        )
```

**核心点：** 不再硬编码用哪个模型。用户在前端选了 `claude-sonnet-4-6`，后端从 `model_config` 表查出它的 `base_url` 和 `api_key`，动态创建客户端。**选了 GPT 就用 GPT 的脑子，选了 Claude 就用 Claude 的脑子。**

#### (B) 工具定义 — 从 tool_registry 表动态生成

```python
async def build_tool_definitions(db: AsyncSession) -> list[dict]:
    """从 DB tool_registry 读取已启用工具，转为 LLM tool_use 格式"""
    tools = await db.execute(
        select(ToolRegistry).where(ToolRegistry.is_enabled == True)
    )
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,  # 已经是 JSON Schema
            }
        }
        for tool in tools.scalars()
    ]
```

**现有 tool_registry 表已经有完整数据：**
```
generate_image     | ComfyUI 图像生成   | input_schema: {prompt, style, ...}
edit_image         | 图像编辑           | input_schema: {image, instruction}
image_to_video     | 图生视频           | input_schema: {image, motion}
text_to_video      | 文生视频           | input_schema: {prompt, style}
upscale_image      | 超分放大           | input_schema: {image}
generate_comic     | 漫剧生成           | input_schema: {description, style, frames}
tts_synthesis      | TTS 语音合成       | input_schema: {text, voice}
face_swap          | 人脸替换           | input_schema: {source, target}
```

**核心点：** 这些工具定义已经在 DB 里了，只需读出来传给 LLM。LLM 根据用户意图自主决定调什么工具。

#### (C) 工具执行器 — 复用现有 ComicAgent

```python
TOOL_EXECUTORS = {
    "generate_image": execute_generate_image,    # → ComfyUI workflow
    "edit_image":     execute_edit_image,         # → ComicAgent.edit_image()
    "image_to_video": execute_image_to_video,     # → ComicAgent.animate_image()
    "text_to_video":  execute_text_to_video,      # → ComicAgent.text_to_video()
    "upscale_image":  execute_upscale_image,      # → ComicAgent.upscale_image()
    "generate_comic": execute_generate_comic,     # → ComicAgent.generate()
}

async def execute_generate_image(params: dict) -> dict:
    """执行文生图：选工作流 → 注入参数 → ComfyUI 提交 → 等结果"""
    style = params.get("style", "xianxia")
    prompt = params["prompt"]
    workflow_name = select_t2i(style)
    workflow = load_workflow(workflow_name)
    workflow = inject_params(workflow, positive_prompt=prompt, ...)
    image_bytes = await comfyui_client.run_workflow(workflow)
    # 保存到文件，返回 URL
    url = save_to_uploads(image_bytes)
    return {"image_url": url, "status": "success"}
```

**核心点：** 不需要重写生成逻辑。`ComicAgent` 类已经实现了 `generate()`, `edit_image()`, `animate_image()`, `text_to_video()`, `upscale_image()` 全部 5 个能力。只需包装成工具执行器的统一接口。

#### (D) ReAct 循环 — LLM 自主决策

```python
async def agent_loop(
    messages: list[dict],       # 完整对话历史
    llm_client,                 # 用户选的模型
    tools: list[dict],          # 从 DB 加载的工具定义
    websocket: WebSocket,       # 用于推送事件
):
    """核心 ReAct 循环"""
    MAX_ITERATIONS = 10

    for iteration in range(MAX_ITERATIONS):
        # 1. 调用 LLM（带工具定义）
        response = await llm_client.chat(
            messages=messages,
            tools=tools,
            stream=True,  # 流式输出
        )

        # 2. 如果 LLM 返回文字 → 推送给前端
        if response.content:
            await websocket.send_json({
                "type": "text",
                "content": response.content,
            })
            messages.append({"role": "assistant", "content": response.content})

        # 3. 如果 LLM 要调用工具 → 执行并反馈
        if response.tool_calls:
            for call in response.tool_calls:
                # 推送 tool_start
                await websocket.send_json({
                    "type": "tool_start",
                    "tool": call.function.name,
                    "input": call.function.arguments,
                })

                # 执行工具
                executor = TOOL_EXECUTORS[call.function.name]
                result = await executor(call.function.arguments)

                # 推送 tool_done
                await websocket.send_json({
                    "type": "tool_done",
                    "tool": call.function.name,
                    "result": result.get("status"),
                    "image_url": result.get("image_url"),
                })

                # 把工具结果注入消息历史，让 LLM 看到
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                })

            # 继续循环 — LLM 看到工具结果后决定下一步
            continue

        # 4. LLM 既没返回文字也没调工具 → 结束
        break
```

**这就是「大脑」的完整运作方式：**

1. LLM 看到用户说的话 + 历史对话
2. LLM 思考后决定：直接回复？还是调用工具？
3. 如果调工具 → 执行 → 把结果告诉 LLM → LLM 继续思考
4. 循环直到 LLM 觉得任务完成，返回最终文字

### 4.5 修改后的 WebSocket 处理流程

```python
# comic_agent.py websocket_agent_chat() 改造

data = await websocket.receive_json()
message = data.get("message", "").strip()
style = data.get("style", "auto")
frames = data.get("frames", 0)
model_id = data.get("model")       # ★ 接收用户选的模型

# ★ 根据 model_id 查 DB 获取模型配置
model_config = await get_model_config(db, model_id)
llm_client = create_llm_client(model_config)

# ★ 加载对话历史
history = await load_conversation_history(db, conv_id)

# ★ 加载已启用工具
tools = await build_tool_definitions(db)

# ★ 启动 ReAct 循环
await agent_loop(history + [user_message], llm_client, tools, websocket)
```

**对比改造前：**
```python
# 改造前 — 忽略 model，不用 LLM，不传历史
async for event in smart_agent_stream(message, style, frames):
    await websocket.send_json(event)
```

### 4.6 System Prompt 设计

```python
SYSTEM_PROMPT = """你是「漫剧 Agent」，一个专业的 AI 漫画和视觉创作助手。

## 你的能力
你可以通过工具完成以下任务：
- 根据用户描述生成各种风格的图片（仙侠/水墨/盲盒/动漫/写实/Flux）
- 创作多格连环漫剧（规划分镜 → 逐格生成）
- 将图片动态化为视频
- 编辑修改已有图片
- 超分放大提升图片质量
- 语音合成

## 工作原则
1. 先理解用户意图，明确需求后再行动
2. 创作前简要说明方案（风格、构图、分镜规划）
3. 调用工具时传入精确的英文提示词
4. 生成完成后询问用户是否满意，可以调整
5. 对话中记住之前的创作内容，支持"修改上一张"等引用

## 提示词规范
- 图像提示词用英文，质量词(masterpiece, best quality)放在开头
- 根据风格添加对应的风格词
- 负面提示词：ugly, deformed, blurry, bad anatomy, watermark, text, nsfw
"""
```

---

## 五、改造工作量评估

### 5.1 需要新增的文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `core/comic_chat_agent/agent_runner.py` | ~250 | ReAct 循环 + 工具执行器 |
| `core/comic_chat_agent/openai_client.py` | ~120 | OpenAI 兼容 LLM 客户端（AIPro 用） |
| `core/comic_chat_agent/tool_executor.py` | ~180 | 8 个工具的执行器包装 |

### 5.2 需要修改的文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `api/v1/comic_agent.py` | ~30 行 | WebSocket 接收 model 参数，调用 agent_runner |
| `core/llm_client.py` | ~60 行 | 抽象基类 + 南格/OpenAI 两个实现 |
| `core/comic_chat_agent/__init__.py` | ~5 行 | 导出 agent_runner |

### 5.3 不需要改的（复用现有）

| 模块 | 说明 |
|------|------|
| `ComicAgent` 整个类 | generate/edit/animate/t2v/upscale 全部复用 |
| `comfyui_client.py` | 不动 |
| `workflow_selector.py` | 不动 |
| `workflow_registry.py` | 不动 |
| `workflows/*.json` | 不动 |
| `model_config` 表 | 已有完整数据 |
| `tool_registry` 表 | 已有完整数据 |
| 前端全部代码 | 事件协议不变，无需改前端 |

### 5.4 工作量估算

```
新增代码：~550 行（3 个新文件）
修改代码：~95 行（3 个现有文件）
前端代码：0 行（协议兼容）
预计时间：3-4 小时
```

---

## 六、改造前后对比

### 6.1 用户体验变化

**改造前：** 用户说 "画一张仙侠风的月下剑客"
```
SmartAgent: 关键词匹配 → intent="t2i"
→ 返回 picsum 随机图片 (一张猫狗照片)
→ 用户看到一张无关的图片
```

**改造后：** 用户说 "画一张仙侠风的月下剑客"
```
AgentRunner: Claude Sonnet 4.6 分析意图
→ 思考: "用户要仙侠风文生图，我来构造提示词"
→ 调用 generate_image(
    prompt="masterpiece, xianxia style, lone swordsman under moonlight,
            flowing white robes, ancient bamboo forest, ethereal mist",
    style="xianxia"
  )
→ ComfyUI GPU 执行 xianxia_basic 工作流
→ 返回真实生成的仙侠月下剑客图片
→ 回复: "已生成月下剑客图片，需要调整构图或风格吗？"
```

### 6.2 多轮能力变化

**改造前：**
```
用户: 画一张仙侠剑客
Agent: (返回随机图)
用户: 把背景改成夜晚
Agent: (不知道"背景"和"夜晚"是什么关系，又返回随机图)
```

**改造后：**
```
用户: 画一张仙侠剑客
Agent: [调用 generate_image] → 返回真实图片 (image_001.jpg)
用户: 把背景改成夜晚
Agent: (看到历史中 image_001.jpg)
       [调用 edit_image(image="image_001.jpg", instruction="将背景改为夜晚月色")]
       → 返回编辑后的图片
用户: 让这张图动起来
Agent: [调用 image_to_video(image="image_001_edited.jpg", motion="gentle wind")]
       → 返回视频
```

### 6.3 模型切换能力

```
用户选了 claude-sonnet-4-6   → Claude 作为大脑，调度 ComfyUI 工具
用户切换 gpt-5.4             → GPT 作为大脑，调度同样的 ComfyUI 工具
用户切换 gemini-3.1-pro-high → Gemini 作为大脑，调度同样的 ComfyUI 工具
用户切换 Qwen3-32B (南格)    → Qwen 作为大脑，南格 HMAC 签名认证

工具不变，工作流不变，只有大脑换了。
```

---

## 七、三种运行模式共存

改造后系统支持三种模式，用户可在前端切换：

```
┌─────────────────────────────────────────────────────┐
│              前端模式选择                              │
│                                                      │
│  ○ Mock 模式    → mock_agent.py    → picsum 占位图   │
│  ○ Smart 模式   → smart_agent.py   → 关键词+占位图   │
│  ● Agent 模式   → agent_runner.py  → LLM+ComfyUI    │
│    └─ 选择模型: [claude-sonnet-4-6 ▾]               │
│                                                      │
└─────────────────────────────────────────────────────┘
```

后端路由根据有无 model 参数自动分发：
```python
if model_id and model_id != "mock":
    # Agent 模式：用户选的模型驱动
    await agent_runner.run(...)
else:
    # Mock/Smart 模式：关键词分发
    async for event in smart_agent_stream(...):
        ...
```

---

## 八、执行计划

```
Step 1: 新增 OpenAI 兼容 LLM 客户端          (~120 行)
────────────────────────────────────────
创建 openai_client.py
- 支持 AIPro（OpenAI 兼容接口）
- 支持 tool_use / function_calling
- 支持流式输出
- 自动从 model_config 表获取配置

Step 2: 新增工具执行器                        (~180 行)
────────────────────────────────────────
创建 tool_executor.py
- 8 个工具执行函数
- 每个函数封装 ComicAgent 对应方法
- 统一输入/输出格式
- 图片结果保存到 uploads/ 并返回 URL

Step 3: 新增 Agent Runner                     (~250 行)
────────────────────────────────────────
创建 agent_runner.py
- ReAct 循环
- System Prompt
- 对话历史管理
- thinking 事件推送
- 错误处理 + 重试

Step 4: 修改 WebSocket 入口                   (~30 行)
────────────────────────────────────────
修改 comic_agent.py
- 接收 model 参数
- 查 DB 获取模型配置
- 分发到 agent_runner 或 smart_agent

Step 5: 验证测试
────────────────────────────────────────
- 选 claude-sonnet-4-6 → 发送生成指令 → 验证真实图片
- 多轮对话 → 验证上下文保持
- 切换模型 → 验证不同模型都能驱动
```

---

## 九、总结

### 误诊纠正

之前说"系统缺少大脑"是不准确的。**大脑（21 个 LLM 模型）已经在数据库里了，前端也让用户选了。** 问题是：

> **大脑和身体之间的四条神经被切断了：**
> 1. 前端传了 model，后端没读
> 2. 意图识别没调 LLM，用的关键词
> 3. 工具执行没调 ComfyUI，用的占位图
> 4. 没传对话历史，每轮独立

### 修复方案

**不是造新器官，而是接通神经。** 所有零部件已就位：

| 已有零部件 | 说明 |
|-----------|------|
| 大脑 | 21 个 LLM 模型（Claude/GPT/Gemini/Qwen） |
| 手脚 | ComfyUI 40+ 工作流 + ComicAgent 5 个方法 |
| 感官 | WebSocket + 前端 UI + 事件协议 |
| 记忆 | MySQL 消息持久化 |

**只需新增 ~550 行代码（3 个文件），修改 ~95 行（3 个文件），前端零改动。**

```
改造后效果：
用户选了 Claude Sonnet → Claude 分析你说的话 → 自主决定调什么工具
→ ComfyUI GPU 真实生成图片 → 返回给你 → 你说"改一下" → Claude 记得之前的图
→ 调编辑工具修改 → 你说"动起来" → Claude 调视频工具 → 完整的多轮创作体验
```
