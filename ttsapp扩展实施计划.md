# ttsapp 扩展实施计划：集成 Soul AI Lab 模型

> 基于《ttsapp扩展设计.md》，本文档为**逐步可执行的实施检查清单**。  
> 每个步骤标注：文件路径、来源设计章节、验收标准、预估耗时。

---

## 总览

| 阶段 | 内容 | 文件数 | 预估 |
|------|------|-------|------|
| **P0** | 基础设施搭建 | 5 | 2h |
| **P1** | Podcast 播客集成 | 2 | 2h |
| **P2** | Singer 歌声集成 | 2 | 3h |
| **P3** | FlashHead 数字人集成 | 2 | 2h |
| **P4** | 路由注册 & 联调 | 2 | 1h |
| **P5** | 前端页面 | 6+ | 6h |
| **合计** | **20 文件（7 修改 + 13 新增）** | | **~16h** |

---

## P0 — 基础设施搭建

> 所有后续阶段依赖此阶段完成。P0 完成后应能启动服务且不报错。

### Step 0.1 — 安装依赖

| 项目 | 值 |
|------|---|
| **文件** | `backend/requirements.txt` |
| **设计参考** | §3.1 新增依赖 |
| **操作** | 追加 `gradio_client>=1.5.0` |

```bash
# 验收
pip install gradio_client>=1.5.0
python -c "from gradio_client import Client; print('OK')"
```

### Step 0.2 — 配置扩展

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/config.py` + `.env` |
| **设计参考** | §3.2 配置扩展 |
| **操作** | Settings 类中追加 7 个字段 |

**config.py 追加字段**：
```
SOUL_PODCAST_SPACE       = "Soul-AILab/SoulX-Podcast-1.7B"
SOUL_SINGER_SPACE        = "Soul-AILab/SoulX-Singer"
SOUL_FLASHHEAD_SPACE     = "Soul-AILab/SoulX-FlashHead"
SOUL_API_TIMEOUT         = 300
SOUL_HF_TOKEN            = ""
SOUL_ENABLED             = True
SOUL_MIDI_EDITOR_URL     = "https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor"
```

**.env 追加**：
```
SOUL_PODCAST_SPACE=Soul-AILab/SoulX-Podcast-1.7B
SOUL_SINGER_SPACE=Soul-AILab/SoulX-Singer
SOUL_FLASHHEAD_SPACE=Soul-AILab/SoulX-FlashHead
SOUL_API_TIMEOUT=300
SOUL_HF_TOKEN=
SOUL_ENABLED=true
SOUL_MIDI_EDITOR_URL=https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor
```

```bash
# 验收
python -c "from app.config import settings; print(settings.SOUL_PODCAST_SPACE)"
```

### Step 0.3 — Gradio 通用基类

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/core/gradio_client.py`（新建） |
| **设计参考** | §3.3 通用基类 |
| **行数** | ~60 行 |
| **核心类** | `GradioSpaceClient` |

**关键方法**：
| 方法 | 说明 |
|------|------|
| `_get_client()` | 延迟创建 gradio Client 实例 |
| `call(api_name, **kwargs)` | 在线程池中执行同步 predict，asyncio 包装 |
| `save_temp_file(data, suffix)` | 保存临时文件供 Gradio 上传 |
| `read_result_file(filepath)` | 读取 Gradio 返回的文件路径为 bytes |
| `health_check()` | 检测 Space 是否在线 |

```bash
# 验收（单元级）
python -c "from app.core.gradio_client import GradioSpaceClient; print('import OK')"
```

### Step 0.4 — SoulTask 数据模型

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/models/soul_task.py`（新建） |
| **设计参考** | §3.7 统一 SoulTask 模型 |
| **行数** | ~45 行 |

**核心定义**：
- `SoulTaskType` 枚举: `podcast`, `singing_svs`, `singing_svc`, `digital_human`
- `SoulTaskStatus` 枚举: `pending`, `processing`, `completed`, `failed`
- `SoulTask` 表字段: id, user_id, task_type, status, input_text, input_params, ref_audio_url, ref_audio2_url, ref_image_url, source_audio_url, midi_url, metadata_url, output_url, output_size, output_format, error_message, created_at, completed_at

⚠️ **关键步骤**：必须在 `backend/app/models/__init__.py` 中注册新模型！

```python
# backend/app/models/__init__.py 追加：
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus

