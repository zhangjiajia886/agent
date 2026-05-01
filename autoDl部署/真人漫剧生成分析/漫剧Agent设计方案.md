# 漫剧生成 Agent 设计方案

> 目标：用户只需用自然语言描述需求，Agent 自动完成工作流选择、提示词生成、图像/视频生成、结果整合。

---

## 一、模型存储架构（明确分层）

```
┌─────────────────────────────────────────────────────┐
│  ttsapp 服务器（你的服务器 / 本地）                   │
│                                                     │
│  前端 Vue  ──►  后端 FastAPI                         │
│                    │                                │
│              漫剧 Agent（新增）                      │
│              ComfyUI Client（HTTP）                  │
└──────────────────┬──────────────────────────────────┘
                   │ HTTPS API
┌──────────────────▼──────────────────────────────────┐
│  AutoDL bjb2 实例（RTX 5090，按需开关）               │
│                                                     │
│  ComfyUI 服务（端口 6006）                           │
│  ~/ComfyUI/models/                                  │
│    ├── checkpoints/  （基础模型，数十GB）             │
│    ├── loras/        （风格LoRA）                    │
│    ├── controlnet/   （结构控制）                    │
│    └── ...（仅推理，不含业务逻辑）                    │
└─────────────────────────────────────────────────────┘
```

**结论**：
- **模型** → 永久留在 AutoDL RTX5090（计算密集型，需GPU）
- **业务逻辑** → 全部在 ttsapp（Agent/路由/任务管理/用户系统）
- **升级模型**：在 Jupyter Lab 直接下载，不影响 ttsapp 代码

### 模型升级操作（在 Jupyter Lab 执行）

```python
# 升级过时模型 — 在 Jupyter Lab (https://a982127-xxx:8443/jupyter/lab) 执行

import os
os.chdir("/root/ComfyUI/models/checkpoints")

# 升级A：下载 Illustrious XL（替代 NetaYumev35，动漫质量更好）
os.system("wget -c 'https://hf-mirror.com/OnomaAIResearch/Illustrious-xl-early-release-v0/resolve/main/Illustrious-XL-v0.1.safetensors' -O IllustriousXL_v0.1.safetensors")

# 升级B：下载 PuLID-FLUX 相关模型（替代 InstantID，人脸保持更强）
os.chdir("/root/ComfyUI/models/pulid")
os.system("wget -c 'https://hf-mirror.com/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors'")
```

---

## 二、对外依赖分析

### 2.1 AutoDL 实例运行时依赖

| 依赖项 | 类型 | 是否影响推理 | 说明 |
|---|---|---|---|
| **ComfyUI Manager 节点列表** | 网络（启动时） | ❌ 不影响 | 仅启动时从 GitHub/comfy.org 拉取节点元数据，可关闭 |
| **network_turbo（AutoDL学术加速）** | 系统级代理 | ❌ 不影响 | 仅加速下载，推理不需要 |
| **AutoDL 反向代理** | 平台服务 | ✅ 必须 | `u982127-xxx.bjb2.seetacloud.com:8443` URL 依赖AutoDL存活 |
| **模型文件（本地）** | 本地存储 | ✅ 必须 | 模型已在本地，推理无网络依赖 |

### 2.2 ttsapp 集成后的依赖链

```
ttsapp 后端
  → COMFYUI_URL（AutoDL实例URL，实例必须开机）
  → LLM API（提示词生成，可选 OpenAI/Claude/本地模型）
  → 现有 MySQL（任务状态存储）
  → 现有文件存储（结果图像/视频）
```

### 2.3 关键风险点

| 风险 | 影响 | 缓解方案 |
|---|---|---|
| AutoDL 实例关机 | 漫剧功能不可用 | 检测接口 + 前端提示"生成服务暂时不可用" |
| AutoDL URL 变化（重启后可能变） | API 连接失败 | 配置化 COMFYUI_URL，不硬编码 |
| 网络延迟（跨地域） | 上传/下载慢 | 压缩图像，结果存 AutoDL 临时目录后再异步下载 |

