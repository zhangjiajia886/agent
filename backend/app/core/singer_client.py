"""SoulX-Singer 歌声合成客户端

实际 Singer Gradio API 端点（通过 view_api() 确认）：
  /_transcribe_prompt(prompt_audio, prompt_metadata, prompt_lyric_lang, prompt_vocal_sep)
      → (prompt_元数据, prompt_midi)
  /_transcribe_target(target_audio, target_metadata, target_lyric_lang, target_vocal_sep)
      → (target_元数据, target_midi, value_28)
  /_run_synthesis(prompt_audio, prompt_metadata, target_metadata, control, auto_shift, pitch_shift, seed)
      → 合成结果音频

参数类型注意：
  control    : 'melody-controlled' 或 'score-controlled'（非 'melody'/'score'）
  auto_shift : 'yes' 或 'no'（非 bool）
  vocal_sep  : 'yes' 或 'no'（非 bool）
"""

import asyncio
import os
import subprocess
import tempfile
from typing import Optional
from gradio_client import handle_file
from app.config import settings
from app.core.gradio_client import GradioSpaceClient
from loguru import logger

_CONTROL_MAP = {
    "melody": "melody-controlled",
    "score": "score-controlled",
    "melody-controlled": "melody-controlled",
    "score-controlled": "score-controlled",
}


