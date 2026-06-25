"""structlog configuration for voxmap CLI scripts.

Call ``get_logger(__name__)`` from a script — structlog is configured on first
use with a colorized console renderer (timestamp + level + key=value pairs).
Subsequent calls are no-op.

To additionally write logs to a file, call ``configure_file_logging(path)``
before the first ``get_logger`` call (typically at the top of run.py main()).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import structlog

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    _configured = True


def configure_file_logging(path: Path) -> None:
    """Add a plain-text file handler to the root logger.

    Must be called before the first get_logger() invocation.
    Captures both structlog output and Python warnings (logging.captureWarnings).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setLevel(logging.INFO)
    # Plain formatter without ANSI codes for file output
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    logging.captureWarnings(True)


def get_logger(name: str | None = None) -> Any:
    _configure()
    return structlog.get_logger(name) if name else structlog.get_logger()
