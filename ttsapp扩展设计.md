# ttsapp 扩展设计：集成 Soul AI Lab 模型

> 基于《迁移可行性分析.md》，本文档给出**可直接落地的详细设计**。  
> 原则：复用现有架构模式，最小改动，渐进式扩展。

---

## 一、当前架构回顾

```
backend/app/
├── main.py                    # FastAPI 入口，注册路由
├── config.py                  # Settings (pydantic-settings, 读 .env)
├── core/
│   ├── fish_speech.py         # FishSpeechClient (httpx → Fish Audio)
│   ├── llm_client.py          # SouthgridLLMClient (httpx → AI Gateway)
│   └── security.py            # JWT
├── api/v1/
│   ├── tts.py                 # POST /synthesize → BackgroundTask → TTSTask
│   ├── asr.py                 # POST /recognize  → BackgroundTask → ASRTask
│   ├── chat.py                # POST /stream → SSE
│   └── voice_models.py        # CRUD + Fish Audio 音色管理
├── models/
│   ├── tts_task.py            # TTSTask (status: pending→processing→completed)
│   └── asr_task.py            # ASRTask
└── schemas/
    └── tts.py                 # TTSRequest / TTSResponse / TTSTaskDetail
```

**核心模式**：  
`Router → BackgroundTask → Client → 外部 API → 存文件 → 更新 DB status`

新增模块严格复用此模式。

---

## 二、扩展后目标架构

```
backend/app/
├── main.py                    # +3 行 include_router
├── config.py                  # +6 行 Soul 配置
├── core/
│   ├── fish_speech.py         # [不变]
│   ├── llm_client.py          # [不变]
│   ├── security.py            # [不变]
│   ├── gradio_client.py       # [新增] Gradio Space 通用基类
│   ├── podcast_client.py      # [新增] SoulX-Podcast 客户端
│   ├── singer_client.py       # [新增] SoulX-Singer 客户端
│   └── flashhead_client.py    # [新增] SoulX-FlashHead 客户端
├── api/v1/
│   ├── tts.py                 # [不变]
│   ├── asr.py                 # [不变]
│   ├── chat.py                # [不变]
│   ├── voice_models.py        # [不变]
│   ├── podcast.py             # [新增] 播客语音合成路由
│   ├── singing.py             # [新增] 歌声合成路由
│   └── digital_human.py       # [新增] 数字人视频生成路由
├── models/
│   ├── tts_task.py            # [不变]
│   ├── asr_task.py            # [不变]
│   └── soul_task.py           # [新增] 统一 Soul 任务模型
└── schemas/
    ├── tts.py                 # [不变]
    └── soul.py                # [新增] 请求/响应 Schema
```

---

## 三、详细设计

### 3.1 新增依赖

```txt
# requirements.txt 追加
gradio_client>=1.5.0
```

> `gradio_client` 是 Gradio 官方 Python SDK，用于调用 HuggingFace Spaces API。  
> 无需安装 gradio 本身，client 是独立轻量包。

---

### 3.2 配置扩展 — `config.py`

```python
# ---- Soul AI Lab 配置 ----
SOUL_PODCAST_SPACE: str = "Soul-AILab/SoulX-Podcast-1.7B"
    # 可切换为 "Soul-AILab/SoulX-Podcast-1.7B-Dialect" 使用方言专用模型
    # 两个 Space API 签名完全相同，仅模型权重不同
SOUL_SINGER_SPACE: str = "Soul-AILab/SoulX-Singer"
SOUL_FLASHHEAD_SPACE: str = "Soul-AILab/SoulX-FlashHead"
SOUL_API_TIMEOUT: int = 300          # Gradio Space 最大等待秒数
SOUL_HF_TOKEN: str = ""              # 可选，HF 令牌（提升速率限制）
SOUL_ENABLED: bool = True            # 总开关，关闭后相关路由返回 503
SOUL_MIDI_EDITOR_URL: str = "https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor"
    # MIDI 编辑器前端 URL（纯前端应用，无需后端代理，前端直接 iframe/链接跳转）
```

对应 `.env` 追加：
```env
SOUL_PODCAST_SPACE=Soul-AILab/SoulX-Podcast-1.7B
# SOUL_PODCAST_SPACE=Soul-AILab/SoulX-Podcast-1.7B-Dialect  # 切换方言专用模型
SOUL_SINGER_SPACE=Soul-AILab/SoulX-Singer
SOUL_FLASHHEAD_SPACE=Soul-AILab/SoulX-FlashHead
SOUL_API_TIMEOUT=300
SOUL_HF_TOKEN=
SOUL_ENABLED=true
SOUL_MIDI_EDITOR_URL=https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor
```

---

### 3.3 通用基类 — `core/gradio_client.py`

```python
"""Gradio Space 通用调用基类，异步封装同步 gradio_client SDK"""

import asyncio
import tempfile
import os
from typing import Optional, Any
from gradio_client import Client, handle_file
from loguru import logger
from app.config import settings


class GradioSpaceClient:

    def __init__(self, space_id: str, timeout: Optional[int] = None):
        self.space_id = space_id
        self.timeout = timeout or settings.SOUL_API_TIMEOUT
        self.hf_token = settings.SOUL_HF_TOKEN or None

    def _get_client(self) -> Client:
        return Client(self.space_id, hf_token=self.hf_token)

    async def save_temp_file(self, data: bytes, suffix: str) -> str:
        """将 bytes 写入临时文件，返回路径"""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.write(fd, data)
        os.close(fd)
        return path

    async def call(self, api_name: str, **kwargs) -> Any:
        """在线程池中执行同步 Gradio 调用，不阻塞事件循环"""
        loop = asyncio.get_event_loop()

        def _sync():
            client = self._get_client()
            return client.predict(api_name=api_name, **kwargs)

        logger.info(f"[Gradio] calling {self.space_id}{api_name}")
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _sync),
            timeout=self.timeout,
        )
        logger.info(f"[Gradio] {self.space_id}{api_name} done")
        return result

    async def read_result_file(self, filepath: str) -> bytes:
        """读取 Gradio 返回的本地文件路径为 bytes"""
        loop = asyncio.get_event_loop()
        def _read():
            with open(filepath, "rb") as f:
                return f.read()
        return await loop.run_in_executor(None, _read)

    async def health_check(self) -> bool:
        """检查 Space 是否在线"""
        try:
            loop = asyncio.get_event_loop()
            def _check():
                client = self._get_client()
                return client.view_api()  # 不报错即在线
            await asyncio.wait_for(
                loop.run_in_executor(None, _check),
                timeout=30,
            )
            return True
        except Exception as e:
            logger.warning(f"[Gradio] {self.space_id} offline: {e}")
            return False
```

---

### 3.4 Podcast 客户端 — `core/podcast_client.py`

> **源码校验**: 基于 HF Space `app.py` 中 `dialogue_synthesis_function` 实际签名

**实际 Gradio 函数签名**（来自源码）:
```python
dialogue_synthesis_function(
    target_text,                # "[S1]xxx\n[S2]xxx" 对话文本（支持 [S1]~[S4]）
    spk1_prompt_text,           # 说话人1 参考文本
    spk1_prompt_audio,          # 说话人1 参考音频
    spk1_dialect_prompt_text,   # 说话人1 方言提示（如 "<|Sichuan|>..."）
    spk2_prompt_text,           # 说话人2 参考文本
    spk2_prompt_audio,          # 说话人2 参考音频
    spk2_dialect_prompt_text,   # 说话人2 方言提示
    seed,                       # 随机种子
) -> audio (wav)
```