__all__ = [..., "SoulTask", "SoulTaskType", "SoulTaskStatus"]
```

> 不注册则 `Base.metadata.create_all` 不会创建 `soul_tasks` 表。

```bash
# 验收：启动服务后检查表是否自动创建
python -c "from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus; print('OK')"
```

### Step 0.5 — Schema 定义

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/schemas/soul.py`（新建） |
| **设计参考** | §3.8 请求/响应 Schema |
| **行数** | ~55 行 |

**Schema 列表**：
| Schema | 用途 |
|--------|------|
| `PodcastResponse` | 播客合成任务创建响应 |
| `SVSResponse` | 歌声合成任务创建响应 |
| `SVCResponse` | 歌声转换任务创建响应 |
| `DigitalHumanResponse` | 数字人生成任务创建响应 |
| `SoulTaskDetail` | 通用任务详情（含所有字段） |

```bash
# 验收
python -c "from app.schemas.soul import SoulTaskDetail, PodcastResponse; print('OK')"
```

### ✅ P0 里程碑验收

```bash
# 服务正常启动，无报错
cd backend && uvicorn app.main:app --reload
# 数据库中出现 soul_tasks 表
# Swagger UI (/docs) 可以正常打开
```

---

## P1 — Podcast 播客集成

> 依赖：P0 完成

### Step 1.1 — Podcast 客户端

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/core/podcast_client.py`（新建） |
| **设计参考** | §3.4 Podcast 客户端 |
| **行数** | ~45 行 |
| **对接 API** | `/dialogue_synthesis_function` |

**核心方法**：
```
podcast_client.synthesize(
    target_text, spk1_prompt_audio_bytes, spk1_prompt_text,
    spk1_dialect_prompt_text, spk2_prompt_audio_bytes,
    spk2_prompt_text, spk2_dialect_prompt_text, seed
) → bytes (wav)
```

**实现要点**：
- 继承 `GradioSpaceClient`
- `spk2` 系列参数可选（独白模式不传）
- 结果为 `(sample_rate, audio_array)` 元组或文件路径，需兼容两种

### Step 1.2 — Podcast 路由

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/api/v1/podcast.py`（新建） |
| **设计参考** | §3.9 路由设计 |
| **行数** | ~90 行 |

**路由列表**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/synthesize` | 提交播客合成任务（双说话人） |
| GET | `/tasks` | 任务列表 |
| GET | `/tasks/{id}` | 任务详情 |
| GET | `/health` | Space 在线检查 |

**POST `/synthesize` 参数**：
| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `target_text` | Form str | ✅ | 对话文本 `[S1]...\n[S2]...` |
| `spk1_prompt_audio` | UploadFile | ✅ | 说话人1 参考音频 |
| `spk1_prompt_text` | Form str | | 说话人1 参考文本 |
| `spk1_dialect_prompt_text` | Form str | | 方言提示 `<\|Sichuan\|>...` |
| `spk2_prompt_audio` | UploadFile | | 说话人2 参考音频 |
| `spk2_prompt_text` | Form str | | 说话人2 参考文本 |
| `spk2_dialect_prompt_text` | Form str | | 说话人2 方言提示 |
| `seed` | Form int | | 默认 1988 |

### ✅ P1 里程碑验收

```bash
# 1. 在 main.py 临时注册 podcast 路由（或等 P4 统一注册）
# 2. Swagger UI 测试：
#    POST /api/v1/podcast/synthesize  上传音频+文本 → 返回 task_id
#    GET  /api/v1/podcast/tasks/{id}  轮询至 completed
#    GET  /api/v1/podcast/health      返回 {"online": true}
# 3. 下载 output_url 对应音频，人工听验
```

---

## P2 — Singer 歌声集成

> 依赖：P0 完成（与 P1 可并行）

### Step 2.1 — Singer 客户端

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/core/singer_client.py`（新建） |
| **设计参考** | §3.5 Singer 客户端 |
| **行数** | ~80 行 |
| **对接 API** | `/transcription_function` + `/synthesis_function` + `/_start_svc` |

**3 个核心方法**：

| 方法 | 对接 Gradio API | 输入 | 输出 |
|------|-----------------|------|------|
| `transcribe()` | `/transcription_function` | 2 音频 + lang + vocal_sep | `(prompt_meta_bytes, target_meta_bytes)` |
| `synthesize_singing()` | `/synthesis_function` | 2 音频 + control/shift/seed/lang/sep + 可选 metadata | `bytes (wav)` |
| `convert_voice()` | `/_start_svc` | 2 音频 + vocal_sep/shift/n_step/cfg/fp16/seed | `bytes (wav)` |

