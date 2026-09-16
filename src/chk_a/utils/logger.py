"""JSONL logger with rotation for chk-a.

Every log record is emitted as a single line of JSON so it can be tailed and
parsed by external tooling (jq, log shippers, the Alert agent).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .context import get_correlation_id

# Fields that belong to the standard LogRecord and should not be copied verbatim.
_RESERVED = {
    "args",
    "msg",
    "message",
    "levelname",
    "levelno",
    "name",
    "created",
    "msecs",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "lineno",
    "module",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JSONFormatter(logging.Formatter):
    """Render a log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        cid = get_correlation_id()
        if cid:
            payload["correlation_id"] = cid
        for key, val in record.__dict__.items():
            if key in _RESERVED:
                continue
            payload[key] = val
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logger(
    name: str = "chk_a",
    level: str = "INFO",
    log_file: str | None = None,
    max_size_mb: int = 50,
    backup_count: int = 10,
    file_mode: int = 0o640,
    dir_mode: int = 0o750,
) -> logging.Logger:
    """Configure and return the named logger.

    Avoids adding duplicate handlers when called more than once.
    Auto-creates log directory if needed. If running as root and log directory
    is under /var/log/chk-a, sets ownership to chk-a:chk-a.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.getLevelName(level.upper()))
    if logger.handlers:
        return logger

    formatter = JSONFormatter()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file:
        log_path = Path(log_file)
        log_dir = log_path.parent
        log_dir.mkdir(parents=True, exist_ok=True, mode=dir_mode)

        # If running as root and log dir is /var/log/chk-a, fix ownership
        if os.geteuid() == 0 and log_dir == Path("/var/log/chk-a"):
            try:
                import pwd
                import grp

                uid = pwd.getpwnam("chk-a").pw_uid
                gid = grp.getgrnam("chk-a").gr_gid
                os.chown(log_dir, uid, gid)
                if log_path.exists():
                    os.chown(log_path, uid, gid)
            except (KeyError, PermissionError):
                pass  # User/group doesn't exist or no permission
        else:
            # Set directory permissions
            try:
                os.chmod(log_dir, dir_mode)
            except (OSError, PermissionError):
                pass

        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Set file permissions
        try:
            os.chmod(log_file, file_mode)
        except (OSError, PermissionError):
            pass

    return logger


__all__ = ["JSONFormatter", "setup_logger", "write_day_separator"]


def write_day_separator(log_file: str) -> bool:
    """Write a day separator line to a log file.

    Args:
        log_file: Path to the log file.

    Returns:
        True if written successfully, False otherwise.
    """
    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        separator = f"\n{'=' * 60}\n=== DAY SEPARATOR: {today} ===\n{'=' * 60}\n\n"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(separator)
            fh.flush()
            os.fsync(fh.fileno())
        return True
    except Exception:
        return False
