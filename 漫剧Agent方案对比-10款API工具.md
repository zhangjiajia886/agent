# 漫剧 Agent 方案对比：10 款可对接 API 的主流工具

> 基于当前 ttsapp 项目 ComfyUI + Agent 架构，对比可替代或互补的 10 款工具
> 评估维度：API 可用性、漫剧适配度、角色一致性、成本、Agent 集成难度

---

## 一、当前架构回顾

```
用户输入故事 → Agent(LLM) 拆解分镜 → 逐帧调用 ComfyUI 工作流 → 生成图片/视频 → 拼合漫剧
```

**痛点**：
- ComfyUI 工作流 JSON 维护成本高（widget_values 错位、节点版本不兼容）
- 依赖远程 GPU 服务器，需自建运维
- 角色一致性依赖 LoRA/IPAdapter 等特定节点，调参复杂

---

## 二、10 款工具横向对比

| # | 工具 | API 状态 | 漫画适配 | 角色一致性 | 单图成本 | Agent 集成难度 | 延迟 |
|---|------|---------|---------|-----------|---------|--------------|------|
| 1 | **ComfyUI** (自建) | ✅ 本地 REST | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ (IPAdapter/LoRA) | GPU 租赁费 | 🔴 高 | 5-60s |
| 2 | **OpenAI GPT-Image** | ✅ 官方 API | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (对话上下文) | $0.02-0.08/张 | 🟢 极低 | 5-15s |
| 3 | **FLUX (fal.ai)** | ✅ 官方 API | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Kontext/Redux) | $0.01-0.05/张 | 🟢 低 | 2-8s |
| 4 | **Midjourney** | ⚠️ 非官方 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ (--sref/--cref) | $0.02-0.04/张 | 🟡 中 | 10-60s |
| 5 | **Stability AI (SD3.5)** | ✅ 官方 API | ⭐⭐⭐⭐ | ⭐⭐⭐ | $0.03-0.065/张 | 🟢 低 | 3-10s |
| 6 | **Leonardo.AI** | ✅ 官方 API | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Character Ref) | $0.01-0.04/张 | 🟢 低 | 3-10s |
| 7 | **Ideogram 3.0** | ✅ 官方 API | ⭐⭐⭐ | ⭐⭐⭐ | $0.02-0.08/张 | 🟢 低 | 5-15s |
| 8 | **即梦/可灵 (Jimeng/Kling)** | ✅ 官方 API | ⭐⭐⭐⭐ | ⭐⭐⭐ | ¥0.04-0.2/张 | 🟢 低 | 3-15s |
| 9 | **硅基流动 (SiliconFlow)** | ✅ 聚合 API | ⭐⭐⭐⭐ | ⭐⭐⭐ (依赖底层模型) | ¥0.01-0.06/张 | 🟢 低 | 2-10s |
| 10 | **Replicate** | ✅ 官方 API | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (多模型组合) | $0.01-0.10/张 | 🟢 低 | 3-30s |

---

## 三、逐款详细分析

### 1. ComfyUI（当前方案）

**定位**：节点式 AI 图像/视频生成引擎，全面可控

| 项目 | 详情 |
|------|------|
| API | `POST /prompt` 本地 REST，无官方云 API |
| 漫剧能力 | 文生图/图生图/图生视频/局部重绘/放大 全链路覆盖 |
| 角色一致性 | IPAdapter + LoRA + InstantID + Pulid，效果最好但配置复杂 |
| 成本 | AutoDL RTX5090 ≈ ¥3.5/h，无 per-image 费 |
| 优势 | 完全可控、可离线、工作流可视化、社区节点丰富 |
| 劣势 | 维护成本高、JSON 脆弱、需运维 GPU 服务器 |
| Agent 集成 | 已完成（当前架构），但工作流注册/参数注入逻辑复杂 |

**适合**：需要极致控制和批量生产的专业漫剧流水线

---

### 2. OpenAI GPT-Image（gpt-image-1 / gpt-image-2）⭐ 推荐

**定位**：GPT-4o 原生图像生成，对话式创作

| 项目 | 详情 |
|------|------|
| API | `POST /v1/images/generations` model=`gpt-image-1`（或 `dall-e-3`） |
| 漫剧能力 | 文生图 + 图片编辑 + 对话迭代修改，天然支持漫画面板 |
| 角色一致性 | ⭐ **最强**：利用对话上下文 + 图片输入保持一致性，无需额外配置 |
| 成本 | 1024x1024 标准 $0.04/张，HD $0.08/张；gpt-image-2 更便宜 |
| 优势 | **零配置角色一致性**（同一对话自动保持角色外观）、文字渲染极好、API 极简 |
| 劣势 | 不能训练 LoRA、风格可控性弱于 ComfyUI、有内容审核限制 |

