"""
后台应用日志：从 server.yaml 的 logging 段读取配置。
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Any, Mapping, Optional


def _load_logging_config() -> Mapping[str, Any]:
    root = Path(__file__).resolve().parents[2]
    path = root / "server.yaml"
    if not path.is_file():
        return {}
    import yaml
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("logging") or {}


def setup_logging() -> None:
    """
    根据 server.yaml 的 logging 配置设置根 logger。
    支持：file（路径）、level、rotation（按大小或按天切分）。
    """
    cfg = _load_logging_config()
    if not cfg:
        return

    level_name = (cfg.get("level") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_file = cfg.get("file") or ""
    log_file = log_file.strip() if isinstance(log_file, str) else ""

    root = logging.getLogger()
    root.setLevel(level)
    # 避免重复添加 handler（例如 reload 时）
    for h in root.handlers[:]:
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_file:
        path = Path(log_file).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        rotation = cfg.get("rotation") or {}
        rtype = (rotation.get("type") or "size").lower()

        if rtype == "time":
            when = rotation.get("when") or "midnight"
            interval = int(rotation.get("interval") or 1)
            backup_count = int(rotation.get("backup_count") or 30)
            file_handler = logging.handlers.TimedRotatingFileHandler(
                str(path),
                when=when,
                interval=interval,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.suffix = "%Y-%m-%d"
        else:
            max_bytes = int(rotation.get("max_bytes") or 10 * 1024 * 1024)
            backup_count = int(rotation.get("backup_count") or 5)
            file_handler = logging.handlers.RotatingFileHandler(
                str(path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)


__all__ = ["setup_logging"]