**实现要点**：
- `synthesize_singing` 返回 `(output_audio, prompt_meta, target_meta)` 三元组，取 `[0]`
- `convert_voice` 返回单个文件路径
- metadata 为可选 JSON 文件，通过 `handle_file()` 上传

### Step 2.2 — Singer 路由

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/api/v1/singing.py`（新建） |
| **设计参考** | §3.10 路由设计 |
| **行数** | ~130 行 |

**路由列表**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/transcribe` | 歌词转写（同步，返回 metadata JSON） |
| POST | `/svs` | 歌声合成任务（异步后台） |
| POST | `/svc` | 歌声转换任务（异步后台） |
| GET | `/tasks` | 歌声任务列表（SVS+SVC 合并） |
| GET | `/tasks/{id}` | 任务详情 |
| GET | `/health` | Singer Space 在线检查 |

**关键差异**：
- `/transcribe` 是**同步接口**（转写耗时较短），直接返回 base64 编码的 metadata JSON
- `/svs` 和 `/svc` 走异步 BackgroundTask 模式
- SVS 核心输入是**两段音频**（非歌词文本），模型自动转写歌词和提取旋律

### ✅ P2 里程碑验收

```bash
# Swagger UI 测试：
# 1. POST /api/v1/singing/transcribe  → 返回 prompt_metadata + target_metadata (base64)
# 2. POST /api/v1/singing/svs         → 返回 task_id → 轮询完成 → 下载音频
# 3. POST /api/v1/singing/svc         → 返回 task_id → 轮询完成 → 下载音频
# 4. GET  /api/v1/singing/tasks       → 列出 SVS+SVC 任务
```

---

## P3 — FlashHead 数字人集成

> 依赖：P0 完成（与 P1/P2 可并行）

### Step 3.1 — FlashHead 客户端

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/core/flashhead_client.py`（新建） |
| **设计参考** | §3.6 FlashHead 客户端 |
| **行数** | ~40 行 |
| **对接 API** | `/run_inference_streaming` |

**核心方法**：
```
flashhead_client.generate_video(
    image_bytes, audio_bytes, model_type="lite", seed=9999, use_face_crop=False
) → bytes (mp4)
```

**实现要点**：
- Space 内部 `ckpt_dir` 和 `wav2vec_dir` 路径固定，客户端硬编码
- 流式 yield 输出，`gradio_client` SDK 自动等待全部片段完成后返回最终视频
- 结果可能是 list/tuple，取最后一个元素

### Step 3.2 — FlashHead 路由

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/api/v1/digital_human.py`（新建） |
| **设计参考** | §3.11 路由设计 |
| **行数** | ~100 行 |

**路由列表**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/generate` | 提交数字人视频生成任务 |
| GET | `/tasks` | 任务列表 |
| GET | `/tasks/{id}` | 任务详情 |
| GET | `/health` | Space 在线检查 |

**POST `/generate` 参数**：
| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `image` | UploadFile | ✅ | 参考人脸图片 (jpg/png) |
| `audio` | UploadFile | ✅ | 驱动音频 (wav/mp3) |
| `model_type` | Form str | | `"lite"` 或 `"pro"`，默认 `"lite"` |
| `seed` | Form int | | 默认 9999 |
| `use_face_crop` | Form bool | | 默认 false |

### ✅ P3 里程碑验收

```bash
# Swagger UI 测试：
# 1. POST /api/v1/digital-human/generate  上传图片+音频 → 返回 task_id
# 2. GET  /api/v1/digital-human/tasks/{id} 轮询至 completed
# 3. 下载 output_url 对应 mp4，播放检验口型同步
# 4. GET  /api/v1/digital-human/health     返回 {"online": true}
```

---

## P4 — 路由注册 & 联调

> 依赖：P1 + P2 + P3 全部完成

### Step 4.1 — main.py 注册路由

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/main.py`（修改） |
| **设计参考** | §3.12 注册路由 |
| **改动** | +3 行 import + 3 行 include_router |

