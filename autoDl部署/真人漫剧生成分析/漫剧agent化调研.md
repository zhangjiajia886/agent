# 漫剧 Agent 化调研报告

> 基于 Chao-comfyui 漫剧专用镜像 + ComfyUI API 实测
> 更新日期：2026-04-28

---

## 一、镜像概述

**镜像名称**：Chao-comfyui-漫剧专用镜像-LTX2.3适配字字动画  
**访问地址**：`https://u982127-7772b8fbe6d9.bjb2.seetacloud.com:8443/`  
**工作流文档**：[夸克网盘](https://pan.quark.cn/s/be71c1c1f30b)

### 核心特点

- 完全本地运行，**无需任何第三方接口/API Key**（回答问题2）
- ComfyUI 4.0 版本，所有模型已预置，开机即用
- 通过 ComfyUI `/prompt` API 可直接 Agent 化，无需人工操作界面

---

## 二、内置模型完整清单（已通过 API 实测）

### 2.1 图像生成模型

| 模型 | 文件名 | 特点 | 速度 |
|---|---|---|---|
| **Z-Image BF16** | `z_image_bf16.safetensors` | 开源最强真人图像 | ~5s/张 |
| **Z-Image Turbo** | `z_image_turbo_bf16.safetensors` | 加速版，质量略降 | ~2s/张 |
| **Qwen Image 2512** | `qwen_image_2512_bf16.safetensors` | Qwen最新版图像生成 | ~5s/张 |
| **DreamshaperXL** | `dreamshaperXL_lightningDPMSDE.safetensors` | 仙侠/动漫风格基础 | ~4s/张 |
| **FLUX1 dev** | `flux1-dev-fp8.safetensors` | 最高写实质量 | ~15s/张 |

### 2.2 图像编辑模型

| 模型 | 文件名 | 能力 |
|---|---|---|
| **Qwen Image Edit** | `qwen_image_edit_2511_fp8mixed.safetensors` | 指令式编辑（中英文指令） |
| **Qwen Image Edit Lightning** | `qwen_image_edit_2511_fp8_e4m3fn_scaled_lightning.safetensors` | 4步快速编辑 |
| **Klein 4B** | `flux-2-klein-4b.safetensors` | 多图参考编辑，提示词遵从度最强 |
| **Klein 9B** | `flux-2-klein-9b.safetensors` | 更强质量的多图参考编辑 |

### 2.3 视频生成模型

| 模型 | 文件名 | 类型 |
|---|---|---|
| **Wan 2.1 I2V 480P** | `Wan2.1/wan2.1_i2v_480p_14B_fp8_scaled.safetensors` | 图生视频 14B |
| **Wan 2.1 I2V 720P** | `Wan2.1/wan2.1_i2v_720p_14B_fp8_scaled.safetensors` | 图生视频 720P |
| **Wan 2.2 I2V 高噪** | `Wan2.2/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | 更强运动幅度 |
| **Wan 2.2 I2V 低噪** | `Wan2.2/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | 更稳定的运动 |
| **LTX 2.3 22B** | `ltx-2.3-22b-dev-fp8.safetensors` | 目前最长/最高质量视频 |
| **LTX 2.0 19B** | `ltx-2-19b-distilled-fp8.safetensors` | 快速蒸馏版 |

### 2.4 人脸保持模型

| 模型 | 文件名 | 架构 |
|---|---|---|
| **InstantID SDXL** | `ip-adapter_instant_id_sdxl.bin` | SDXL + InstantID |
| **InstantID ControlNet** | `control_instant_id_sdxl.safetensors` | 配套 ControlNet |
| **PuLID FLUX** | `NunchakuPulidLoader` 节点 | FLUX + PuLID，效果更强 |

---

## 三、工作流 Skill 清单（Agent 化设计）

### 3.0 服务器能力全图 vs Agent 已集成（实测：共 71 个工作流）

> **说明**：ComfyUI 服务器共有 71 个工作流，分 13 大类。ttsapp Agent 目前集成了其中 8 个核心能力（JSON 文件在 `/backend/app/core/comic_agent/workflows/`）。剩余能力可按需扩展。

| 服务器分类 | 工作流数 | 核心功能 | Agent 已集成 | 已集成的文件名 |
|---|---|---|---|---|
| **Z-Image 系列** | 4 | 真人写实文生图（Lumina2 模型）| ✅ | `z_image_t2i.json` |
| **QwenImage 系列** | 6 | 指令式图像编辑、材质替换、文生图 | ✅ | `qwen_edit.json` |
| **Wan 视频系列** | 7 | I2V/T2V/首尾帧/音频驱动视频 | ✅（I2V） | `wan_i2v.json` |
| **SD 系列** | 9 | 仙侠/水墨/动漫/盲盒文生图 + InstantID 人脸保持 | ✅ | `xianxia_basic/blindbox_q/moxin_ink/anime_basic/xianxia_instantid.json` |
| **Flux2/Klein 系列** | 13 | Flux2 高质量图像编辑、外扩、局部清除、图参考 | ❌ 待扩展 | — |
| **双截棍-RTX5090** | 10 | 上述工作流的 fp4/量化版本（生成速度更快）| ❌ 待扩展 | — |
| **双截棍-非RTX5090** | 10 | 适配非5090显卡的 int4 版本 | ❌ 待扩展 | — |
| **LTX2 视频系列** | 4 | 高质量长视频（T2V/I2V/图+音频）| ❌ 待扩展 | — |
| **HiDream 图像** | 2 | HiDream 文生图+编辑 | ❌ 待扩展 | — |
| **其他图像** | 3 | SeedVR2 超分、LBM 光源统一、图生图 | ❌ 待扩展 | — |
| **Wan-KJ 视频** | 1 | Wan 2.1 KJ 优化版视频 | ❌ 待扩展 | — |
| **语音生成** | 1 | 音频分离（人声/背景音）| ❌ 待扩展 | — |
| **其他** | 1 | WAN 2.2 动漫特供 | ❌ 待扩展 | — |

**已集成 8 个 vs 待扩展 63 个**——重点方向：Flux2 编辑（高质量）、双截棍加速版（极速）、Wan T2V（文生视频）、LTX2（长视频）

---

### 3.1 镜像内置工作流完整清单（API 实测，71 个）

**Z-Image 系列（真人图像）**
| 文件名 | 用途 | Agent Skill ID |
|---|---|---|
| `Z-Image-Base文生图.json` | 真人写实文生图 | `skill_z_image_t2i` |
| `Z-Image-Base文生图-fp4版.json` | RTX 5090 加速版 | `skill_z_image_t2i_fast` |
| `Z-Image-Turbo文生图.json` | 极速版（2s/张） | `skill_z_image_turbo` |
| `Z-Image-Turbo-ControlNet控制.json` | ControlNet 姿态控制 | `skill_z_image_ctrl` |

**QwenImage 系列（图像编辑）**
| 文件名 | 用途 | Agent Skill ID |
|---|---|---|
| `Qwen-Imag-Eedit-2509图像编辑.json` | 指令式图像编辑 | `skill_qwen_edit` |
| `Qwen-Image-Edit2511-材质替换.json` | 材质/风格替换专用 | `skill_qwen_material` |
| `Qwen-Image-2512文生图-4步.json` | Qwen 2512 文生图 | `skill_qwen_t2i` |
| `Qwen-Image-Layered图层分解.json` | 图层分解（特效） | `skill_qwen_layer` |

**Flux2 / Klein 系列（高质量编辑）**
| 文件名 | 用途 | Agent Skill ID |
|---|---|---|
| `Flux2-Klein-4B-图像编辑.json` | Klein 4B 图像编辑 | `skill_klein_edit_4b` |
| `Flux2-Klein-9B-图像编辑.json` | Klein 9B 高质量编辑 | `skill_klein_edit_9b` |
| `Flux2-Klein-9B-文生图.json` | Klein 9B 文生图 | `skill_klein_t2i` |
| `Flux2图像编辑.json` | Flux2 标准编辑 | `skill_flux2_edit` |
| `Flux-redux图参考.json` | 图像参考合成 | `skill_flux_redux` |
| `Flux-fill扩图.json` | 画面外扩 | `skill_flux_outpaint` |
| `Flux-fill-画面局部清除.json` | 局部清除/去除 | `skill_flux_inpaint` |

**Wan 视频系列（图生视频）**
| 文件名 | 用途 | Agent Skill ID |
|---|---|---|
| `Wan2.2-14B图生视频_4步.json` | **核心 I2V 工作流** | `skill_wan22_i2v` |
| `Wan2.2首尾帧视频_4步.json` | 首帧+尾帧控制视频 | `skill_wan22_keyframe` |
| `Wan2.2-14B文生视频-4步.json` | 文字直接生视频 | `skill_wan22_t2v` |
| `Wan2.2Animate-角色动画与替换.json` | 角色动画替换 | `skill_wan22_animate` |
| `Wan2.2-S2V音频驱动视频生成.json` | **音频驱动动态** | `skill_wan22_s2v` |
| `Wan2.2-14B-Fun控制版.json` | ControlNet 控制视频 | `skill_wan22_ctrl` |

**LTX2 视频系列（高质量/长视频）**
| 文件名 | 用途 | Agent Skill ID |
|---|---|---|
| `LTX2图生视频.json` | LTX 2.3 图生视频 | `skill_ltx2_i2v` |
| `LTX2-文生视频.json` | LTX 2.3 文生视频 | `skill_ltx2_t2v` |
| `LTX-2图像加音频到视频v3.json` | 图像+音频生视频 | `skill_ltx2_audio` |

**SD 系列（人脸保持/经典）**
| 文件名 | 用途 | Agent Skill ID |
|---|---|---|
| `SDXL-InstantID面部一致.json` | InstantID 人脸保持 | `skill_instantid` |
| `SDXL-IPA-FaceID+ControlNet.json` | FaceID + 姿态控制 | `skill_faceid_ctrl` |

**其他**
| 文件名 | 用途 | Agent Skill ID |
|---|---|---|
| `SeedVR2_简单图像高清放大.json` | **SeedVR2 图像超分** | `skill_seedvr2_upscale` |
| `LBM-Repaint-光源统一.json` | 光源统一重绘 | `skill_lbm_relight` |
| `HiDream_E1.1-图像编辑.json` | HiDream 图像编辑 | `skill_hidream_edit` |
| `音频分离.json` | 人声/背景音分离 | `skill_audio_sep` |

### 3.2 工作流 Skill 优先实现（含节点链路）

#### P0 - Skill 1：Z-Image 文生图（✅ JSON 已生成）
```
节点链路: UNETLoader(z_image_bf16) → ModelSamplingAuraFlow(shift=3)
         CLIPLoader(qwen_3_4b, lumina2) → CLIPTextEncode
         VAELoader(ae.safetensors) → EmptySD3LatentImage(1024x1024)
         KSampler(steps=25, cfg=4, res_multistep) → VAEDecode → SaveImage
工作流文件: z_image_t2i.json
```

#### P0 - Skill 2：Qwen 图像编辑（✅ JSON 已生成）
```
节点链路: UNETLoader(qwen_image_edit_2509_fp8) → LoraLoaderModelOnly(Lightning 4步)
         CFGNorm(strength=1) → ModelSamplingAuraFlow(shift=3)
         CLIPLoader(qwen_2.5_vl_7b_fp8, qwen_image) + VAELoader(qwen_image_vae)
         TextEncodeQwenImageEditPlus(image1=原图, prompt=指令)
         EmptySD3LatentImage(1024x1024) → KSampler(steps=4, cfg=1) → VAEDecode → SaveImage
工作流文件: qwen_edit.json
```

#### P0 - Skill 3：Wan 2.2 I2V（✅ JSON 已重写）
```
节点链路: UNETLoader(wan2.2_i2v_high_noise_14B_fp8) → ModelSamplingSD3(shift=8)
         UNETLoader(wan2.2_i2v_low_noise_14B_fp8) → ModelSamplingSD3(shift=8)
         CLIPLoader(umt5_xxl_fp8, wan) → CLIPTextEncode x2
         VAELoader(wan_2.1_vae) + LoadImage
         WanImageToVideo(640x640, 81帧)
         KSamplerAdvanced(enable, steps=20, cfg=3.5, euler) [高噪前10步]
         KSamplerAdvanced(disable, steps=20, cfg=3.5, euler) [低噪后10步]
         VAEDecode → VHS_VideoCombine(16fps, h264-mp4)
工作流文件: wan_i2v.json（已修正）
```

#### P1 - Skill 4：InstantID 人脸保持（✅ JSON 已有）
```
节点链路: CheckpointLoaderSimple → InstantIDModelLoader + InstantIDFaceAnalysis
         ControlNetLoader → ApplyInstantID
         CLIPTextEncode x2 → EmptyLatentImage → KSampler → VAEDecode → SaveImage
工作流文件: xianxia_instantid.json
```

---

## 四、移植到已有 Agent 项目

### 4.1 现有 Agent 代码结构（ttsapp）

```
backend/app/core/comic_agent/
├── agent.py              ← ComicAgent 主类（generate 方法）
├── intent_parser.py      ← LLM 解析意图（style/need_face/mood 等）
├── story_planner.py      ← 分镜规划
├── prompt_builder.py     ← 提示词生成
├── workflow_selector.py  ← 工作流选择 + inject_params 参数注入
└── workflows/
    ├── xianxia_basic.json      ✅ 已有
    ├── anime_basic.json        ✅ 已有
    ├── blindbox_q.json         ✅ 已有
    ├── moxin_ink.json          ✅ 已有
    ├── xianxia_instantid.json  ✅ 已有（InstantID 人脸保持）
    ├── wan_i2v.json            ✅ 已修正（Wan 2.2 双路采样）← 新
    ├── z_image_t2i.json        ✅ 已生成（Z-Image 文生图）← 新
    └── qwen_edit.json          ✅ 已生成（Qwen Edit 4步）← 新
```

### 4.2 三个新工作流文件（审核通过后复制）

| 文件 | 用途 | 复制到目标 agent 的位置 |
|---|---|---|
| `workflows/z_image_t2i.json` | 真人文生图 | `{your_agent}/workflows/z_image_t2i.json` |
| `workflows/qwen_edit.json` | 图像指令编辑 | `{your_agent}/workflows/qwen_edit.json` |
| `workflows/wan_i2v.json` | 图生视频 | `{your_agent}/workflows/wan_i2v.json` |

> 三个文件只依赖 ComfyUI API（`/upload/image` + `/prompt` + `/history`），无其他依赖。

### 4.3 workflow_selector.py 需要的修改

复制文件后，目标 agent 的 `workflow_selector.py` 中需要：

**① 扩展 WORKFLOW_MAP**
```python
WORKFLOW_MAP = {
    # 原有
    ("xianxia",   False): "xianxia_basic",
    ("xianxia",   True):  "xianxia_instantid",
    # 新增
    ("realistic", False): "z_image_t2i",     # Z-Image 真人写实
    ("realistic", True):  "xianxia_instantid",
}
```

**② 扩展 inject_params（支持新节点类型）**

新工作流使用了以下新节点，现有 inject_params 未覆盖：

| 节点 class_type | 需要注入的参数 | 对应字段 |
|---|---|---|
| `KSamplerAdvanced` | `noise_seed`（当 `add_noise=enable`） | seed |
| `EmptySD3LatentImage` | `width`, `height` | 图像尺寸 |
| `TextEncodeQwenImageEditPlus` | `prompt` → 编辑指令; `image1` → 原图文件名 | instruction + edit_image |
| `LoadImage` | `image` → 文件名 | source_image / edit_image |
| `WanImageToVideo` | `width`, `height`, `num_frames` | 视频尺寸帧数 |

**完整扩展代码**（在现有 inject_params 内追加以下 elif 分支）：

```python
elif ct == "KSamplerAdvanced":
    if inputs.get("add_noise") == "enable":
        inputs["noise_seed"] = seed

elif ct == "EmptySD3LatentImage":
    if width:
        inputs["width"] = width
    if height:
        inputs["height"] = height

elif ct == "TextEncodeQwenImageEditPlus":
    if kwargs.get("instruction"):
        inputs["prompt"] = kwargs["instruction"]
    # image1 保持连线引用 ["load_img_node_id", 0]，不覆盖
    # 实际图片通过 LoadImage 节点加载（由 LoadImage 的 image 字段注入文件名）

elif ct == "LoadImage":
    img = kwargs.get("source_image") or kwargs.get("edit_image") or kwargs.get("face_image")
    if img:
        inputs["image"] = img

elif ct == "WanImageToVideo":
    if kwargs.get("source_image"):
        # start_image 是 LATENT 连线，不直接修改；图片由 LoadImage 节点提供
        pass
    if width:
        inputs["width"] = width
    if height:
        inputs["height"] = height
```

### 4.4 agent.py 需要新增的两个方法

**编辑方法（接 qwen_edit.json）**
```python
async def edit_image(self, source_image: bytes, instruction: str, seed: int = -1) -> ComicResult:
    result = ComicResult()
    seed = seed if seed != -1 else random.randint(0, 2**31)
    filename = await self.comfyui.upload_image(source_image, "edit_source.jpg")
    workflow = load_workflow("qwen_edit")
    workflow = inject_params(
        workflow, positive_prompt="", negative_prompt="", seed=seed,
        instruction=instruction, edit_image=filename,
    )
    frame_bytes = await self.comfyui.run_workflow(workflow)
    result.frames = [frame_bytes]
    return result
```

**动态化方法（接 wan_i2v.json）**
```python
async def animate_image(self, source_image: bytes, motion_prompt: str, seed: int = -1) -> ComicResult:
    result = ComicResult()
    seed = seed if seed != -1 else random.randint(0, 2**31)
    filename = await self.comfyui.upload_image(source_image, "animate_source.jpg")
    workflow = load_workflow("wan_i2v")
    workflow = inject_params(
        workflow, positive_prompt=motion_prompt,
        negative_prompt="色调艳丽，过曝，静态，细节模糊，字幕，整体发灰，最差质量",
        seed=seed, source_image=filename,
    )
    video_bytes = await self.comfyui.run_workflow(workflow)  # run_workflow 需支持视频输出
    result.video = video_bytes
    return result
```

### 4.5 comfyui_client.py 确认项

`run_workflow` 方法需要能处理**视频输出**（不只是图片）：
- 现有实现若只返回第一张图片，需要改为检测 outputs 中的 `gifs` / `video` 字段
- 视频文件用 `/view?filename=xxx&type=output` 下载

### 4.6 新增 API 路由（可选）

```python
# backend/app/api/v1/comic.py 追加：
@router.post("/edit")
async def edit_image(
    source_image: UploadFile,
    instruction: str = Form(...),
    seed: int = Form(-1),
):
    img_bytes = await source_image.read()
    result = await comic_agent.edit_image(img_bytes, instruction, seed)
    ...

@router.post("/animate")
async def animate_image(
    source_image: UploadFile,
    motion_prompt: str = Form(...),
    seed: int = Form(-1),
):
    img_bytes = await source_image.read()
    result = await comic_agent.animate_image(img_bytes, motion_prompt, seed)
    ...
```

---

## 四-B、全量工作流测试

### 测试脚本

```bash
# 安装依赖
pip install openpyxl

# 运行测试（需 ComfyUI 实例已开机）
python3 /tmp/test_all_workflows.py
```

测试脚本路径：`/tmp/test_all_workflows.py`  
测试报告输出：`autoDl部署/真人漫剧生成分析/工作流测试报告.xlsx`

### 测试用例覆盖

| 工作流 | 类型 | 测试输入 | 期望耗时 |
|---|---|---|---|
| `xianxia_basic` | 文生图 | 仙侠英文提示词 | ~30s |
| `anime_basic` | 文生图 | 动漫英文提示词 | ~30s |
| `blindbox_q` | 文生图 | Q版英文提示词 | ~30s |
| `moxin_ink` | 文生图 | 水墨英文提示词 | ~30s |
| `z_image_t2i` | 文生图 | 真人写实提示词 | ~30s |
| `xianxia_instantid` | 人脸保持 | girl.png + 仙侠提示词 | ~60s |
| `qwen_edit` | 图像编辑 | girl.png + "把衣服改成红色" | ~15s |
| `wan_i2v` | 图生视频 | girl.png + 运动描述 | ~5min（提交后跳过等待） |

Excel 报告列：序号 / 工作流 / 类型 / 参数摘要 / **状态** / **耗时** / prompt_id / 输出文件 / 错误信息

---

---

## 五、Seedance / SeedVR2 调研结论

### 5.1 Seedance（字节视频生成）
| 项目 | 结论 |
|---|---|
| **Seedance 1.0** | 字节跳动商业产品，未完全开源，需通过火山引擎 API 付费使用 |
| **Seedance 2.0** | 截至 2026-04-28，**未开源**，无法本地部署 |

### 5.2 SeedVR2（字节视频超分，已开源！）

**镜像内已有**：`其他图像/SeedVR2_简单图像高清放大.json`

SeedVR2 是字节跳动开源的**视频/图像超分辨率模型**，功能完全不同于 Seedance：
- **用途**：将低分辨率图像/视频放大到高清（2x/4x），不是生成视频
- **开源状态**：✅ 完全开源，已集成在镜像中
- **使用场景**：Wan/LTX 生成 640×640 视频后，用 SeedVR2 放大到 1280×1280

### 5.3 推荐生产流程

```
Wan 2.2 I2V（640×640，5s@16fps）
    ↓
SeedVR2 超分（放大到 1280×1280）
    ↓
最终高清漫剧视频
```

**结论：Seedance 2.0 无法本地部署。SeedVR2（超分）已内置，可直接用作视频增强后处理。**

---

## 六、是否需要第三方接口

**结论：完全不需要。**

| 功能 | 所用模型 | 是否本地 |
|---|---|---|
| 真人图像生成 | Z-Image / Qwen Image | ✅ 本地 |
| 仙侠漫画生成 | DreamshaperXL + LoRA | ✅ 本地 |
| 图像编辑 | Qwen Image Edit / Klein | ✅ 本地 |
| 图生视频 | Wan 2.2 / LTX 2.3 | ✅ 本地 |
| 人脸保持 | InstantID / PuLID | ✅ 本地 |

唯一的外部依赖：**AutoDL 算力租赁**（约 2~5 元/小时，24GB GPU）

---

## 七、下一步测试计划

### 阶段 1：工作流获取（需手动操作）
1. 从夸克网盘下载字字动画工作流包
2. 导入 ComfyUI（拖入 JSON 文件）
3. 运行一次验证节点是否报错

### 阶段 2：API 化（我来自动完成）
每个工作流运行成功后：
1. 通过 ComfyUI API 提交运行，记录 `prompt_id`
2. 轮询 `/history/{id}` 获取结果图片/视频 URL
3. 封装为后端 Skill 函数

### 阶段 3：Agent 集成
- 在 `agent.py` 中添加 `skill_router`
- 前端 Tab2/Tab3 对接新的 Skill API
- 端到端测试：用户上传图片 → 选择操作 → Agent 选 Skill → 返回结果

### 优先级排序

| 优先级 | Skill | 原因 |
|---|---|---|
| P0 | Z-Image 文生图 | 替换现有仙侠基础，速度/质量大幅提升 |
| P0 | Qwen Image Edit | Tab2 编辑功能核心 |
| P1 | Wan 2.2 I2V | Tab3 动态化核心（已有 wan_i2v.json） |
| P1 | Klein 多图参考 | 高级编辑场景 |
| P2 | LTX 2.3 | 长视频/高质量视频需求 |
| P2 | PuLID + FLUX | FLUX 质量的人脸保持 |

---

## 八、附录：关键节点名称（ComfyUI API 实测）

> ⚠️ 以下节点名称基于 SSH 下载的真实工作流 JSON 分析，非文档猜测。

### 8.1 图像生成节点（Z-Image / Qwen Image）

```
Z-Image 文生图链路：
  UNETLoader(z_image_bf16.safetensors, default)
  CLIPLoader(qwen_3_4b.safetensors, lumina2, default)   ← 注意：type=lumina2
  VAELoader(ae.safetensors)                              ← FLUX 的 VAE
  CLIPTextEncode × 2
  EmptySD3LatentImage(1024, 1024, 1)
  ModelSamplingAuraFlow(shift=3)
  KSampler(steps=25, cfg=4, res_multistep, simple, denoise=1)
  VAEDecode → SaveImage

Qwen Image Edit 链路：
  UNETLoader(qwen_image_edit_2509_fp8_e4m3fn.safetensors, default)
  CLIPLoader(qwen_2.5_vl_7b_fp8_scaled.safetensors, qwen_image, default)  ← type=qwen_image
  VAELoader(qwen_image_vae.safetensors)
  LoraLoaderModelOnly(Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors, 1.0)
  CFGNorm(strength=1)
  ModelSamplingAuraFlow(shift=3)
  TextEncodeQwenImageEditPlus(clip, vae, image1=原图, prompt=编辑指令)
  EmptySD3LatentImage(1024, 1024, 1)
  KSampler(steps=4, cfg=1, euler, simple, denoise=1)
  VAEDecode → SaveImage
```

### 8.2 视频生成节点（Wan 2.2 I2V）

```
Wan 2.2 I2V 双路采样链路：
  UNETLoader(wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors, default)
  UNETLoader(wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors, default)
  ModelSamplingSD3(shift=8)  × 2
  CLIPLoader(umt5_xxl_fp8_e4m3fn_scaled.safetensors, wan, default)  ← type=wan
  VAELoader(wan_2.1_vae.safetensors)
  CLIPTextEncode × 2（正/负提示词）
  LoadImage(source_image)
  WanImageToVideo(positive, negative, vae, start_image, width=640, height=640, num_frames=81)
  KSamplerAdvanced(add_noise=enable,  steps=20, cfg=3.5, euler, simple, start=0)    ← 高噪路
  KSamplerAdvanced(add_noise=disable, steps=20, cfg=3.5, euler, simple, start=10)   ← 低噪路
  VAEDecode → VHS_VideoCombine(fps=16, h264-mp4)
```

### 8.3 人脸保持节点（InstantID SDXL）

```
SDXL InstantID 链路：
  CheckpointLoaderSimple(dreamshaperXL 或同类 SDXL)
  InstantIDModelLoader(ip-adapter_instant_id_sdxl.bin)
  InstantIDFaceAnalysis(provider=CUDA)
  ControlNetLoader(control_instant_id_sdxl.safetensors)
  LoadImage(face_image) + LoadImage(reference_image)
  ApplyInstantID(model, face_analysis, control_net, image, weight=0.8, start=0, end=1)
  CLIPTextEncode × 2
  EmptyLatentImage(1024, 1024, 1)
  KSampler(steps=20, cfg=7, dpmpp_2m, karras, denoise=1)
  VAEDecode → SaveImage
```

### 8.4 测试脚本快速参考

```bash
# 运行全量测试（需 ComfyUI 实例已开机）
python3 /tmp/test_all_workflows.py

# 查看 Excel 报告
open "autoDl部署/真人漫剧生成分析/工作流测试报告.xlsx"

# 测试输出图片/视频位置
ls /tmp/wf_test_outputs/
```