```python
# Agent 集成示例 — 极简
response = openai.images.generate(
    model="gpt-image-1",
    prompt="漫画风格，第3格：少年拔剑而起，背景是燃烧的山门，分镜构图左低右高",
    size="1024x1536",
    quality="hd"
)
```

**集成方案**：直接在 Agent tool_executor 中新增 `openai_image_gen` 工具，3 行核心代码即可集成。**最适合快速实现漫剧 Agent 的方案**。

---

### 3. FLUX（via fal.ai / Replicate / SiliconFlow）⭐ 推荐

**定位**：Black Forest Labs 开源旗舰模型，速度+质量平衡

| 项目 | 详情 |
|------|------|
| API | fal.ai: `fal.ai/models/flux`；Replicate: `black-forest-labs/flux`；SiliconFlow 也有 |
| 漫剧能力 | FLUX.1 Pro/Dev 文生图 + Kontext（角色一致性编辑）+ Redux（风格迁移） |
| 角色一致性 | **Kontext 模型**：输入参考图 → 保持角色生成新场景，效果接近 IPAdapter |
| 成本 | fal.ai: FLUX Pro $0.05/张，Dev $0.025/张；SiliconFlow 更便宜 ¥0.01起 |
| 优势 | 速度快（fal.ai 2-5s）、开源可自建、Kontext 角色一致性优秀 |
| 劣势 | 不如 GPT-Image 的对话式一致性，需要自己管理参考图 |

```python
# FLUX Kontext 角色一致性示例
result = fal_client.run("fal-ai/flux-pro/kontext", arguments={
    "prompt": "same character, now in a bamboo forest at night, martial arts pose",
    "image_url": "https://xxx/character_ref.png",  # 参考图
    "aspect_ratio": "9:16"
})
```

**集成方案**：新增 `flux_image_gen` 工具，支持 text2img 和 kontext(角色一致性) 两种模式。

---

### 4. Midjourney

**定位**：最高画质 AI 绘画，但 API 受限

| 项目 | 详情 |
|------|------|
| API | ⚠️ 无官方 API！需通过第三方代理（GoAPI、ImagineAPI 等），稳定性不保证 |
| 漫剧能力 | V7 画质顶级，`--style` 支持多种漫画风格 |
| 角色一致性 | `--cref`（角色参考）+ `--sref`（风格参考），效果好但不如 GPT/Kontext 精准 |
| 成本 | 官方 $10-60/月订阅；第三方 API 约 $0.02-0.04/张 |
| 优势 | 画质天花板、社区风格丰富 |
| 劣势 | **无官方 API 是硬伤**、第三方代理不稳定、不可自建、速度慢 |

**集成方案**：不推荐作为主力。可作为"高画质模式"的可选工具，通过 GoAPI 等代理接入。

---

### 5. Stability AI（Stable Diffusion 3.5 / SDXL API）

**定位**：开源图像生成鼻祖的官方 API 服务

| 项目 | 详情 |
|------|------|
| API | `api.stability.ai`，支持 SD3.5、SDXL、图片编辑、放大等 |
| 漫剧能力 | 文生图 + ControlNet + img2img + inpaint |
| 角色一致性 | API 层面较弱，需配合 ControlNet/img2img 手动管理 |
| 成本 | SD3.5 Medium $0.035/张，Large $0.065/张 |
| 优势 | 官方稳定、支持 ControlNet、可结合自建 ComfyUI 使用 |
| 劣势 | API 功能不如 ComfyUI 灵活、角色一致性需自己实现 |

**集成方案**：适合作为 ComfyUI 的云端备选，不适合替代主方案。

---

### 6. Leonardo.AI

**定位**：专业 AI 创作平台，有多个微调模型

| 项目 | 详情 |
|------|------|
| API | `cloud.leonardo.ai/api/rest/v1`，RESTful，文档完善 |
| 漫剧能力 | 多个漫画/动漫微调模型（Anime Pastel Dream、DreamShaper 等） |
| 角色一致性 | Character Reference 功能（上传参考图保持角色） |
| 成本 | 按 token 计费，约 $0.01-0.04/张 |
| 优势 | 开箱即用的动漫风格模型、Character Reference、API 文档好 |
| 劣势 | Token 体系复杂、生态不如 FLUX 开放 |