---

## 三、漫剧生成 Agent 设计

### 3.1 Agent 是什么

用户只需说：
> "帮我生成一个仙侠风格的4格漫剧，主角是年轻女侠，故事是初次踏入仙山，给我保留这张脸的特征"（+上传一张照片）

Agent 自动完成：
1. 理解意图（风格=仙侠，格数=4，剧情=初入仙山，需要人脸保持）
2. 生成4格分镜描述（LLM）
3. 生成每格专业提示词（LLM）
4. 选择工作流（InstantID + 仙侠LoRA）
5. 依次调用 ComfyUI API 生成4张图
6. 返回完整漫剧

### 3.2 Agent 架构图

```
用户输入
  │ 自然语言 + 可选人脸图
  ▼
┌─────────────────────────────────┐
│        ComicAgent               │
│                                 │
│  Step 1: IntentParser（LLM）    │
│    → 解析：风格/格数/剧情/人脸   │
│                                 │
│  Step 2: StoryboardPlanner（LLM）│
│    → 生成每格分镜描述            │
│                                 │
│  Step 3: PromptGenerator（LLM） │
│    → 生成每格专业英文提示词       │
│                                 │
│  Step 4: WorkflowSelector       │
│    → 选择合适工作流模板           │
│                                 │
│  Step 5: ComfyUIExecutor        │
│    → 依次提交 ComfyUI API        │
│    → 轮询结果，下载图像          │
│                                 │
│  Step 6: ResultComposer         │
│    → 拼接多格图，生成预览         │
└─────────────────────────────────┘
  │
  ▼
输出：多格漫剧图像 + 可选动态视频
```

### 3.3 核心代码实现

#### 文件结构

```
backend/app/
├── core/
│   ├── comfyui_client.py      # ComfyUI HTTP 通信层（已设计）
│   └── comic_agent/
│       ├── __init__.py
│       ├── agent.py           # Agent 主入口
│       ├── intent_parser.py   # 意图解析
│       ├── story_planner.py   # 分镜规划
│       ├── prompt_builder.py  # 提示词构建
│       ├── workflow_selector.py # 工作流选择
│       └── workflows/         # 工作流 JSON 模板
│           ├── xianxia_basic.json
│           ├── instantid_xianxia.json
│           └── wan_i2v.json
└── api/v1/
    └── comic.py               # 对外路由
```

#### agent.py — Agent 主入口

```python
# backend/app/core/comic_agent/agent.py

from dataclasses import dataclass
from typing import Optional
from .intent_parser import IntentParser
from .story_planner import StoryboardPlanner
from .prompt_builder import PromptBuilder
from .workflow_selector import WorkflowSelector
from ..comfyui_client import ComfyUIClient

@dataclass
class ComicRequest:
    description: str               # 用户的自然语言描述
    face_image: Optional[bytes]    # 可选：人脸参考图
    num_frames: int = 4            # 格数
    include_video: bool = False    # 是否同时生成动态版

@dataclass
class ComicResult:
    frames: list[bytes]            # 每格图像 bytes
    video: Optional[bytes]         # 动态视频（可选）
    storyboard: list[str]          # 每格分镜描述（供前端展示）
    prompts: list[str]             # 生成的提示词（供调试）


class ComicAgent:
    def __init__(self, comfyui_client: ComfyUIClient, llm_client):
        self.comfyui = comfyui_client
        self.llm = llm_client
        self.intent_parser = IntentParser(llm_client)
        self.story_planner = StoryboardPlanner(llm_client)
        self.prompt_builder = PromptBuilder(llm_client)
        self.workflow_selector = WorkflowSelector()

    async def generate(self, request: ComicRequest) -> ComicResult:
        # Step 1: 解析意图
        intent = await self.intent_parser.parse(request.description)
        # intent.style = "xianxia" | "blindbox" | "ink" | "anime"
        # intent.story = "初次踏入仙山"
        # intent.need_face = True/False

        # Step 2: 规划分镜
        storyboard = await self.story_planner.plan(
            story=intent.story,
            num_frames=request.num_frames,
            style=intent.style,
        )
        # storyboard = ["格1：远景，少女背对仙山", "格2：回头惊讶", ...]

        # Step 3: 生成提示词
        prompts = await self.prompt_builder.build_all(
            storyboard=storyboard,
            style=intent.style,
            has_face=request.face_image is not None,
        )
        # prompts = ["xianxia style, 1girl from behind...", ...]

        # Step 4: 选择工作流
        workflow_name = self.workflow_selector.select(
            style=intent.style,
            has_face=request.face_image is not None,
        )

        # Step 5: 依次生成每格
        frames = []
        for i, prompt in enumerate(prompts):
            frame_bytes = await self.comfyui.generate_image(
                workflow_name=workflow_name,
                prompt=prompt,
                face_image=request.face_image,
            )
            frames.append(frame_bytes)

        # Step 6: 可选视频化
        video = None
        if request.include_video:
            video = await self.comfyui.animate_image(
                source_image=frames[0],  # 以第一格为主
                motion_prompt="gentle breathing, hair swaying, natural motion",
            )

        return ComicResult(
            frames=frames,
            video=video,
            storyboard=storyboard,
            prompts=prompts,
        )
```

