"""Structured logging setup (infrastructure binding for the Logger port)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def setup_logging(node_id: str, log_dir: str = "logs") -> None:
    """Configure structlog to emit console + file logs tagged with this node's context."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(node_id=node_id)


def get_logger():
    """Return a structlog logger bound to this node's id."""
    return structlog.get_logger()