```python
from app.api.v1 import podcast, singing, digital_human

app.include_router(podcast.router, prefix=f"{settings.API_V1_PREFIX}/podcast", tags=["Podcast"])
app.include_router(singing.router, prefix=f"{settings.API_V1_PREFIX}/singing", tags=["Singing"])
app.include_router(digital_human.router, prefix=f"{settings.API_V1_PREFIX}/digital-human", tags=["Digital Human"])
```

### Step 4.1b — models/__init__.py 注册模型

| 项目 | 值 |
|------|---|
| **文件** | `backend/app/models/__init__.py`（修改） |
| **操作** | 追加 SoulTask 导入 |

```python
# 在现有 import 后追加：
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus
```

> 当前 `__init__.py` 导入了 User, VoiceModel, TTSTask, ASRTask, ChatSession, ChatMessage。
> 必须追加 SoulTask 才能让 SQLAlchemy 自动建表。

### Step 4.2 — 全量后端联调

```bash
# 验收清单（全部通过后 P4 完成）
# ┌────────────────────────────────────────────────────────────────────┐
# │ 1. 服务启动无报错                                                   │
# │ 2. Swagger /docs 显示 Podcast / Singing / Digital Human 三组路由     │
# │ 3. soul_tasks 表在 DB 中已创建                                      │
# │ 4. Podcast: 上传音频+文本 → 任务完成 → 下载 wav 可播放                 │
# │ 5. Singer SVS: 上传两段音频 → 任务完成 → 下载 wav 可播放               │
# │ 6. Singer SVC: 上传两段音频 → 任务完成 → 下载 wav 可播放               │
# │ 7. Singer Transcribe: 上传音频 → 同步返回 metadata JSON              │
# │ 8. FlashHead: 上传图片+音频 → 任务完成 → 下载 mp4 可播放              │
# │ 9. 各 /health 端点返回 online 状态                                   │
# │10. SOUL_ENABLED=false 时所有 Soul 路由返回 503                       │
# └────────────────────────────────────────────────────────────────────┘
```

---

## P5 — 前端页面

> 依赖：P4 完成（后端 API 全部可用）

### Step 5.1 — 前端 API 封装

| 项目 | 值 |
|------|---|
| **文件** | `frontend/src/api/soul.ts`（新建） |
| **行数** | ~80 行 |

封装所有 Soul API 调用：
```
podcastSynthesize(formData)  → { task_id, status }
singingTranscribe(formData)  → { prompt_metadata, target_metadata }
singingSvs(formData)         → { task_id, status }
singingSvc(formData)         → { task_id, status }
digitalHumanGenerate(formData) → { task_id, status }
getSoulTask(module, taskId)  → SoulTaskDetail
getSoulTasks(module, skip, limit) → SoulTaskDetail[]
```

### Step 5.2 — 播客语音页面

| 项目 | 值 |
|------|---|
| **文件** | `frontend/src/views/podcast/PodcastView.vue`（新建） |
| **行数** | ~150 行 |

**UI 组件**：
- 对话文本输入框（多行，提示 `[S1]...\n[S2]...` 格式）
- 说话人1 区域：音频上传 + 参考文本 + 方言提示下拉
- 说话人2 区域：音频上传 + 参考文本 + 方言提示（可折叠，独白可不填）
- Seed 输入
- 提交按钮 → 进度轮询 → 音频播放器 + 下载按钮
- 历史任务列表

### Step 5.3 — AI 歌声页面

| 项目 | 值 |
|------|---|
| **文件** | `frontend/src/views/singing/SingingView.vue`（新建） |
| **行数** | ~200 行 |

**UI 布局**（Tabs 双标签页）：

**SVS 标签页**：
- Prompt 音频上传（目标音色，max 30s）
- Target 音频上传（旋律来源，max 60s）
- 控制模式: melody / score 切换
- 高级参数折叠面板: auto_shift, pitch_shift, seed, lyric_lang, vocal_sep
- 可选 metadata 上传（JSON）
- 转写按钮（调 `/transcribe`）+ MIDI Editor 外链
- 合成按钮 → 进度轮询 → 播放器

**SVC 标签页**：
- Prompt 音频上传（目标音色）
- Target 音频上传（待转换歌曲）
- 高级参数面板: vocal_sep, auto_shift, auto_mix_acc, pitch_shift, n_step, cfg, fp16, seed
- 转换按钮 → 进度轮询 → 播放器

### Step 5.4 — 数字人页面

| 项目 | 值 |
|------|---|
| **文件** | `frontend/src/views/digital-human/DigitalHumanView.vue`（新建） |
| **行数** | ~150 行 |