#### intent_parser.py — 意图解析

```python
# backend/app/core/comic_agent/intent_parser.py

INTENT_PROMPT = """
你是一个漫剧生成助手，分析用户的描述，提取以下信息并以JSON返回：
- style: 风格（"xianxia"仙侠 | "blindbox"盲盒Q版 | "ink"水墨 | "anime"动漫 | "realistic"写实漫）
- story: 核心故事情节（中文，简短）
- need_face: 是否需要人脸保持（true/false，若用户提到"这张脸"/"保留人物"则为true）
- mood: 情感基调（"epic"史诗 | "cute"可爱 | "dramatic"戏剧性 | "peaceful"平和）

用户描述：{description}

返回纯JSON，不要有其他文字。
"""

class IntentParser:
    def __init__(self, llm_client):
        self.llm = llm_client

    async def parse(self, description: str) -> dict:
        response = await self.llm.chat(
            INTENT_PROMPT.format(description=description)
        )
        import json
        return json.loads(response)
```

#### story_planner.py — 分镜规划

```python
# backend/app/core/comic_agent/story_planner.py

STORYBOARD_PROMPT = """
为以下漫剧生成{num_frames}格分镜描述，风格：{style}，故事：{story}

遵循起承转合结构，每格用一句话描述：
- 格N的场景（远景/中景/近景）
- 人物动作/状态
- 情绪/氛围

以JSON数组返回，例如：
["格1（远景）：少女背对仙山，仰望云端", "格2（中景）：少女回眸，表情惊讶"]
"""

class StoryboardPlanner:
    def __init__(self, llm_client):
        self.llm = llm_client

    async def plan(self, story: str, num_frames: int, style: str) -> list[str]:
        response = await self.llm.chat(
            STORYBOARD_PROMPT.format(
                story=story, num_frames=num_frames, style=style
            )
        )
        import json
        return json.loads(response)
```

#### workflow_selector.py — 工作流选择（规则式，无需LLM）

```python
# backend/app/core/comic_agent/workflow_selector.py

WORKFLOW_MAP = {
    # (style, has_face) -> workflow_name
    ("xianxia",   True):  "instantid_xianxia",      # 仙侠 + 人脸保持
    ("xianxia",   False): "xianxia_basic",           # 仙侠 纯文生图
    ("blindbox",  False): "blindbox_q",              # 盲盒Q版
    ("blindbox",  True):  "blindbox_with_face",      # 盲盒 + 人脸
    ("ink",       False): "moxin_ink",               # 水墨
    ("anime",     True):  "instantid_anime",         # 动漫 + 人脸
    ("anime",     False): "anime_basic",             # 动漫
    ("realistic", True):  "instantid_realistic",     # 写实漫 + 人脸
}

class WorkflowSelector:
    def select(self, style: str, has_face: bool) -> str:
        key = (style, has_face)
        return WORKFLOW_MAP.get(key, WORKFLOW_MAP.get((style, False), "xianxia_basic"))
```