**客户端代码**:
```python
"""SoulX-Podcast 播客语音合成客户端"""

import os
from typing import Optional
from gradio_client import handle_file
from loguru import logger
from app.config import settings
from app.core.gradio_client import GradioSpaceClient


class PodcastClient(GradioSpaceClient):

    def __init__(self):
        super().__init__(settings.SOUL_PODCAST_SPACE)

    async def synthesize(
        self,
        target_text: str,
        spk1_prompt_audio_bytes: bytes,
        spk1_prompt_text: str = "",
        spk1_dialect_prompt_text: str = "",
        spk2_prompt_audio_bytes: Optional[bytes] = None,
        spk2_prompt_text: str = "",
        spk2_dialect_prompt_text: str = "",
        seed: int = 1988,
    ) -> bytes:
        """
        播客/对话语音合成（支持双说话人独立配置）

        :param target_text: 对话文本，格式 "[S1]xxx\n[S2]xxx"
                            支持 [S1]~[S4]，支持副语言标签 <|laughter|> <|sigh|> 等
        :param spk1_prompt_audio_bytes: 说话人1 参考音频（零样本声音克隆）
        :param spk1_prompt_text: 说话人1 参考文本（对应参考音频的文字内容）
        :param spk1_dialect_prompt_text: 说话人1 方言提示，如 "<|Sichuan|>四川话文本"
        :param spk2_prompt_audio_bytes: 说话人2 参考音频（可选，单人独白可不传）
        :param spk2_prompt_text: 说话人2 参考文本
        :param spk2_dialect_prompt_text: 说话人2 方言提示
        :param seed: 随机种子（控制生成一致性）
        :return: 合成音频 bytes (wav)
        """
        spk1_path = await self.save_temp_file(spk1_prompt_audio_bytes, ".wav")
        spk2_path = None
        try:
            if spk2_prompt_audio_bytes:
                spk2_path = await self.save_temp_file(spk2_prompt_audio_bytes, ".wav")

            result = await self.call(
                api_name="/dialogue_synthesis_function",
                target_text=target_text,
                spk1_prompt_text=spk1_prompt_text,
                spk1_prompt_audio=handle_file(spk1_path),
                spk1_dialect_prompt_text=spk1_dialect_prompt_text,
                spk2_prompt_text=spk2_prompt_text,
                spk2_prompt_audio=handle_file(spk2_path) if spk2_path else None,
                spk2_dialect_prompt_text=spk2_dialect_prompt_text,
                seed=seed,
            )
            # result 是 (sample_rate, audio_array) 元组 或文件路径
            if isinstance(result, str):
                return await self.read_result_file(result)
            elif isinstance(result, tuple):
                return await self.read_result_file(result[0])
            return result
        finally:
            os.unlink(spk1_path)
            if spk2_path:
                os.unlink(spk2_path)


podcast_client = PodcastClient()
```

**支持的方言提示格式**:
- 四川话: `<|Sichuan|>方言文本内容`
- 粤语: `<|Yue|>粤语文本内容`
- 河南话: `<|Henan|>方言文本内容`
- 不使用方言: 留空 `""`

---

### 3.5 Singer 客户端 — `core/singer_client.py`

> **源码校验**: 基于 HF Space `webui.py` `transcription_function` + `synthesis_function` 和 `webui_svc.py` `_start_svc` 实际签名

**实际 Gradio 函数签名**（SVS 转写 — `transcription_btn.click`）:
```python
transcription_function(
    prompt_audio,       # 参考歌手音频
    target_audio,       # 目标音频
    prompt_metadata,    # 可选，已有 prompt metadata（若传入则直接复制不重新转写）
    target_metadata,    # 可选，已有 target metadata
    prompt_lyric_lang,  # "Mandarin" / "Cantonese" / "English"
    target_lyric_lang,  # "Mandarin" / "Cantonese" / "English"
    prompt_vocal_sep,   # bool，参考音频声伴分离
    target_vocal_sep,   # bool，目标音频声伴分离
) -> (prompt_metadata_path, target_metadata_path)  # 两个 JSON 文件路径
```

