import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import cast

# Configuration
LOGS_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Set log level from environment or default to INFO
log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO"))


class NoTracebackConsoleFilter(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        record.exc_text = None
        return True


class CustomLogger(logging.Logger):
    """Custom logger with analytics capabilities"""

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

        # Create analytics logger as regular Logger to prevent recursion
        orig_logger_class = logging.getLoggerClass()
        logging.setLoggerClass(logging.Logger)
        self._analytics_logger = logging.getLogger(f"{name}.analytics")
        logging.setLoggerClass(orig_logger_class)

        self._analytics_logger.propagate = False

    def analyze(self, msg, *args, **kwargs):
        """Log to analytics log only"""
        self._analytics_logger.debug(msg, *args, **kwargs)

    def setup_analytics_handler(self, handler):
        """Add a handler specifically for analytics logger"""
        self._analytics_logger.addHandler(handler)


# Set up the logger factory
logging.setLoggerClass(CustomLogger)


# Create a function to initialize the logger - this makes it easier to test
def setup_logger():
    # Main logger
    logger = cast(CustomLogger, logging.getLogger("app"))
    logger.setLevel(log_level)
    logger.propagate = False

    # Remove existing handlers if any
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # File handler
    file_handler = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR, "trading_logs.log"), when="midnight", interval=1, backupCount=7
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(message)s         (%(levelname)s - %(asctime)s)"))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.addFilter(NoTracebackConsoleFilter())
    logger.addHandler(console_handler)

    # Analytics handler
    analytics_handler = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR, "analytics_log.log"), when="midnight", interval=1, backupCount=7
    )
    analytics_handler.setLevel(logging.DEBUG)
    analytics_handler.setFormatter(logging.Formatter("%(message)s         (%(levelname)s - %(asctime)s)"))
    logger.setup_analytics_handler(analytics_handler)

    return logger


# Initialize the logger
logger = setup_logger()