#### comic.py — 对外 API 路由

```python
# backend/app/api/v1/comic.py

@router.post("/comic/generate")
async def generate_comic(
    description: str = Form(...,  description="用自然语言描述漫剧内容"),
    face_image: Optional[UploadFile] = File(None, description="人脸参考图（可选）"),
    num_frames: int = Form(4, ge=1, le=8),
    include_video: bool = Form(False),
    background_tasks: BackgroundTasks = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    漫剧生成接口
    - 描述示例："生成一个仙侠风格的4格漫剧，讲述少女初次踏入仙境的故事"
    - 有人脸图时自动启用人脸保持
    """
    face_bytes = await face_image.read() if face_image else None

    task = await create_comic_task(db, description=description, user_id=...)
    background_tasks.add_task(
        agent.generate,
        ComicRequest(
            description=description,
            face_image=face_bytes,
            num_frames=num_frames,
            include_video=include_video,
        ),
        task_id=task.id,
    )
    return {"task_id": task.id, "status": "pending"}


@router.get("/comic/tasks/{task_id}")
async def get_comic_status(task_id: str):
    """查询任务进度（轮询或配合 WebSocket）"""
    ...


@router.get("/comic/tasks/{task_id}/frames/{index}")
async def get_frame(task_id: str, index: int):
    """获取指定格的图像"""
    ...
```

---

## 四、前端页面设计（简化版）

```vue
<!-- 用户只需要做 3 步 -->

<template>
  <div class="comic-generator">
    <!-- 步骤1：描述 -->
    <el-input
      v-model="description"
      type="textarea"
      :rows="3"
      placeholder="描述你的漫剧：风格、人物、故事情节... 例如：生成仙侠风格4格漫剧，主角是年轻女侠，故事是她初次踏入神秘仙山"
    />

    <!-- 步骤2：可选人脸（拖拽上传） -->
    <el-upload
      drag action="#" :auto-upload="false"
      @change="onFaceSelected"
      accept="image/*"
    >
      <div>拖入人脸照片（可选，保留人物面部特征）</div>
    </el-upload>

    <!-- 步骤3：一键生成 -->
    <el-button type="primary" size="large" @click="generate" :loading="isGenerating">
      {{ isGenerating ? `生成中... ${progress}%` : '✨ 生成漫剧' }}
    </el-button>

    <!-- 结果展示 -->
    <div class="comic-strip" v-if="frames.length">
      <img v-for="(frame, i) in frames" :key="i" :src="frame" class="comic-frame" />
    </div>
  </div>
</template>
```

---

## 五、LLM 选型建议

| 选项 | 适用场景 | 费用 | 集成难度 |
|---|---|---|---|
| **OpenAI GPT-4o-mini** | 推荐，理解中文最好，提示词质量高 | 低（约$0.01/次） | 低 |
| **Claude Haiku** | 备选，也很好 | 低 | 低 |
| **Qwen-turbo（阿里云）** | 中文场景，国内无需翻墙 | 极低 | 低 |
| **本地 Qwen2.5-7B** | 无外部依赖，需本地GPU | 免费 | 中 |

ttsapp 已有 LLM 集成，直接复用现有 LLM 客户端即可。

---

## 六、实施路径（4步走）

```
Week 1：基础通信层
  ✅ comfyui_client.py（基础HTTP封装）
  ✅ 验证 TC-01~TC-03 可通过 API 调用成功生成图像

Week 2：Agent 核心
  □ 实现 intent_parser.py（LLM解析）
  □ 实现 story_planner.py（LLM分镜）
  □ 实现 prompt_builder.py（提示词生成）
  □ 实现 workflow_selector.py（规则选择）

Week 3：集成与路由
  □ 实现 comic.py 路由
  □ 数据库任务管理
  □ 拷贝工作流 JSON 模板

Week 4：前端
  □ ComicView.vue 简洁前端
  □ 进度轮询/WebSocket
  □ 端到端测试
```