**UI 组件**：
- 参考图片上传（支持预览）
- 驱动音频上传
- Model type: lite / pro 切换
- Seed 输入 + 人脸裁剪开关
- 提交按钮 → 进度轮询 → 视频播放器 + 下载按钮
- 历史任务列表

### Step 5.5 — 路由 & 菜单注册

**5.5a — 前端路由** `frontend/src/router/index.ts`（修改）

在 `children` 数组的 `chat` 路由后追加：
```typescript
{
  path: 'podcast',
  name: 'Podcast',
  component: () => import('@/views/podcast/PodcastView.vue'),
  meta: { title: '播客语音', icon: 'Microphone' },
},
{
  path: 'singing',
  name: 'Singing',
  component: () => import('@/views/singing/SingingView.vue'),
  meta: { title: 'AI 歌声', icon: 'VideoCamera' },
},
{
  path: 'digital-human',
  name: 'DigitalHuman',
  component: () => import('@/views/digital-human/DigitalHumanView.vue'),
  meta: { title: '数字人', icon: 'Avatar' },
},
```

**5.5b — 侧边栏菜单** `frontend/src/views/layout/MainLayout.vue`（修改）

在现有 `<el-menu-item index="/chat">` 之后追加：
```vue
<el-menu-item index="/podcast">
  <el-icon><Microphone /></el-icon>
  <template #title>播客语音</template>
</el-menu-item>
<el-menu-item index="/singing">
  <el-icon><VideoCamera /></el-icon>
  <template #title>AI 歌声</template>
</el-menu-item>
<el-menu-item index="/digital-human">
  <el-icon><Avatar /></el-icon>
  <template #title>数字人</template>
</el-menu-item>
```

> 现有菜单项：仪表盘、TTS、ASR、声音模型、AI 陪聊。新增 3 项在末尾。

### Step 5.6 — 前端请求超时调整

| 项目 | 值 |
|------|---|
| **文件** | `frontend/src/api/soul.ts` |
| **注意** | Soul API 调用耗时远超普通接口 |

> 现有 `request.ts` 默认超时 60s，但 Soul Space 任务可能需要 5 分钟。
> **解决方案**：`soul.ts` 中创建独立 axios 实例或在请求级覆盖 timeout。

```typescript
// soul.ts 中每个请求均需设置较长超时
export function podcastSynthesize(formData: FormData) {
  return request.post('/v1/podcast/synthesize', formData, { timeout: 300000 })
}
```

> 注意：异步任务模式下 POST 只是创建任务（秒级返回），真正耗时在后端 BackgroundTask。
> 但 `/transcribe` 是同步接口，可能需要 2-3 分钟，必须设长超时。

### ✅ P5 里程碑验收

```
1. 三个页面均可正常访问、渲染无报错
2. Podcast 页面：双说话人音频上传 → 提交 → 轮询 → 播放合成音频
3. Singer SVS 页面：双音频上传 → 合成 → 播放
4. Singer SVC 页面：双音频上传 → 转换 → 播放
5. Singer 转写功能：上传音频 → 获取 metadata → 可下载 JSON
6. 数字人页面：上传图片+音频 → 生成 → 播放 mp4 视频
7. 任务列表正常展示历史记录
8. MIDI Editor 链接可正常跳转
```

---

## 文件变更清单

> 按创建/修改顺序排列，每个文件标注所属阶段

### 新建文件（13 个）

| # | 阶段 | 文件路径 | 行数 |
|---|------|---------|------|
| 1 | P0 | `backend/app/core/gradio_client.py` | ~60 |
| 2 | P0 | `backend/app/models/soul_task.py` | ~45 |
| 3 | P0 | `backend/app/schemas/soul.py` | ~55 |
| 4 | P1 | `backend/app/core/podcast_client.py` | ~45 |
| 5 | P1 | `backend/app/api/v1/podcast.py` | ~90 |
| 6 | P2 | `backend/app/core/singer_client.py` | ~80 |
| 7 | P2 | `backend/app/api/v1/singing.py` | ~130 |
| 8 | P3 | `backend/app/core/flashhead_client.py` | ~40 |
| 9 | P3 | `backend/app/api/v1/digital_human.py` | ~100 |
| 10 | P5 | `frontend/src/api/soul.ts` | ~80 |
| 11 | P5 | `frontend/src/views/podcast/PodcastView.vue` | ~150 |
| 12 | P5 | `frontend/src/views/singing/SingingView.vue` | ~200 |
| 13 | P5 | `frontend/src/views/digital-human/DigitalHumanView.vue` | ~150 |

