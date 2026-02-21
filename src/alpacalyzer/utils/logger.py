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


# Catppuccin Mocha palette (true-color ANSI escapes)
_CATPPUCCIN = {
    "rosewater": "\033[38;2;245;224;220m",
    "flamingo": "\033[38;2;242;205;205m",
    "pink": "\033[38;2;245;194;231m",
    "mauve": "\033[38;2;203;166;247m",
    "red": "\033[38;2;243;139;168m",
    "maroon": "\033[38;2;235;160;172m",
    "peach": "\033[38;2;250;179;135m",
    "yellow": "\033[38;2;249;226;175m",
    "green": "\033[38;2;166;227;161m",
    "teal": "\033[38;2;148;226;213m",
    "sky": "\033[38;2;137;220;235m",
    "sapphire": "\033[38;2;116;199;236m",
    "blue": "\033[38;2;137;180;250m",
    "lavender": "\033[38;2;180;190;254m",
}
_RESET = "\033[0m"

# Map component names to Catppuccin colors
_COMPONENT_COLORS: dict[str, str] = {
    "cli": _CATPPUCCIN["mauve"],
    "orchestrator": _CATPPUCCIN["blue"],
    "engine": _CATPPUCCIN["sapphire"],
    "registry": _CATPPUCCIN["teal"],
    "aggregator": _CATPPUCCIN["green"],
    "scheduler": _CATPPUCCIN["green"],
    "adapters": _CATPPUCCIN["sky"],
    "social_scanner": _CATPPUCCIN["flamingo"],
    "stocktwits_scanner": _CATPPUCCIN["flamingo"],
    "finviz_scanner": _CATPPUCCIN["flamingo"],
    "wsb_scanner": _CATPPUCCIN["flamingo"],
    "emitter": _CATPPUCCIN["lavender"],
    "momentum": _CATPPUCCIN["peach"],
    "breakout": _CATPPUCCIN["peach"],
    "mean_reversion": _CATPPUCCIN["peach"],
    "alpaca_client": _CATPPUCCIN["yellow"],
    "yfinance_client": _CATPPUCCIN["yellow"],
    "api": _CATPPUCCIN["yellow"],
    "technical_analysis": _CATPPUCCIN["rosewater"],
    "dashboard": _CATPPUCCIN["rosewater"],
    "structured": _CATPPUCCIN["pink"],
    "__init__": _CATPPUCCIN["pink"],
    "hedge_fund": _CATPPUCCIN["red"],
    "state": _CATPPUCCIN["maroon"],
    "risk_manager": _CATPPUCCIN["red"],
    "portfolio_manager": _CATPPUCCIN["red"],
    "opportunity_finder": _CATPPUCCIN["maroon"],
    "trading_strategist": _CATPPUCCIN["maroon"],
    "fundamentals_agent": _CATPPUCCIN["teal"],
    "sentiment_agent": _CATPPUCCIN["teal"],
    "order_manager": _CATPPUCCIN["sapphire"],
    "position_tracker": _CATPPUCCIN["sapphire"],
    "display": _CATPPUCCIN["lavender"],
    "backtester": _CATPPUCCIN["sky"],
}

# Cycle through palette for unknown components
_PALETTE_CYCLE = list(_CATPPUCCIN.values())


class ComponentFormatter(logging.Formatter):
    """Formatter that injects a short component name from the logger name."""

    _color_index = 0

    def format(self, record: logging.LogRecord) -> str:
        component = _extract_component(record.name)
        record.component = component  # type: ignore[attr-defined]

        # Apply Catppuccin color to console bracket prefix
        if self._use_color:
            color = _COMPONENT_COLORS.get(component)
            if color is None:
                color = _PALETTE_CYCLE[ComponentFormatter._color_index % len(_PALETTE_CYCLE)]
                _COMPONENT_COLORS[component] = color
                ComponentFormatter._color_index += 1
            record.colored_prefix = f"{color}[{component}]{_RESET}"  # type: ignore[attr-defined]

        return super().format(record)

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, use_color: bool = False) -> None:
        super().__init__(fmt, datefmt)
        self._use_color = use_color


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

    # Console handler (Catppuccin Mocha colored brackets)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ComponentFormatter("%(colored_prefix)s %(message)s", use_color=True))
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