class SingerClient(GradioSpaceClient):

    def __init__(self):
        super().__init__(settings.SOUL_SINGER_SPACE)

    async def _save_audio_as_wav(self, audio_bytes: bytes) -> str:
        """保存音频为 WAV 格式，自动转换 WebM/MP4/OGG 等浏览器录音格式"""
        loop = asyncio.get_event_loop()

        def _convert() -> str:
            is_wav = len(audio_bytes) >= 12 and audio_bytes[:4] == b'RIFF' and audio_bytes[8:12] == b'WAVE'
            if is_wav:
                fd, path = tempfile.mkstemp(suffix=".wav")
                os.write(fd, audio_bytes)
                os.close(fd)
                return path

            fd_src, src_path = tempfile.mkstemp(suffix=".audio")
            os.write(fd_src, audio_bytes)
            os.close(fd_src)
            fd_dst, dst_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd_dst)
            try:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", src_path,
                     "-ar", "44100", "-ac", "1", "-f", "wav", dst_path],
                    capture_output=True, timeout=60,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"音频格式转换失败（非 WAV 输入需要 ffmpeg）: "
                        f"{result.stderr.decode(errors='replace')[:300]}"
                    )
                logger.info(f"Singer 音频格式转换完成 src={src_path} dst={dst_path}")
                return dst_path
            finally:
                os.unlink(src_path)

        return await loop.run_in_executor(None, _convert)

    async def _transcribe_prompt(
        self,
        prompt_audio_bytes: bytes,
        prompt_lyric_lang: str = "Mandarin",
        prompt_vocal_sep: bool = False,
        prompt_metadata_bytes: Optional[bytes] = None,
    ) -> Optional[bytes]:
        """转写参考音频 → prompt metadata JSON bytes"""
        prompt_path = await self._save_audio_as_wav(prompt_audio_bytes)
        prompt_meta_path = None
        try:
            if prompt_metadata_bytes:
                prompt_meta_path = await self.save_temp_file(prompt_metadata_bytes, ".json")
            result = await self.call(
                api_name="/_transcribe_prompt",
                prompt_audio=handle_file(prompt_path),
                prompt_metadata=handle_file(prompt_meta_path) if prompt_meta_path else None,
                prompt_lyric_lang=prompt_lyric_lang,
                prompt_vocal_sep="yes" if prompt_vocal_sep else "no",
            )
            return await self.read_result_file(result[0]) if result[0] else None
        finally:
            os.unlink(prompt_path)
            if prompt_meta_path:
                os.unlink(prompt_meta_path)

    async def _transcribe_target(
        self,
        target_audio_bytes: bytes,
        target_lyric_lang: str = "Mandarin",
        target_vocal_sep: bool = True,
        target_metadata_bytes: Optional[bytes] = None,
    ) -> Optional[bytes]:
        """转写目标音频 → target metadata JSON bytes"""
        target_path = await self._save_audio_as_wav(target_audio_bytes)
        target_meta_path = None
        try:
            if target_metadata_bytes:
                target_meta_path = await self.save_temp_file(target_metadata_bytes, ".json")
            result = await self.call(
                api_name="/_transcribe_target",
                target_audio=handle_file(target_path),
                target_metadata=handle_file(target_meta_path) if target_meta_path else None,
                target_lyric_lang=target_lyric_lang,
                target_vocal_sep="yes" if target_vocal_sep else "no",
            )
            return await self.read_result_file(result[0]) if result[0] else None
        finally:
            os.unlink(target_path)
            if target_meta_path:
                os.unlink(target_meta_path)

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
        歌词转写（独立预处理步骤）

        分别调用 /_transcribe_prompt 和 /_transcribe_target，
        返回 (prompt_metadata_bytes, target_metadata_bytes)。
        """
        p_bytes = await self._transcribe_prompt(
            prompt_audio_bytes=prompt_audio_bytes,
            prompt_lyric_lang=prompt_lyric_lang,
            prompt_vocal_sep=prompt_vocal_sep,
            prompt_metadata_bytes=prompt_metadata_bytes,
        )
        t_bytes = await self._transcribe_target(
            target_audio_bytes=target_audio_bytes,
            target_lyric_lang=target_lyric_lang,
            target_vocal_sep=target_vocal_sep,
            target_metadata_bytes=target_metadata_bytes,
        )
        return p_bytes, t_bytes

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

        工作流：先对两段音频分别转写（如未提供 metadata），再调用 /_run_synthesis 合成。

        :param control: "melody" 或 "score"（内部自动映射为 API 要求的格式）
        :param prompt_lyric_lang: 参考音频歌词语言，仅在需要转写时生效
        :param target_lyric_lang: 目标音频歌词语言，仅在需要转写时生效
        :param prompt_vocal_sep: 参考音频是否声伴分离，仅在需要转写时生效
        :param target_vocal_sep: 目标音频是否声伴分离，仅在需要转写时生效
        :param prompt_metadata_bytes: 已有 prompt metadata（跳过重新转写）
        :param target_metadata_bytes: 已有 target metadata（跳过重新转写）
        :return: 合成歌声 bytes (wav)
        """
        if prompt_metadata_bytes is None:
            prompt_metadata_bytes = await self._transcribe_prompt(
                prompt_audio_bytes=prompt_audio_bytes,
                prompt_lyric_lang=prompt_lyric_lang,
                prompt_vocal_sep=prompt_vocal_sep,
            )
        if target_metadata_bytes is None:
            target_metadata_bytes = await self._transcribe_target(
                target_audio_bytes=target_audio_bytes,
                target_lyric_lang=target_lyric_lang,
                target_vocal_sep=target_vocal_sep,
            )

        prompt_path = await self._save_audio_as_wav(prompt_audio_bytes)
        prompt_meta_path = await self.save_temp_file(prompt_metadata_bytes, ".json")
        target_meta_path = await self.save_temp_file(target_metadata_bytes, ".json")
        try:
            result = await self.call(
                api_name="/_run_synthesis",
                prompt_audio=handle_file(prompt_path),
                prompt_metadata=handle_file(prompt_meta_path),
                target_metadata=handle_file(target_meta_path),
                control=_CONTROL_MAP.get(control, "melody-controlled"),
                auto_shift="yes" if auto_shift else "no",
                pitch_shift=float(pitch_shift),
                seed=float(seed),
            )
            return await self.read_result_file(result)
        finally:
            os.unlink(prompt_path)
            os.unlink(prompt_meta_path)
            os.unlink(target_meta_path)

    async def convert_voice(
        self,
        prompt_audio_bytes: bytes,
        target_audio_bytes: bytes,
        prompt_vocal_sep: bool = False,
        target_vocal_sep: bool = True,
        auto_shift: bool = True,
        pitch_shift: int = 0,
        seed: int = 42,
        **_ignored,
    ) -> bytes:
        """
        歌声转换 (SVC) — 内部通过 SVS (/_run_synthesis) 实现

        Singer Gradio API 没有专用 SVC 端点，但 /_run_synthesis 效果等价：
        prompt_audio 提供音色，target_audio 提供旋律/歌词 → 输出音色已替换的歌声。
        diffusion 参数（n_step / cfg / use_fp16 / auto_mix_acc）在 Singer 不适用，已忽略。
        """
        return await self.synthesize_singing(
            prompt_audio_bytes=prompt_audio_bytes,
            target_audio_bytes=target_audio_bytes,
            control="melody",
            auto_shift=auto_shift,
            pitch_shift=pitch_shift,
            seed=seed,
            prompt_vocal_sep=prompt_vocal_sep,
            target_vocal_sep=target_vocal_sep,
        )


singer_client = SingerClient()
