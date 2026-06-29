from __future__ import annotations

import json
import logging
import sys
from typing import Any

_SKIP_FIELDS = frozenset(
    {
        "args", "exc_info", "exc_text", "levelno", "lineno", "module",
        "msecs", "msg", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName",
        "filename", "funcName", "created", "taskName",
    }
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key not in _SKIP_FIELDS and not key.startswith("_") and key not in data:
                data[key] = val
        return json.dumps(data, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """アプリ全体のログをJSON形式で標準出力に設定する。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 外部ライブラリのノイズを抑制
    for noisy in ("httpx", "httpcore", "urllib3", "botocore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
