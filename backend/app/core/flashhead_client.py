"""SoulX-FlashHead 数字人视频生成客户端"""
 
import asyncio
import os
import subprocess
import tempfile
from gradio_client import handle_file
from app.config import settings
from app.core.gradio_client import GradioSpaceClient
from loguru import logger
 
 
class FlashHeadClient(GradioSpaceClient):

    def __init__(self):
        super().__init__(settings.SOUL_FLASHHEAD_SPACE)

    async def _convert_hls_to_mp4_bytes(self, playlist_path: str) -> bytes:
        loop = asyncio.get_event_loop()

        def _convert() -> bytes:
            fd, output_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            try:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-allowed_extensions",
                    "ALL",
                    "-i",
                    playlist_path,
                    "-c",
                    "copy",
                    output_path,
                ]
                logger.info(f"检测到 FlashHead 返回 HLS 播放列表，开始转为 MP4 playlist={playlist_path} output={output_path}")
                completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if completed.returncode != 0:
                    raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "ffmpeg convert failed")
                with open(output_path, "rb") as f:
                    return f.read()
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)

        return await loop.run_in_executor(None, _convert)

    async def _read_video_result(self, result_path) -> bytes:
        resolved_path = self._resolve_result_filepath(result_path)
        logger.info(f"FlashHead 结果路径已解析 path={resolved_path}")
        if resolved_path.endswith(".m3u8"):
            return await self._convert_hls_to_mp4_bytes(resolved_path)
        return await self.read_result_file(result_path)

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
        logger.info(
            f"FlashHead 输入临时文件已准备 图片路径={img_path} 音频路径={aud_path} model_type={model_type} seed={seed} use_face_crop={use_face_crop}"
        )
        try:
            ckpt_dir = "models/SoulX-FlashHead-1_3B"
            wav2vec_dir = "models/wav2vec2-base-960h"

            logger.info(
                f"开始提交 FlashHead Gradio 任务 space={self.space_id} api=/dispatch_inference ckpt={ckpt_dir} wav2vec={wav2vec_dir}"
            )
            result = await self.submit(
                api_name="/dispatch_inference",
                mode="Single GPU",
                gpu_ids="0",
                ckpt=ckpt_dir,
                wav2vec=wav2vec_dir,
                model_type=model_type,
                img=handle_file(img_path),
                audio=handle_file(aud_path),
                enc_mode="once",
                seed=seed,
                use_face_crop=use_face_crop,
            )
            logger.info(
                f"FlashHead Gradio 任务返回成功 返回结构={self._describe_result(result)}"
            )
            # result 是 dict(video: filepath, subtitles: filepath|None)
            if isinstance(result, dict):
                result_path = result.get("video") or result.get("path")
            elif isinstance(result, (list, tuple)):
                result_path = result[0] if result else None
            else:
                result_path = result
            logger.info(f"FlashHead 视频文件路径={result_path}")
            return await self._read_video_result(result_path)
        finally:
            logger.info(f"开始清理 FlashHead 临时文件 图片路径={img_path} 音频路径={aud_path}")
            os.unlink(img_path)
            os.unlink(aud_path)
            logger.info("FlashHead 临时文件清理完成")


flashhead_client = FlashHeadClient()
