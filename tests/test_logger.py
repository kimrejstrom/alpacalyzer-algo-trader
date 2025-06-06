import pytest
import logging
import io
import os
import re # For timestamp matching

# Important: Import the loggers AFTER potential monkeypatching or at least be aware of import order issues.
# For this setup, we are modifying handlers on the already imported instances.
from src.alpacalyzer.utils.logger import logger, analytics_logger, file_formatter, analytics_formatter

# Log file names, defined here for consistency if needed, though not directly used by tests if handlers are replaced
TRADING_LOG_FILE = "trading_logs.log"
ANALYTICS_LOG_FILE = "analytics_log.txt"

@pytest.fixture
def mock_log_handlers():
    # --- Setup ---
    original_logger_handlers = list(logger.handlers)
    original_analytics_logger_handlers = list(analytics_logger.handlers)

    # Find and store original file handlers and their formatters
    original_trading_file_handler = None
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename.endswith(TRADING_LOG_FILE):
            original_trading_file_handler = h
            break

    original_analytics_file_handler = None
    for h in analytics_logger.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename.endswith(ANALYTICS_LOG_FILE):
            original_analytics_file_handler = h
            break

    # Create StringIO buffers for capturing log output
    trading_log_buffer = io.StringIO()
    analytics_log_buffer = io.StringIO()

    # Create new StreamHandlers
    mock_trading_handler = logging.StreamHandler(trading_log_buffer)
    mock_analytics_handler = logging.StreamHandler(analytics_log_buffer)

    # Apply original formatters to mock handlers
    if original_trading_file_handler:
        mock_trading_handler.setFormatter(original_trading_file_handler.formatter)
    else: # Fallback if original file handler wasn't found for some reason (e.g. tests run standalone)
        mock_trading_handler.setFormatter(file_formatter) # Use the imported one

    if original_analytics_file_handler:
        mock_analytics_handler.setFormatter(original_analytics_file_handler.formatter)
    else: # Fallback
        mock_analytics_handler.setFormatter(analytics_formatter)


    # Replace existing file handlers with mock handlers
    # Remove all handlers first to be safe, then add back non-file handlers and our new mock file handlers.

    logger.handlers = [h for h in original_logger_handlers if not isinstance(h, logging.FileHandler) or not h.baseFilename.endswith(TRADING_LOG_FILE)]
    logger.addHandler(mock_trading_handler)

    analytics_logger.handlers = [h for h in original_analytics_logger_handlers if not isinstance(h, logging.FileHandler) or not h.baseFilename.endswith(ANALYTICS_LOG_FILE)]
    analytics_logger.addHandler(mock_analytics_handler)

    # Ensure log levels are set for the mock handlers if not inherited or set by logger
    # Typically, handlers inherit level from logger if not set, or use their own if set.
    # The loggers themselves (logger, analytics_logger) have levels (DEBUG, INFO).
    # Let's assume the logger's level is sufficient. For file handlers, they were DEBUG.
    mock_trading_handler.setLevel(logging.DEBUG)
    mock_analytics_handler.setLevel(logging.DEBUG)


    yield trading_log_buffer, analytics_log_buffer

    # --- Teardown ---
    # Remove mock handlers
    logger.removeHandler(mock_trading_handler)
    analytics_logger.removeHandler(mock_analytics_handler)

    # Restore original handlers
    # This simplistic restoration might lead to duplicated handlers if not careful.
    # A better way is to clear and then add original_*.
    logger.handlers = original_logger_handlers
    analytics_logger.handlers = original_analytics_logger_handlers

    # Close StringIO buffers
    trading_log_buffer.close()
    analytics_log_buffer.close()

    # Clean up actual log files that might have been created if setup failed or outside tests
    if os.path.exists(ANALYTICS_LOG_FILE):
        os.remove(ANALYTICS_LOG_FILE)
    if os.path.exists(TRADING_LOG_FILE):
        os.remove(TRADING_LOG_FILE)


def test_analyze_writes_to_analytics_log(mock_log_handlers):
    trading_buffer, analytics_buffer = mock_log_handlers
    test_message = "Test analytics message for analyze function"

    logger.analyze(test_message)

    analytics_content = analytics_buffer.getvalue()
    assert test_message in analytics_content
    # Format: "%(message)s         (%(levelname)s - %(asctime)s)"
    # Example: Test analytics message for analyze function         (INFO - 2023-10-27 10:00:00,123)
    # Regex to check for " (LEVEL - YYYY-MM-DD HH:MM:SS,ms)"
    assert re.search(r" \s+\(INFO - \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\)$", analytics_content.strip())

def test_analyze_not_writes_to_trading_log(mock_log_handlers):
    trading_buffer, analytics_buffer = mock_log_handlers
    test_message = "Another analytics message that should not be in trading log"

    logger.analyze(test_message)

    trading_content = trading_buffer.getvalue()
    assert test_message not in trading_content

def test_regular_log_not_writes_to_analytics_log(mock_log_handlers):
    trading_buffer, analytics_buffer = mock_log_handlers
    test_message = "Regular info message for main logger, not for analytics"

    logger.info(test_message) # Regular logger uses INFO level by default for console

    analytics_content = analytics_buffer.getvalue()
    assert test_message not in analytics_content

def test_regular_log_writes_to_trading_log(mock_log_handlers):
    trading_buffer, analytics_buffer = mock_log_handlers
    test_message = "Regular info message for main logger, destined for trading log"

    logger.info(test_message) # Regular logger

    trading_content = trading_buffer.getvalue()
    assert test_message in trading_content
    # Check format for trading log as well
    # Format: "%(message)s         (%(levelname)s - %(asctime)s)"
    assert re.search(r" \s+\(INFO - \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\)$", trading_content.strip())

def test_debug_log_writes_to_trading_log_if_level_is_debug(mock_log_handlers):
    trading_buffer, analytics_buffer = mock_log_handlers
    test_message = "A debug message for the trading log"

    # Temporarily set logger level to DEBUG if it's not already, to ensure message is processed
    original_level = logger.level
    logger.setLevel(logging.DEBUG)

    logger.debug(test_message)

    logger.setLevel(original_level) # Restore level

    trading_content = trading_buffer.getvalue()
    # The file_handler for logger is set to DEBUG level
    assert test_message in trading_content
    assert re.search(r" \s+\(DEBUG - \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\)$", trading_content.strip())

def test_analytics_logger_direct_usage(mock_log_handlers):
    trading_buffer, analytics_buffer = mock_log_handlers
    test_message = "Direct call to analytics_logger.info"

    analytics_logger.info(test_message)

    analytics_content = analytics_buffer.getvalue()
    assert test_message in analytics_content
    assert re.search(r" \s+\(INFO - \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\)$", analytics_content.strip())

    trading_content = trading_buffer.getvalue()
    assert test_message not in trading_content
