"""
JSON structured logging with ContextVar-based correlation.

Usage:
    from app.logging_config import setup_logging
    setup_logging(level="INFO", json_format=True)

ContextVars (request_id, user_id) are automatically included
in every log record when set by middleware.
"""

import json
import logging
import logging.config
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# ── Context variables for request correlation ─────────────────────────────────
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON with correlation context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject correlation context
        req_id = request_id_ctx.get()
        if req_id:
            log_entry["request_id"] = req_id

        uid = user_id_ctx.get()
        if uid:
            log_entry["user_id"] = uid

        # Source location for warnings and above
        if record.levelno >= logging.WARNING:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Exception info
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Extra fields passed via `logger.info("msg", extra={"key": "val"})`
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "stack_info", "lineno", "funcName", "pathname",
            "filename", "module", "levelno", "levelname", "msecs", "message",
            "thread", "threadName", "process", "processName", "taskName",
        }
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extras:
            log_entry["extra"] = extras

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, output structured JSON; otherwise plain text.
    """
    formatter_class = "app.logging_config.JSONFormatter" if json_format else "logging.Formatter"
    plain_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": formatter_class,
            } if json_format else {
                "format": plain_fmt,
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": level,
            "handlers": ["console"],
        },
        # Quieten noisy third-party loggers
        "loggers": {
            "uvicorn": {"level": "INFO", "propagate": False, "handlers": ["console"]},
            "uvicorn.access": {"level": "WARNING", "propagate": False, "handlers": ["console"]},
            "sqlalchemy.engine": {"level": "WARNING", "propagate": False, "handlers": ["console"]},
            "httpx": {"level": "WARNING", "propagate": False, "handlers": ["console"]},
            "httpcore": {"level": "WARNING", "propagate": False, "handlers": ["console"]},
        },
    }

    logging.config.dictConfig(config)
