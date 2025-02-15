import logging
import os
from logging.handlers import TimedRotatingFileHandler

from dotenv import load_dotenv

load_dotenv()
log_level = os.getenv("LOG_LEVEL", "INFO").upper()  # Set the log level to INFO by default

# Validate and map log level
valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if log_level not in valid_levels:
    raise ValueError(f"Invalid log level: {log_level}. Must be one of {valid_levels}")

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level))  # Set minimum logging level


# Create handlers
file_handler = TimedRotatingFileHandler(
    "trading_logs.log", when="midnight", interval=1, backupCount=7
)  # Rotate daily, keep 7 backups
console_handler = logging.StreamHandler()  # Logs to console (stdout)

# Set levels for each handler
file_handler.setLevel(getattr(logging, log_level))
console_handler.setLevel(getattr(logging, log_level))

# Create a formatter and set it for both handlers
file_formatter = logging.Formatter("%(message)s         (%(levelname)s - %(asctime)s)")
console_formatter = logging.Formatter("%(message)s")
file_handler.setFormatter(file_formatter)
console_handler.setFormatter(console_formatter)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)