**集成方案**：新增 `leonardo_image_gen` 工具，特别适合动漫风格漫剧。

---

### 7. Ideogram 3.0

**定位**：文字渲染之王

| 项目 | 详情 |
|------|------|
| API | `api.ideogram.ai`，也可通过 Together AI / fal.ai 调用 |
| 漫剧能力 | 文字渲染极强（对话气泡、标题、拟声词），适合漫画中的文字元素 |
| 角色一致性 | 一般，无专门的角色一致性功能 |
| 成本 | Standard $0.02/张，Premium $0.08/张 |
| 优势 | **文字渲染最佳**（对话气泡直接生成在画面中） |
| 劣势 | 角色一致性弱、不擅长连续叙事 |

**集成方案**：作为"气泡/文字叠加"的补充工具，不适合作为主力。

---

### 8. 即梦 / 可灵（Jimeng / Kling）

**定位**：字节跳动旗下，国内生态友好

| 项目 | 详情 |
|------|------|
| API | 即梦 API（`jimeng.jianying.com`）+ 可灵 API（`klingai.com`），兼容 OpenAI 格式 |
| 漫剧能力 | 文生图 + 图生视频 + 视频生成，即梦 4.0 画质优秀 |
| 角色一致性 | 基础的参考图功能，不如 GPT/Kontext 成熟 |
| 成本 | 官方每日 66 免费积分，API ¥0.04-0.2/张 |
| 优势 | **国内网络无障碍**、中文理解好、视频生成能力强（可灵） |
| 劣势 | API 生态不够成熟、文档不如国际产品完善 |

```python
# 即梦 API 兼容 OpenAI 格式
response = openai.images.generate(
    model="jimeng_s2i_high_aes_l20",
    prompt="仙侠漫画风格，少年负剑站在悬崖边",
    base_url="https://jimeng-api-endpoint/v1"
)
```

**集成方案**：国内部署首选，特别是配合可灵做图生视频环节。

---

### 9. 硅基流动（SiliconFlow）

**定位**：国内 AI 模型 API 聚合平台

| 项目 | 详情 |
|------|------|
| API | `api.siliconflow.cn`，聚合 FLUX、SD3.5、Kolors 等多模型 |
| 漫剧能力 | 取决于底层模型，FLUX Pro 和 Kolors 表现好 |
| 角色一致性 | 依赖底层模型的能力 |
| 成本 | **极低**：FLUX.1 Dev ¥0.01/张，Schnell 甚至免费 |
| 优势 | **国内最便宜**、一个 API key 调多个模型、延迟低 |
| 劣势 | 上层封装，灵活性不如直接调用 |

**集成方案**：作为 FLUX/SD 的国内加速通道，特别适合批量生产降低成本。

---

### 10. Replicate

**定位**：AI 模型 Marketplace，按需调用

| 项目 | 详情 |
|------|------|
| API | `api.replicate.com`，支持 FLUX/SD/SDXL 及大量社区微调模型 |
| 漫剧能力 | 丰富的漫画 LoRA 模型（如 `flux-manga`、`anime-style` 等） |
| 角色一致性 | 可用 Pulid-FLUX、IPAdapter 等社区模型组合 |
| 成本 | 按 GPU 秒计费，FLUX Dev 约 $0.01/张，Pro 约 $0.05/张 |
| 优势 | 模型选择最多、社区微调模型丰富、API 设计优秀 |
| 劣势 | 冷启动慢（首次可能 30s+）、大量使用成本累积快 |

**集成方案**：适合做"多风格漫画"选择器，Agent 根据用户选择的风格选不同模型。

---

## 四、推荐方案矩阵

### 方案 A：快速落地（1-2 天）⭐⭐⭐⭐⭐

```
Agent → OpenAI GPT-Image API → 生成分镜图片 → TTS 配音 → 输出漫剧
```

| 项 | 详情 |
|----|------|
| 核心工具 | GPT-Image-1（gpt-image-1） |
| 角色一致性 | 利用对话上下文自动保持（零配置） |
| 开发量 | 新增 1 个 tool（`openai_image_gen`），约 50 行代码 |
| 成本 | 4 格漫画 ≈ $0.16-0.32 |
| 适合 | 快速验证、对画质要求中等、最低开发成本 |