### 修改文件（7 个）

| # | 阶段 | 文件路径 | 改动 |
|---|------|---------|------|
| 1 | P0 | `backend/requirements.txt` | +1 行 |
| 2 | P0 | `backend/app/config.py` | +7 行 |
| 3 | P0 | `.env` | +7 行 |
| 4 | P4 | `backend/app/main.py` | +6 行 |
| 5 | P4 | `backend/app/models/__init__.py` | +2 行（SoulTask 注册） |
| 6 | P5 | `frontend/src/router/index.ts` | +3 路由定义 |
| 7 | P5 | `frontend/src/views/layout/MainLayout.vue` | +3 个 el-menu-item |

---

## 跨模块依赖注意事项

实施时需注意以下隐含依赖，设计文档中以代码形式体现但容易遗漏：

| 依赖项 | 说明 | 影响文件 |
|--------|------|---------|
| **`save_audio_file`** | Podcast / Singer 路由复用现有 TTS 的文件保存函数：`from app.api.v1.tts import save_audio_file` | `podcast.py`, `singing.py` |
| **`get_current_user`** | 所有新路由需要 JWT 认证：`from app.api.v1.auth import get_current_user` | 所有路由文件 |
| **`get_db`** | 数据库 session 依赖：`from app.db.session import get_db` | 所有路由文件 |
| **`settings.UPLOAD_DIR`** | 数字人视频手动保存到上传目录（非复用 `save_audio_file`） | `digital_human.py` |
| **Element Plus 图标** | 前端新增菜单需注册 `Avatar`, `VideoCamera` 等图标（若未全局注册） | `MainLayout.vue` |

---

## 风险 & 缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| HF Space 排队/不可用 | 任务超时失败 | `SOUL_API_TIMEOUT=300`；`/health` 端点提前探测；前端提示排队状态 |
| Space 冷启动慢（首次 2-5min） | 首个任务超时 | 定时心跳保活（每 10min 空调用）；或接受首次等待 |
| 大文件上传（音频/视频） | 内存峰值 | `save_temp_file` 流式写入；任务完成后清理临时文件 |
| Gradio API 签名变更 | 调用失败 | 客户端方法中 try/except + 详细日志；版本锁定 `gradio_client` |
| 并发请求过多 | HF 限流 | v1.1 阶段加 Redis 队列 + 速率限制 |
| `SOUL_ENABLED=false` 误配 | 所有 Soul 功能不可用 | 路由层统一拦截返回 503，日志明确提示 |

---

## 执行顺序依赖图

```
P0 基础设施
 ├──→ P1 Podcast ──┐
 ├──→ P2 Singer  ──┼──→ P4 路由注册 & 联调 ──→ P5 前端页面
 └──→ P3 FlashHead─┘
```

> **P1/P2/P3 互不依赖，可并行开发。** P4 需等三者全部完成。P5 依赖 P4。

---

## 验收总检查清单

完成所有阶段后，按以下清单逐项验收：

- [ ] `pip install -r requirements.txt` 无报错
- [ ] 服务 `uvicorn app.main:app` 启动无报错
- [ ] Swagger `/docs` 显示全部 15 个新增 API 端点
- [ ] DB 中 `soul_tasks` 表已自动创建
- [ ] **Podcast**: 合成任务 → 完成 → 下载 wav 可播放
- [ ] **Podcast**: 双说话人 + 方言提示正常工作
- [ ] **Singer SVS**: 双音频合成 → 完成 → 下载 wav 可播放
- [ ] **Singer SVC**: 音色转换 → 完成 → 下载 wav 可播放
- [ ] **Singer Transcribe**: 同步返回 metadata JSON
- [ ] **FlashHead**: 图片+音频 → 视频生成 → 下载 mp4 可播放
- [ ] 各 `/health` 端点正确反映 Space 在线状态
- [ ] `SOUL_ENABLED=false` 时所有 Soul 路由返回 503
- [ ] 前端三个页面正常渲染、提交、轮询、播放
- [ ] 前端 MIDI Editor 链接可跳转
- [ ] 前端左侧菜单显示 3 个新入口
- [ ] 现有 TTS/ASR/Chat 功能**不受影响**（零侵入验证）