> **工作流说明**: 这是一个**可选的预处理步骤**。用户可以：
> 1. 先调用 `transcription_function` 获取自动转写的 metadata JSON
> 2. 下载 metadata → 用 [SoulX-Singer-Midi-Editor](https://huggingface.co/spaces/Soul-AILab/SoulX-Singer-Midi-Editor) 编辑对齐
> 3. 上传编辑后的 metadata → 调用 `synthesis_function` 获得更精确的合成结果
>
> 若不需要手动编辑，可直接调用 `synthesis_function`，它会自动执行转写。

**实际 Gradio 函数签名**（SVS 合成 — `synthesis_btn.click`）:
```python
synthesis_function(
    prompt_audio,       # 参考歌手音频（max 30s）
    target_audio,       # 旋律/歌词来源音频（max 60s）—— 注意：不是歌词文本！
    prompt_metadata,    # 可选，自定义 prompt JSON metadata
    target_metadata,    # 可选，自定义 target JSON metadata
    control_radio,      # "melody" 或 "score"
    auto_shift,         # bool，自动音高偏移
    pitch_shift,        # int，手动音高偏移（-36 ~ 36 半音）
    seed_input,         # int，随机种子
    prompt_lyric_lang,  # "Mandarin" / "Cantonese" / "English"
    target_lyric_lang,  # "Mandarin" / "Cantonese" / "English"
    prompt_vocal_sep,   # bool，参考音频声伴分离
    target_vocal_sep,   # bool，目标音频声伴分离
) -> (output_audio, prompt_metadata, target_metadata)
```

**实际 Gradio 函数签名**（SVC — `_start_svc`）:
```python
_start_svc(
    prompt_audio,       # 目标音色参考音频
    target_audio,       # 待转换的源歌曲音频
    prompt_vocal_sep,   # bool，参考音频声伴分离（默认 False）
    target_vocal_sep,   # bool，源音频声伴分离（默认 True）
    auto_shift,         # bool，自动音高偏移（默认 True）
    auto_mix_acc,       # bool，自动混合伴奏（默认 True）
    pitch_shift,        # int，手动音高偏移（-36 ~ 36）
    n_step,             # int，扩散步数（1~200，默认 32）
    cfg,                # float，CFG scale（0.0~10.0，默认 1.0）
    use_fp16,           # bool，使用 FP16 精度（默认 True）
    seed,               # int，随机种子（默认 42）
) -> output_audio
```

**客户端代码**:
```python
"""SoulX-Singer 歌声合成 + 歌声转换客户端"""

import os
from typing import Optional
from gradio_client import handle_file
from app.config import settings
from app.core.gradio_client import GradioSpaceClient


class SingerClient(GradioSpaceClient):

    def __init__(self):
        super().__init__(settings.SOUL_SINGER_SPACE)

    async def transcribe(
        self,
        prompt_audio_bytes: bytes,
        target_audio_bytes: bytes,
        prompt_lyric_lang: str = "Mandarin",
        target_lyric_lang: str = "Mandarin",
        prompt_vocal_sep: bool = False,
        target_vocal_sep: bool = True,
        prompt_metadata_bytes: Optional[bytes] = None,
        target_metadata_bytes: Optional[bytes] = None,
    ) -> tuple:
        """
        歌词转写 (独立预处理步骤)

        从音频中自动转写歌词并生成 metadata JSON。
        用户可下载 metadata → 用 MIDI Editor 编辑 → 再上传到 synthesize_singing。

        :param prompt_audio_bytes: 参考歌手音频
        :param target_audio_bytes: 目标音频
        :param prompt_lyric_lang: 参考音频歌词语言
        :param target_lyric_lang: 目标音频歌词语言
        :param prompt_vocal_sep: 参考音频声伴分离
        :param target_vocal_sep: 目标音频声伴分离
        :param prompt_metadata_bytes: 可选，已有 metadata（传入则跳过重新转写）
        :param target_metadata_bytes: 可选，已有 metadata
        :return: (prompt_metadata_bytes, target_metadata_bytes) 两个 JSON bytes
        """
        prompt_path = await self.save_temp_file(prompt_audio_bytes, ".wav")
        target_path = await self.save_temp_file(target_audio_bytes, ".wav")
        prompt_meta_path = None
        target_meta_path = None
        try:
            if prompt_metadata_bytes:
                prompt_meta_path = await self.save_temp_file(prompt_metadata_bytes, ".json")
            if target_metadata_bytes:
                target_meta_path = await self.save_temp_file(target_metadata_bytes, ".json")

            result = await self.call(
                api_name="/transcription_function",
                prompt_audio=handle_file(prompt_path),
                target_audio=handle_file(target_path),
                prompt_metadata=handle_file(prompt_meta_path) if prompt_meta_path else None,
                target_metadata=handle_file(target_meta_path) if target_meta_path else None,
                prompt_lyric_lang=prompt_lyric_lang,
                target_lyric_lang=target_lyric_lang,
                prompt_vocal_sep=prompt_vocal_sep,
                target_vocal_sep=target_vocal_sep,
            )
            # result = (prompt_metadata_path, target_metadata_path)
            p_bytes = await self.read_result_file(result[0]) if result[0] else None
            t_bytes = await self.read_result_file(result[1]) if result[1] else None
            return p_bytes, t_bytes
        finally:
            os.unlink(prompt_path)
            os.unlink(target_path)
            if prompt_meta_path:
                os.unlink(prompt_meta_path)
            if target_meta_path:
                os.unlink(target_meta_path)

    async def synthesize_singing(
        self,
        prompt_audio_bytes: bytes,
        target_audio_bytes: bytes,
        control: str = "melody",
        auto_shift: bool = True,
        pitch_shift: int = 0,
        seed: int = 12306,
        prompt_lyric_lang: str = "Mandarin",
        target_lyric_lang: str = "Mandarin",
        prompt_vocal_sep: bool = False,
        target_vocal_sep: bool = True,
        prompt_metadata_bytes: Optional[bytes] = None,
        target_metadata_bytes: Optional[bytes] = None,
    ) -> bytes:
        """
        歌声合成 (SVS)

        注意：输入是【两段音频】，不是歌词文本。
        - prompt_audio: 参考歌手音频（提供目标音色，max 30s）
        - target_audio: 旋律/歌词来源音频（模型自动转写歌词和提取旋律，max 60s）

        :param control: "melody"（F0 旋律控制）或 "score"（MIDI 乐谱控制）
        :param prompt_lyric_lang: 参考音频歌词语言 "Mandarin"/"Cantonese"/"English"
        :param target_lyric_lang: 目标音频歌词语言
        :param prompt_vocal_sep: 参考音频是否需要声伴分离
        :param target_vocal_sep: 目标音频是否需要声伴分离
        :param prompt_metadata_bytes: 可选，自定义 prompt metadata JSON
        :param target_metadata_bytes: 可选，自定义 target metadata JSON
        :return: 合成歌声 bytes (wav)
        """
        prompt_path = await self.save_temp_file(prompt_audio_bytes, ".wav")
        target_path = await self.save_temp_file(target_audio_bytes, ".wav")
        prompt_meta_path = None
        target_meta_path = None
        try:
            if prompt_metadata_bytes:
                prompt_meta_path = await self.save_temp_file(prompt_metadata_bytes, ".json")
            if target_metadata_bytes:
                target_meta_path = await self.save_temp_file(target_metadata_bytes, ".json")

            result = await self.call(
                api_name="/synthesis_function",
                prompt_audio=handle_file(prompt_path),
                target_audio=handle_file(target_path),
                prompt_metadata=handle_file(prompt_meta_path) if prompt_meta_path else None,
                target_metadata=handle_file(target_meta_path) if target_meta_path else None,
                control_radio=control,
                auto_shift=auto_shift,
                pitch_shift=pitch_shift,
                seed_input=seed,
                prompt_lyric_lang=prompt_lyric_lang,
                target_lyric_lang=target_lyric_lang,
                prompt_vocal_sep=prompt_vocal_sep,
                target_vocal_sep=target_vocal_sep,
            )
            # result 是 (output_audio, prompt_meta, target_meta) 元组
            output_path = result[0] if isinstance(result, (tuple, list)) else result
            return await self.read_result_file(output_path)
        finally:
            os.unlink(prompt_path)
            os.unlink(target_path)
            if prompt_meta_path:
                os.unlink(prompt_meta_path)
            if target_meta_path:
                os.unlink(target_meta_path)

    async def convert_voice(
        self,
        prompt_audio_bytes: bytes,
        target_audio_bytes: bytes,
        prompt_vocal_sep: bool = False,
        target_vocal_sep: bool = True,
        auto_shift: bool = True,
        auto_mix_acc: bool = True,
        pitch_shift: int = 0,
        n_step: int = 32,
        cfg: float = 1.0,
        use_fp16: bool = True,
        seed: int = 42,
    ) -> bytes:
        """
        歌声转换 (SVC)

        :param prompt_audio_bytes: 目标音色参考音频
        :param target_audio_bytes: 待转换的源歌曲音频
        :param prompt_vocal_sep: 参考音频声伴分离
        :param target_vocal_sep: 源音频声伴分离（默认 True，去除伴奏）
        :param auto_shift: 自动音高偏移
        :param auto_mix_acc: 自动混合伴奏到输出
        :param pitch_shift: 手动音高偏移（半音，-36 ~ 36）
        :param n_step: 扩散步数（越高质量越好但越慢，1~200）
        :param cfg: Classifier-Free Guidance scale（0.0~10.0）
        :param use_fp16: 使用半精度推理
        :param seed: 随机种子
        :return: 转换后歌声 bytes (wav)
        """
        prompt_path = await self.save_temp_file(prompt_audio_bytes, ".wav")
        target_path = await self.save_temp_file(target_audio_bytes, ".wav")
        try:
            result = await self.call(
                api_name="/_start_svc",
                prompt_audio=handle_file(prompt_path),
                target_audio=handle_file(target_path),
                prompt_vocal_sep=prompt_vocal_sep,
                target_vocal_sep=target_vocal_sep,
                auto_shift=auto_shift,
                auto_mix_acc=auto_mix_acc,
                pitch_shift=pitch_shift,
                n_step=n_step,
                cfg=cfg,
                use_fp16=use_fp16,
                seed=seed,
            )
            output_path = result if isinstance(result, str) else result[0]
            return await self.read_result_file(output_path)
        finally:
            os.unlink(prompt_path)
            os.unlink(target_path)


singer_client = SingerClient()
```

> ⚠️ **重要纠正**: SVS 的输入**不是歌词文本**，而是**两段音频**（prompt + target）。  
> 模型内部自动从 target_audio 转写歌词和提取旋律。  
> 如需精确控制，可通过 MIDI Editor 编辑 metadata JSON 后上传。

---

### 3.6 FlashHead 客户端 — `core/flashhead_client.py`

> **源码校验**: 基于 HF Space `gradio_app_streaming.py` 中 `run_inference_streaming` 实际签名

**实际 Gradio 函数签名**（来自源码）:
```python
run_inference_streaming(
    ckpt_dir,           # FlashHead 检查点目录（Space 内固定，用户无需传）
    wav2vec_dir,        # Wav2Vec 模型目录（Space 内固定）
    model_type,         # "pro" 或 "lite"（pro 更高质量，lite 更快）
    cond_image,         # 条件图片（人脸参考图）
    audio_path,         # 驱动音频
    seed,               # 随机种子（默认 9999）
    use_face_crop,      # bool，是否裁剪人脸区域（默认 False）
) -> 流式 yield 视频片段 (mp4)
```

> ⚠️ **特殊**: FlashHead 是**流式输出**（yield 多段视频片段），最终合并为完整 mp4。  
> 通过 `gradio_client` 调用时，SDK 自动等待全部片段完成后返回最终视频路径。

**客户端代码**:
```python
"""SoulX-FlashHead 数字人视频生成客户端"""

import os
from gradio_client import handle_file
from app.config import settings
from app.core.gradio_client import GradioSpaceClient


class FlashHeadClient(GradioSpaceClient):

    def __init__(self):
        super().__init__(settings.SOUL_FLASHHEAD_SPACE)

    async def generate_video(
        self,
        image_bytes: bytes,
        audio_bytes: bytes,
        model_type: str = "lite",
        seed: int = 9999,
        use_face_crop: bool = False,
    ) -> bytes:
        """
        数字人视频生成（音频驱动口型同步）

        :param image_bytes: 参考人脸图片 (jpg/png)
        :param audio_bytes: 驱动音频 (wav/mp3)
        :param model_type: "pro"（高质量，需更多 GPU）或 "lite"（实时级）
        :param seed: 随机种子
        :param use_face_crop: 是否自动裁剪人脸区域
        :return: 生成视频 bytes (mp4)
        """
        img_path = await self.save_temp_file(image_bytes, ".jpg")
        aud_path = await self.save_temp_file(audio_bytes, ".wav")
        try:
            # Space 内部固定的模型路径
            ckpt_dir = "models/SoulX-FlashHead-1_3B"
            wav2vec_dir = "models/wav2vec2-base-960h"

            result_path = await self.call(
                api_name="/run_inference_streaming",
                ckpt_dir=ckpt_dir,
                wav2vec_dir=wav2vec_dir,
                model_type=model_type,
                cond_image=handle_file(img_path),
                audio_path=handle_file(aud_path),
                seed=seed,
                use_face_crop=use_face_crop,
            )
            # 流式生成函数返回最后一个视频片段路径
            # gradio_client 会自动收集最终结果
            if isinstance(result_path, (list, tuple)):
                result_path = result_path[-1]
            return await self.read_result_file(result_path)
        finally:
            os.unlink(img_path)
            os.unlink(aud_path)


flashhead_client = FlashHeadClient()
```

> **model_type 选择建议**:
> - `"lite"`: 默认选择，实时推理速度，单 RTX-4090 支持 3 路并发
> - `"pro"`: 更高质量，需双 RTX-5090 + SageAttention 才能达到实时速度

---

### 3.7 统一任务模型 — `models/soul_task.py`

```python
"""Soul AI Lab 扩展功能的统一异步任务模型"""

from sqlalchemy import (
    Column, BigInteger, String, Text, Integer,
    DateTime, ForeignKey, Enum,
)
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class SoulTaskType(str, enum.Enum):
    podcast = "podcast"        # 播客语音合成
    singing_svs = "singing_svs"  # 歌声合成
    singing_svc = "singing_svc"  # 歌声转换
    digital_human = "digital_human"  # 数字人视频


class SoulTaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class SoulTask(Base):
    __tablename__ = "soul_tasks"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    task_type = Column(Enum(SoulTaskType), nullable=False, index=True)
    status = Column(Enum(SoulTaskStatus), default=SoulTaskStatus.pending, index=True)

    # 输入参数 (JSON 序列化存储)
    input_text = Column(Text)              # 文本/歌词
    input_params = Column(Text)            # JSON: dialect, control_mode 等

    # 输入文件
    ref_audio_url = Column(String(255))    # 说话人1/Prompt 参考音频
    ref_audio2_url = Column(String(255))   # 说话人2 参考音频 (Podcast 双人)
    ref_image_url = Column(String(255))    # 参考图片 (数字人)
    source_audio_url = Column(String(255)) # 目标/源音频 (Singer target_audio / SVC)
    midi_url = Column(String(255))         # MIDI 文件
    metadata_url = Column(String(255))     # metadata JSON 文件 (Singer)

    # 输出
    output_url = Column(String(255))       # 生成结果文件 URL
    output_size = Column(Integer)          # 文件大小 bytes
    output_format = Column(String(10))     # wav / mp4

    # 状态
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
```

> 设计说明：  
> - 用 `task_type` 区分不同功能，**一张表承载所有 Soul 扩展任务**  
> - 与现有 `tts_tasks` / `asr_tasks` 表并列，互不干扰  
> - 输入文件先上传到 `uploads/` 再存 URL，复用现有文件存储

---

### 3.8 请求/响应 Schema — `schemas/soul.py`

> 以下 Schema 与 3.4~3.6 中实际 Gradio 函数签名完全对齐

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ---- Podcast ----
# 文件字段 (spk1_prompt_audio, spk2_prompt_audio) 通过 UploadFile 传入
# 文本字段通过 Form() 传入

class PodcastResponse(BaseModel):
    task_id: int
    status: str
    class Config:
        from_attributes = True


# ---- Singer SVS ----
# 所有音频/文件字段通过 UploadFile 传入
# 控制参数通过 Form() 传入

class SVSResponse(BaseModel):
    task_id: int
    status: str
    class Config:
        from_attributes = True


# ---- Singer SVC ----
# prompt_audio + target_audio 通过 UploadFile 传入
# 高级参数通过 Form() 传入

class SVCResponse(BaseModel):
    task_id: int
    status: str
    class Config:
        from_attributes = True


# ---- Digital Human ----
# image + audio 通过 UploadFile 传入
# model_type, seed, use_face_crop 通过 Form() 传入

class DigitalHumanResponse(BaseModel):
    task_id: int
    status: str
    class Config:
        from_attributes = True


# ---- 通用任务详情 ----

class SoulTaskDetail(BaseModel):
    id: int
    task_type: str
    status: str
    input_text: Optional[str] = None
    input_params: Optional[str] = None
    ref_audio_url: Optional[str] = None
    ref_audio2_url: Optional[str] = None
    ref_image_url: Optional[str] = None
    source_audio_url: Optional[str] = None
    output_url: Optional[str] = None
    output_size: Optional[int] = None
    output_format: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

---

### 3.9 路由设计 — `api/v1/podcast.py`

> 已对齐实际 `dialogue_synthesis_function` 签名：双说话人独立参考音频+文本+方言

```python
"""SoulX-Podcast 播客语音合成路由"""

import json
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus
from app.schemas.soul import PodcastResponse, SoulTaskDetail
from app.api.v1.auth import get_current_user
from app.core.podcast_client import podcast_client
from app.api.v1.tts import save_audio_file
from app.config import settings
from loguru import logger
from datetime import datetime

router = APIRouter()


async def _save_upload(content: bytes, suffix: str) -> tuple:
    """保存上传文件，返回 (filepath, url)"""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{suffix}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath, f"/uploads/{filename}"


async def process_podcast_task(
    task_id: int,
    target_text: str,
    spk1_audio_path: str,
    spk1_prompt_text: str,
    spk1_dialect_prompt_text: str,
    spk2_audio_path: Optional[str],
    spk2_prompt_text: str,
    spk2_dialect_prompt_text: str,
    seed: int,
):
    """后台执行播客语音合成"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = SoulTaskStatus.processing
            await db.commit()

            with open(spk1_audio_path, "rb") as f:
                spk1_bytes = f.read()
            spk2_bytes = None
            if spk2_audio_path:
                with open(spk2_audio_path, "rb") as f:
                    spk2_bytes = f.read()

            audio_bytes = await podcast_client.synthesize(
                target_text=target_text,
                spk1_prompt_audio_bytes=spk1_bytes,
                spk1_prompt_text=spk1_prompt_text,
                spk1_dialect_prompt_text=spk1_dialect_prompt_text,
                spk2_prompt_audio_bytes=spk2_bytes,
                spk2_prompt_text=spk2_prompt_text,
                spk2_dialect_prompt_text=spk2_dialect_prompt_text,
                seed=seed,
            )

            audio_url = await save_audio_file(audio_bytes, "wav")
            task.output_url = audio_url
            task.output_size = len(audio_bytes)
            task.output_format = "wav"
            task.status = SoulTaskStatus.completed
            task.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.error(f"Podcast task {task_id} failed: {e}")
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/synthesize", response_model=PodcastResponse)
async def synthesize_podcast(
    background_tasks: BackgroundTasks,
    # ---- 对话文本 ----
    target_text: str = Form(..., min_length=1, max_length=10000,
        description='对话文本，格式 "[S1]xxx\\n[S2]xxx"，支持 [S1]~[S4]'),
    # ---- 说话人1 ----
    spk1_prompt_audio: UploadFile = File(..., description="说话人1 参考音频"),
    spk1_prompt_text: str = Form(default="", description="说话人1 参考文本（对应音频的文字内容）"),
    spk1_dialect_prompt_text: str = Form(default="",
        description='说话人1 方言提示，如 "<|Sichuan|>四川话文本"'),
    # ---- 说话人2（可选，独白可不传）----
    spk2_prompt_audio: Optional[UploadFile] = File(None, description="说话人2 参考音频"),
    spk2_prompt_text: str = Form(default="", description="说话人2 参考文本"),
    spk2_dialect_prompt_text: str = Form(default="",
        description='说话人2 方言提示'),
    # ---- 控制参数 ----
    seed: int = Form(default=1988, description="随机种子"),
    # ---- 鉴权 & DB ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交播客语音合成任务（支持双说话人独立配置）"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    # 保存说话人1 音频
    spk1_content = await spk1_prompt_audio.read()
    spk1_path, spk1_url = await _save_upload(spk1_content, ".wav")

    # 保存说话人2 音频（可选）
    spk2_path, spk2_url = None, None
    if spk2_prompt_audio:
        spk2_content = await spk2_prompt_audio.read()
        spk2_path, spk2_url = await _save_upload(spk2_content, ".wav")

    params = json.dumps({
        "spk1_prompt_text": spk1_prompt_text,
        "spk1_dialect_prompt_text": spk1_dialect_prompt_text,
        "spk2_prompt_text": spk2_prompt_text,
        "spk2_dialect_prompt_text": spk2_dialect_prompt_text,
        "seed": seed,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.podcast,
        status=SoulTaskStatus.pending,
        input_text=target_text,
        input_params=params,
        ref_audio_url=spk1_url,
        ref_audio2_url=spk2_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_podcast_task, task.id, target_text,
        spk1_path, spk1_prompt_text, spk1_dialect_prompt_text,
        spk2_path, spk2_prompt_text, spk2_dialect_prompt_text, seed,
    )
    return PodcastResponse(task_id=task.id, status=task.status.value)


@router.get("/tasks", response_model=List[SoulTaskDetail])
async def get_podcast_tasks(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask)
        .where(SoulTask.user_id == current_user.id, SoulTask.task_type == SoulTaskType.podcast)
        .order_by(desc(SoulTask.created_at))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=SoulTaskDetail)
async def get_podcast_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask).where(SoulTask.id == task_id, SoulTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/health")
async def podcast_health():
    """检查 Podcast Space 是否在线"""
    online = await podcast_client.health_check()
    return {"space": settings.SOUL_PODCAST_SPACE, "online": online}
```

---

### 3.10 路由设计 — `api/v1/singing.py`

> 已对齐实际源码：SVS 输入是两段音频（prompt + target），不是歌词文本；SVC 包含完整高级参数

```python
"""SoulX-Singer 歌声合成 + 歌声转换路由"""

import json
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus
from app.schemas.soul import SVSResponse, SVCResponse, SoulTaskDetail
from app.api.v1.auth import get_current_user
from app.core.singer_client import singer_client
from app.api.v1.tts import save_audio_file
from app.config import settings
from loguru import logger
from datetime import datetime

router = APIRouter()


async def _save_upload(file: UploadFile, suffix: str) -> tuple:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{suffix}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())
    return filepath, f"/uploads/{filename}"


async def process_svs_task(
    task_id: int,
    prompt_path: str, target_path: str,
    control: str, auto_shift: bool, pitch_shift: int, seed: int,
    prompt_lyric_lang: str, target_lyric_lang: str,
    prompt_vocal_sep: bool, target_vocal_sep: bool,
    prompt_meta_path: Optional[str], target_meta_path: Optional[str],
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = SoulTaskStatus.processing
            await db.commit()

            with open(prompt_path, "rb") as f:
                prompt_bytes = f.read()
            with open(target_path, "rb") as f:
                target_bytes = f.read()
            prompt_meta_bytes = open(prompt_meta_path, "rb").read() if prompt_meta_path else None
            target_meta_bytes = open(target_meta_path, "rb").read() if target_meta_path else None

            audio_bytes = await singer_client.synthesize_singing(
                prompt_audio_bytes=prompt_bytes,
                target_audio_bytes=target_bytes,
                control=control,
                auto_shift=auto_shift,
                pitch_shift=pitch_shift,
                seed=seed,
                prompt_lyric_lang=prompt_lyric_lang,
                target_lyric_lang=target_lyric_lang,
                prompt_vocal_sep=prompt_vocal_sep,
                target_vocal_sep=target_vocal_sep,
                prompt_metadata_bytes=prompt_meta_bytes,
                target_metadata_bytes=target_meta_bytes,
            )
            audio_url = await save_audio_file(audio_bytes, "wav")
            task.output_url = audio_url
            task.output_size = len(audio_bytes)
            task.output_format = "wav"
            task.status = SoulTaskStatus.completed
            task.completed_at = datetime.utcnow()
            await db.commit()
        except Exception as e:
            logger.error(f"SVS task {task_id} failed: {e}")
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


async def process_svc_task(
    task_id: int,
    prompt_path: str, target_path: str,
    prompt_vocal_sep: bool, target_vocal_sep: bool,
    auto_shift: bool, auto_mix_acc: bool, pitch_shift: int,
    n_step: int, cfg: float, use_fp16: bool, seed: int,
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = SoulTaskStatus.processing
            await db.commit()

            with open(prompt_path, "rb") as f:
                prompt_bytes = f.read()
            with open(target_path, "rb") as f:
                target_bytes = f.read()

            audio_bytes = await singer_client.convert_voice(
                prompt_audio_bytes=prompt_bytes,
                target_audio_bytes=target_bytes,
                prompt_vocal_sep=prompt_vocal_sep,
                target_vocal_sep=target_vocal_sep,
                auto_shift=auto_shift,
                auto_mix_acc=auto_mix_acc,
                pitch_shift=pitch_shift,
                n_step=n_step,
                cfg=cfg,
                use_fp16=use_fp16,
                seed=seed,
            )
            audio_url = await save_audio_file(audio_bytes, "wav")
            task.output_url = audio_url
            task.output_size = len(audio_bytes)
            task.output_format = "wav"
            task.status = SoulTaskStatus.completed
            task.completed_at = datetime.utcnow()
            await db.commit()
        except Exception as e:
            logger.error(f"SVC task {task_id} failed: {e}")
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/transcribe")
async def singing_transcription(
    background_tasks: BackgroundTasks,
    prompt_audio: UploadFile = File(..., description="参考歌手音频"),
    target_audio: UploadFile = File(..., description="目标音频"),
    prompt_lyric_lang: str = Form(default="Mandarin"),
    target_lyric_lang: str = Form(default="Mandarin"),
    prompt_vocal_sep: bool = Form(default=False),
    target_vocal_sep: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    歌词转写（独立预处理步骤）
    返回自动转写的 metadata JSON，用户可下载编辑后再上传到 /svs 精确合成。
    注意：这是同步接口，不走后台任务（转写耗时较短）。
    """
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    prompt_content = await prompt_audio.read()
    target_content = await target_audio.read()

    prompt_meta, target_meta = await singer_client.transcribe(
        prompt_audio_bytes=prompt_content,
        target_audio_bytes=target_content,
        prompt_lyric_lang=prompt_lyric_lang,
        target_lyric_lang=target_lyric_lang,
        prompt_vocal_sep=prompt_vocal_sep,
        target_vocal_sep=target_vocal_sep,
    )

    from fastapi.responses import JSONResponse
    import base64
    return JSONResponse({
        "prompt_metadata": base64.b64encode(prompt_meta).decode() if prompt_meta else None,
        "target_metadata": base64.b64encode(target_meta).decode() if target_meta else None,
    })


@router.post("/svs", response_model=SVSResponse)
async def singing_voice_synthesis(
    background_tasks: BackgroundTasks,
    # ---- 两段音频（核心输入）----
    prompt_audio: UploadFile = File(..., description="参考歌手音频（目标音色，max 30s）"),
    target_audio: UploadFile = File(..., description="旋律/歌词来源音频（max 60s）"),
    # ---- 控制参数 ----
    control: str = Form(default="melody", description='"melody"(F0旋律) 或 "score"(MIDI乐谱)'),
    auto_shift: bool = Form(default=True, description="自动音高偏移"),
    pitch_shift: int = Form(default=0, ge=-36, le=36, description="手动音高偏移（半音）"),
    seed: int = Form(default=12306),
    prompt_lyric_lang: str = Form(default="Mandarin",
        description='"Mandarin" / "Cantonese" / "English"'),
    target_lyric_lang: str = Form(default="Mandarin"),
    prompt_vocal_sep: bool = Form(default=False, description="参考音频声伴分离"),
    target_vocal_sep: bool = Form(default=True, description="目标音频声伴分离"),
    # ---- 可选 metadata（精确控制歌词+旋律对齐）----
    prompt_metadata: Optional[UploadFile] = File(None, description="Prompt metadata JSON"),
    target_metadata: Optional[UploadFile] = File(None, description="Target metadata JSON"),
    # ---- 鉴权 ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """歌声合成 (SVS) — 输入两段音频，模型自动转写歌词和提取旋律"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    prompt_path, prompt_url = await _save_upload(prompt_audio, ".wav")
    target_path, target_url = await _save_upload(target_audio, ".wav")
    prompt_meta_path = (await _save_upload(prompt_metadata, ".json"))[0] if prompt_metadata else None
    target_meta_path = (await _save_upload(target_metadata, ".json"))[0] if target_metadata else None

    params = json.dumps({
        "control": control, "auto_shift": auto_shift, "pitch_shift": pitch_shift,
        "seed": seed, "prompt_lyric_lang": prompt_lyric_lang,
        "target_lyric_lang": target_lyric_lang,
        "prompt_vocal_sep": prompt_vocal_sep, "target_vocal_sep": target_vocal_sep,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.singing_svs,
        status=SoulTaskStatus.pending,
        input_params=params,
        ref_audio_url=prompt_url,
        source_audio_url=target_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_svs_task, task.id,
        prompt_path, target_path, control, auto_shift, pitch_shift, seed,
        prompt_lyric_lang, target_lyric_lang, prompt_vocal_sep, target_vocal_sep,
        prompt_meta_path, target_meta_path,
    )
    return SVSResponse(task_id=task.id, status=task.status.value)


@router.post("/svc", response_model=SVCResponse)
async def singing_voice_conversion(
    background_tasks: BackgroundTasks,
    # ---- 两段音频 ----
    prompt_audio: UploadFile = File(..., description="目标音色参考音频"),
    target_audio: UploadFile = File(..., description="待转换的源歌曲音频"),
    # ---- 高级参数 ----
    prompt_vocal_sep: bool = Form(default=False),
    target_vocal_sep: bool = Form(default=True, description="源音频声伴分离"),
    auto_shift: bool = Form(default=True, description="自动音高偏移"),
    auto_mix_acc: bool = Form(default=True, description="自动混合伴奏到输出"),
    pitch_shift: int = Form(default=0, ge=-36, le=36),
    n_step: int = Form(default=32, ge=1, le=200, description="扩散步数"),
    cfg: float = Form(default=1.0, ge=0.0, le=10.0, description="CFG scale"),
    use_fp16: bool = Form(default=True),
    seed: int = Form(default=42),
    # ---- 鉴权 ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """歌声转换 (SVC) — 音频到音频的音色转换"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    prompt_path, prompt_url = await _save_upload(prompt_audio, ".wav")
    target_path, target_url = await _save_upload(target_audio, ".wav")

    params = json.dumps({
        "prompt_vocal_sep": prompt_vocal_sep, "target_vocal_sep": target_vocal_sep,
        "auto_shift": auto_shift, "auto_mix_acc": auto_mix_acc,
        "pitch_shift": pitch_shift, "n_step": n_step, "cfg": cfg,
        "use_fp16": use_fp16, "seed": seed,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.singing_svc,
        status=SoulTaskStatus.pending,
        input_params=params,
        ref_audio_url=prompt_url,
        source_audio_url=target_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_svc_task, task.id,
        prompt_path, target_path,
        prompt_vocal_sep, target_vocal_sep, auto_shift, auto_mix_acc,
        pitch_shift, n_step, cfg, use_fp16, seed,
    )
    return SVCResponse(task_id=task.id, status=task.status.value)


@router.get("/tasks", response_model=List[SoulTaskDetail])
async def get_singing_tasks(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask)
        .where(
            SoulTask.user_id == current_user.id,
            SoulTask.task_type.in_([SoulTaskType.singing_svs, SoulTaskType.singing_svc]),
        )
        .order_by(desc(SoulTask.created_at))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=SoulTaskDetail)
async def get_singing_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask).where(SoulTask.id == task_id, SoulTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

---

### 3.11 路由设计 — `api/v1/digital_human.py`

> 已对齐实际 `run_inference_streaming` 签名：新增 model_type、seed、use_face_crop

```python
"""SoulX-FlashHead 数字人视频生成路由"""

import json
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus
from app.schemas.soul import DigitalHumanResponse, SoulTaskDetail
from app.api.v1.auth import get_current_user
from app.core.flashhead_client import flashhead_client
from app.config import settings
from loguru import logger
from datetime import datetime

router = APIRouter()


async def _save_upload(content: bytes, suffix: str) -> tuple:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{suffix}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath, f"/uploads/{filename}"


async def process_dh_task(
    task_id: int, img_path: str, aud_path: str,
    model_type: str, seed: int, use_face_crop: bool,
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = SoulTaskStatus.processing
            await db.commit()

            with open(img_path, "rb") as f:
                img_bytes = f.read()
            with open(aud_path, "rb") as f:
                aud_bytes = f.read()

            video_bytes = await flashhead_client.generate_video(
                image_bytes=img_bytes,
                audio_bytes=aud_bytes,
                model_type=model_type,
                seed=seed,
                use_face_crop=use_face_crop,
            )

            # 保存视频文件
            video_filename = f"{uuid.uuid4()}.mp4"
            video_filepath = os.path.join(settings.UPLOAD_DIR, video_filename)
            with open(video_filepath, "wb") as f:
                f.write(video_bytes)

            task.output_url = f"/uploads/{video_filename}"
            task.output_size = len(video_bytes)
            task.output_format = "mp4"
            task.status = SoulTaskStatus.completed
            task.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.error(f"Digital human task {task_id} failed: {e}")
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/generate", response_model=DigitalHumanResponse)
async def generate_digital_human(
    background_tasks: BackgroundTasks,
    # ---- 核心输入 ----
    image: UploadFile = File(..., description="参考人脸图片 (jpg/png)"),
    audio: UploadFile = File(..., description="驱动音频 (wav/mp3)"),
    # ---- 生成参数 ----
    model_type: str = Form(default="lite",
        description='"lite"（实时级，单4090）或 "pro"（高质量，需双5090）'),
    seed: int = Form(default=9999, description="随机种子"),
    use_face_crop: bool = Form(default=False, description="是否自动裁剪人脸区域"),
    # ---- 鉴权 ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成数字人口型同步视频（音频驱动，流式生成）"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    img_content = await image.read()
    aud_content = await audio.read()
    img_path, img_url = await _save_upload(img_content, ".jpg")
    aud_path, aud_url = await _save_upload(aud_content, ".wav")

    params = json.dumps({
        "model_type": model_type, "seed": seed, "use_face_crop": use_face_crop,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.digital_human,
        status=SoulTaskStatus.pending,
        input_params=params,
        ref_image_url=img_url,
        ref_audio_url=aud_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_dh_task, task.id, img_path, aud_path, model_type, seed, use_face_crop,
    )
    return DigitalHumanResponse(task_id=task.id, status=task.status.value)


@router.get("/tasks", response_model=List[SoulTaskDetail])
async def get_dh_tasks(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask)
        .where(
            SoulTask.user_id == current_user.id,
            SoulTask.task_type == SoulTaskType.digital_human,
        )
        .order_by(desc(SoulTask.created_at))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=SoulTaskDetail)
async def get_dh_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask).where(SoulTask.id == task_id, SoulTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

---

### 3.12 注册路由 — `main.py` 改动

```python
# main.py 只需新增 3 行 import + 3 行 include_router

from app.api.v1 import tts, asr, voice_models, users, auth, chat
from app.api.v1 import podcast, singing, digital_human  # +1 行

# ... 现有路由注册 ...

app.include_router(podcast.router, prefix=f"{settings.API_V1_PREFIX}/podcast", tags=["Podcast"])
app.include_router(singing.router, prefix=f"{settings.API_V1_PREFIX}/singing", tags=["Singing"])
app.include_router(digital_human.router, prefix=f"{settings.API_V1_PREFIX}/digital-human", tags=["Digital Human"])
```

---

## 四、API 接口总览

### 新增 API（已对齐实际 Gradio 源码签名）

| 方法 | 路径 | 功能 | 核心输入 | 输出 |
|------|------|------|---------|------|
| POST | `/api/v1/podcast/synthesize` | 播客语音合成 | Form: target_text, spk1/2_prompt_text, spk1/2_dialect, seed + File: spk1/2_prompt_audio | `{task_id, status}` |
| GET | `/api/v1/podcast/tasks` | 播客任务列表 | query: skip, limit | `[SoulTaskDetail]` |
| GET | `/api/v1/podcast/tasks/{id}` | 播客任务详情 | — | `SoulTaskDetail` |
| GET | `/api/v1/podcast/health` | 空间健康检查 | — | `{online: bool}` |
| POST | `/api/v1/singing/transcribe` | 歌词转写 | File: prompt_audio, target_audio + Form: lyric_lang, vocal_sep | `{prompt_metadata, target_metadata}` (base64 JSON) |
| POST | `/api/v1/singing/svs` | 歌声合成 | File: prompt_audio, target_audio + Form: control, auto_shift, pitch_shift, seed, lyric_lang, vocal_sep + File(可选): metadata | `{task_id, status}` |
| POST | `/api/v1/singing/svc` | 歌声转换 | File: prompt_audio, target_audio + Form: vocal_sep, auto_shift, auto_mix_acc, pitch_shift, n_step, cfg, seed | `{task_id, status}` |
| GET | `/api/v1/singing/tasks` | 歌声任务列表 | query: skip, limit | `[SoulTaskDetail]` |
| GET | `/api/v1/singing/tasks/{id}` | 歌声任务详情 | — | `SoulTaskDetail` |
| GET | `/api/v1/singing/health` | Singer Space 健康检查 | — | `{online: bool}` |
| POST | `/api/v1/digital-human/generate` | 数字人视频生成 | File: image, audio + Form: model_type(lite/pro), seed, use_face_crop | `{task_id, status}` |
| GET | `/api/v1/digital-human/tasks` | 数字人任务列表 | query: skip, limit | `[SoulTaskDetail]` |
| GET | `/api/v1/digital-human/tasks/{id}` | 数字人任务详情 | — | `SoulTaskDetail` |
| GET | `/api/v1/digital-human/health` | FlashHead Space 健康检查 | — | `{online: bool}` |

### 前端轮询流程（与现有 TTS 一致）

```
1. POST /podcast/synthesize → 返回 task_id
2. 每 2s GET /podcast/tasks/{task_id}
3. status == "completed" → 取 output_url 播放/下载
4. status == "failed" → 显示 error_message
```

---

## 五、数据库变更

仅新增一张表 `soul_tasks`，**不修改任何现有表**。

```sql
CREATE TABLE soul_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    task_type ENUM('podcast','singing_svs','singing_svc','digital_human') NOT NULL,
    status ENUM('pending','processing','completed','failed') DEFAULT 'pending',
    input_text TEXT,
    input_params TEXT,
    ref_audio_url VARCHAR(255),
    ref_audio2_url VARCHAR(255),
    ref_image_url VARCHAR(255),
    source_audio_url VARCHAR(255),
    midi_url VARCHAR(255),
    metadata_url VARCHAR(255),
    output_url VARCHAR(255),
    output_size INT,
    output_format VARCHAR(10),
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    INDEX idx_user_type (user_id, task_type),
    INDEX idx_status (status),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4;
```

> 表会在应用启动时由 `Base.metadata.create_all` 自动创建，无需手动执行 SQL。

---

## 六、前端扩展方案

### 6.1 新增页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 播客语音 | `/podcast` | 双说话人参考音频+文本+方言 → 合成对话播客 |
| AI 歌声 | `/singing` | SVS（双音频+控制参数）+ SVC（音色转换+高级参数）双标签页 |
| 数字人 | `/digital-human` | 上传照片 + 音频 + model_type/seed → 生成视频 |

### 6.2 左侧菜单扩展

```
📌 现有菜单
├── 💬 AI 对话
├── 🔊 TTS 语音合成
├── 🎤 语音识别
├── 🎭 音色管理
│
📌 新增菜单（Soul AI 扩展）
├── 🎙️ 播客语音  [新增]
├── 🎵 AI 歌声   [新增]
└── 👤 数字人     [新增]
```

### 6.3 前端关键组件

```
frontend/src/views/
├── podcast/
│   └── PodcastView.vue     # 播客语音页
├── singing/
│   └── SingingView.vue     # 歌声合成页（SVS + SVC 标签页）
└── digital-human/
    └── DigitalHumanView.vue  # 数字人页
```

每个页面的前端交互逻辑与现有 TTS 页面一致：
1. 表单提交 → `POST /api/v1/xxx/synthesize`
2. 拿到 `task_id` 后启动定时器轮询
3. 完成后展示播放器（音频/视频）

---

## 七、改动量统计

| 类别 | 文件 | 改动类型 | 行数估算 |
|------|------|---------|---------|
| **config.py** | 1 | 修改 | +6 行 |
| **main.py** | 1 | 修改 | +4 行 |
| **requirements.txt** | 1 | 修改 | +1 行 |
| **.env** | 1 | 修改 | +6 行 |
| **core/gradio_client.py** | 1 | 新增 | ~60 行 |
| **core/podcast_client.py** | 1 | 新增 | ~45 行 |
| **core/singer_client.py** | 1 | 新增 | ~80 行 |
| **core/flashhead_client.py** | 1 | 新增 | ~40 行 |
| **models/soul_task.py** | 1 | 新增 | ~45 行 |
| **schemas/soul.py** | 1 | 新增 | ~55 行 |
| **api/v1/podcast.py** | 1 | 新增 | ~90 行 |
| **api/v1/singing.py** | 1 | 新增 | ~130 行 |
| **api/v1/digital_human.py** | 1 | 新增 | ~100 行 |
| **前端 3 个页面** | 3 | 新增 | 各 ~150 行 |
| **合计** | **16 文件** | **4 修改 + 12 新增** | **~1200 行** |

> **现有文件仅修改 4 个，每个改动不超过 6 行，零侵入。**

---

## 八、实施顺序

```
Day 1:  基础设施
        ├─ gradio_client.py (通用基类)
        ├─ models/soul_task.py
        ├─ schemas/soul.py
        ├─ config.py + .env 配置
        └─ requirements.txt + pip install

Day 2:  Phase 1 — Podcast 集成
        ├─ podcast_client.py
        ├─ api/v1/podcast.py
        ├─ main.py 注册路由
        └─ Swagger 测试验证

Day 3:  Phase 2 — Singer 集成
        ├─ singer_client.py
        ├─ api/v1/singing.py
        └─ Swagger 测试验证

Day 4:  Phase 3 — FlashHead 集成
        ├─ flashhead_client.py
        ├─ api/v1/digital_human.py
        └─ Swagger 测试验证

Day 5-7: 前端页面
        ├─ PodcastView.vue
        ├─ SingingView.vue
        ├─ DigitalHumanView.vue
        └─ 路由 + 菜单注册
```

---

## 九、Soul-AILab 全资源审计与覆盖状态

> 截至 2026-04-23，Soul-AILab 组织下共 **5 个 Space** + **10 个 Model** + **3 个 Dataset**

### 9.1 已覆盖（本文档方案，通过 `gradio_client` 集成）

| 资源 | 类型 | API 端点数 | 状态 |
|------|------|-----------|------|
| **SoulX-Podcast-1.7B** | HF Space (Gradio) | 1 (`dialogue_synthesis_function`) | ✅ 完整覆盖 |
| **SoulX-Podcast-1.7B-Dialect** | HF Space (Gradio) | 1（同上，API 签名完全相同） | ✅ 通过配置 `SOUL_PODCAST_SPACE` 切换 |
| **SoulX-Singer** (SVS+SVC) | HF Space (Gradio) | 3 (`transcription_function` + `synthesis_function` + `_start_svc`) | ✅ 完整覆盖 |
| **SoulX-FlashHead** | HF Space (Gradio) | 1 (`run_inference_streaming`) | ✅ 完整覆盖 |
| **SoulX-Singer-Midi-Editor** | HF Space (静态前端) | 0（纯 React/TS 前端，无后端 API） | ✅ 前端 iframe/链接集成，配置项 `SOUL_MIDI_EDITOR_URL` |

### 9.2 暂不可集成（无在线 Gradio Space）

| 资源 | 原因 | 备注 |
|------|------|------|
| **SoulX-FlashTalk-14B** | 无 HF Space（"Coming Soon"），需 64G+ VRAM 单卡或 8×H800 | 待官方上线 Space 后可立即集成（API 模式与 FlashHead 类似） |
| **LiveAct** | 无 HF Space，需 2×H100/H200，仅有本地 CLI + GUI demo | 待官方上线 Space 后集成 |
| **SoulX-Duplug-0.6B** | WebSocket 流式协议（非 Gradio），在线 Demo 在第三方域名 | 集成需自建 WebSocket 代理，架构与 Gradio 方案不同，建议作为独立模块 |
| **SoulX-DuoVoice** | ❌ 闭源（仅 Soul App 内测） | 不可用 |
| **SoulX-Singer-Preprocess** | 预处理模型，已内嵌于 Singer Space | 无需单独集成 |
| **SAC-16k-62_5Hz / 37_5Hz** | 音频编解码器底层组件 | 基础设施模型，不面向终端用户 |

### 9.3 后续演进路线

| 阶段 | 内容 |
|------|------|
| **v1.0** | HF Space 在线转发（本文档方案），覆盖 5 个 Gradio API 端点 |
| **v1.1** | 增加 Redis 任务队列 + 速率限制 |
| **v1.2** | Singer 页面集成 MIDI Editor（iframe 嵌入 + metadata 编辑工作流） |
| **v2.0** | 本地部署 FlashHead Lite (RTX 4090)，替换 HF Space 调用，路由层不变 |
| **v2.1** | 本地部署 Podcast (vLLM + Docker) |
| **v2.2** | FlashTalk Space 上线后接入（复用 FlashHead 客户端模式） |
| **v3.0** | TTS 页面统一引擎选择（Fish Audio / Podcast / Singer），前端无感切换 |
| **v3.1** | Duplug WebSocket 全双工对话集成（独立模块） |

---

*本文档所有代码均基于 ttsapp 现有架构模式设计，可直接按文件创建实施。*
*API 覆盖率：Soul-AILab 全部 5 个 Gradio API 端点 / 5 个已覆盖 = **100%**。*
