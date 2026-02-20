"""
Standardized logging for Alpacalyzer.

Usage:
    from alpacalyzer.utils.logger import get_logger

    logger = get_logger(__name__)  # component name from module
    logger = get_logger("engine")  # or explicit component name
    logger = get_logger()          # root app logger

Log format:
    File:    2026-02-20 14:30:05 [INFO] engine: Processing signal for NVDA
    Console: [engine] Processing signal for NVDA
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler

# Configuration
LOGS_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Set log level from environment or default to INFO
log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO"))

_FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _extract_component(name: str) -> str:
    """
    Extract short component name from logger name.

    'app.execution.engine' -> 'engine'
    'app.scanners.finviz'  -> 'finviz'
    'app'                  -> 'app'
    """
    if "." in name:
        return name.rsplit(".", 1)[-1]
    return name


class ComponentFormatter(logging.Formatter):
    """Formatter that injects a short component name from the logger name."""

    def format(self, record: logging.LogRecord) -> str:
        record.component = _extract_component(record.name)  # type: ignore[attr-defined]
        return super().format(record)


class NoTracebackConsoleFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.exc_info = None
        record.exc_text = None
        return True


# Module-level singleton
_root_logger: logging.Logger | None = None


def setup_logger() -> logging.Logger:
    """Set up the root application logger with console and file handlers."""
    logger = logging.getLogger("app")
    logger.setLevel(log_level)
    logger.propagate = False

    # Remove existing handlers if any
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # File handler
    file_handler = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR, "trading_logs.log"),
        when="midnight",
        interval=1,
        backupCount=7,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        ComponentFormatter(
            "%(asctime)s [%(levelname)s] %(component)s: %(message)s",
            datefmt=_FILE_DATE_FORMAT,
        )
    )
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ComponentFormatter("[%(component)s] %(message)s"))
    console_handler.addFilter(NoTracebackConsoleFilter())
    logger.addHandler(console_handler)

    return logger


# Initialize on import
_root_logger = setup_logger()


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Component name. If provided, returns a child logger
              under the 'app' hierarchy (e.g. 'app.engine').
              Accepts __name__ style names - the last segment is used
              as the component label.
              If None, returns the root 'app' logger.
    """
    if name is None:
        assert _root_logger is not None
        return _root_logger
    short = name.rsplit(".", 1)[-1] if "." in name else name
    return logging.getLogger(f"app.{short}")