### 方案 B：高性价比（2-3 天）⭐⭐⭐⭐

```
Agent → FLUX Kontext (fal.ai) → 角色一致性分镜 → TTS → 漫剧
       ↘ 硅基流动 (备选/降本)
```

| 项 | 详情 |
|----|------|
| 核心工具 | FLUX Pro + Kontext（fal.ai 或硅基流动） |
| 角色一致性 | Kontext 参考图模式 |
| 开发量 | 新增 1 个 tool + 参考图管理逻辑 |
| 成本 | 4 格漫画 ≈ $0.04-0.20（硅基流动更低至 ¥0.04） |
| 适合 | 对成本敏感、批量生产、需要开源可控 |

### 方案 C：混合架构（当前 + 云 API）⭐⭐⭐⭐

```
Agent → 简单需求: GPT-Image / FLUX API（快速出图）
       → 复杂需求: ComfyUI（精细控制、特殊工作流）
       → 视频需求: 可灵 API / ComfyUI Wan
```

| 项 | 详情 |
|----|------|
| 核心工具 | GPT-Image + FLUX + ComfyUI + 可灵 |
| 角色一致性 | GPT 对话上下文 + FLUX Kontext + ComfyUI IPAdapter |
| 开发量 | 新增 2-3 个 tool + 路由逻辑 |
| 成本 | 按需混合，平均 ¥0.1-0.5/格 |
| 适合 | 当前项目的最佳演进路径 |

### 方案 D：国内纯云方案 ⭐⭐⭐

```
Agent → 即梦 API (文生图) → 可灵 API (图生视频) → TTS → 漫剧
       ↘ 硅基流动 FLUX (备选)
```

| 项 | 详情 |
|----|------|
| 核心工具 | 即梦 + 可灵 + 硅基流动 |
| 角色一致性 | 即梦参考图 + prompt 描述 |
| 开发量 | 新增 2 个 tool |
| 成本 | 全中文生态，免翻墙 |
| 适合 | 纯国内部署、中文漫剧、对网络环境有要求 |

---

## 五、实施建议

### 推荐优先级

1. **立刻做**：方案 A（GPT-Image），1-2 天内即可让 Agent 通过纯 API 生成漫剧，无需 ComfyUI
2. **短期做**：方案 C（混合架构），在 A 基础上保留 ComfyUI 做高质量/复杂工作流
3. **可选做**：接入硅基流动/即梦 作为国内低成本通道

### Agent 工具注册建议

```python
# 新增 3 个图像生成工具，与现有 ComfyUI 工具并存
SEED_TOOLS_NEW = [
    {
        "name": "openai_image_gen",
        "description": "使用 OpenAI GPT-Image 生成漫画图片，支持对话式角色一致性",
        "parameters": {
            "prompt": "图片描述（含角色、场景、构图、风格）",
            "size": "尺寸 1024x1024 | 1024x1536 | 1536x1024",
            "quality": "standard | hd",
            "reference_image": "可选，参考图片路径"
        }
    },
    {
        "name": "flux_image_gen",
        "description": "使用 FLUX 模型快速生成图片，支持 Kontext 角色一致性",
        "parameters": {
            "prompt": "图片描述",
            "mode": "text2img | kontext",
            "reference_image": "Kontext 模式的参考图",
            "aspect_ratio": "宽高比"
        }
    },
    {
        "name": "jimeng_image_gen",
        "description": "使用即梦 AI 生成图片（国内加速，中文优化）",
        "parameters": {
            "prompt": "图片描述",
            "model": "即梦模型版本",
            "reference_image": "可选参考图"
        }
    }
]
```

---

## 六、关键结论

| 维度 | 最优选择 |
|------|---------|
| **最快集成** | OpenAI GPT-Image（API 最简，角色一致性零配置） |
| **最高画质** | Midjourney V7（但无官方 API，不推荐） |
| **最便宜** | 硅基流动 FLUX Schnell（¥0.01/张起） |
| **最强角色一致性** | GPT-Image（对话上下文） > FLUX Kontext > ComfyUI IPAdapter |
| **最佳文字渲染** | Ideogram 3.0 / GPT-Image |
| **国内最优** | 即梦 + 可灵 + 硅基流动 |
| **最灵活可控** | ComfyUI（当前方案） |
| **综合最优** | 混合方案 C：GPT-Image(快) + ComfyUI(精) + 可灵(视频) |
