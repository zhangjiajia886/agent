"""
日志系统配置：
  - 按 8 小时分片（TimedRotatingFileHandler）
  - 同时输出到文件 + 控制台
  - 保留最近 90 个分片（约 30 天）
  - 文件名格式：logs/myagent.log.YYYY-MM-DD_HH（整点对齐）
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_INITIALIZED = False

_FMT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    log_dir: Path | None = None,
    backup_count: int = 90,
) -> None:
    """
    初始化全局日志系统。
    只执行一次（幂等），多次调用无副作用。
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    log_dir = log_dir or _LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "myagent.log"

    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # ── 文件 Handler：每 8 小时滚动一次，午夜对齐 ──
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file),
        when="H",           # 按小时
        interval=8,         # 每 8 小时一个分片
        backupCount=backup_count,
        encoding="utf-8",
        utc=False,          # 使用本地时间（北京时间）
    )
    file_handler.suffix = "%Y-%m-%d_%H"          # 分片文件名后缀
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # ── 控制台 Handler：同步输出到 stdout ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # ── 根 Logger 配置 ──
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # 降低第三方库的噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"[LOG INIT] 日志系统启动 level={logging.getLevelName(level)} "
        f"file={log_file} interval=8h backup={backup_count}"
    )
