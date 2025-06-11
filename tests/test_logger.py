import logging
from unittest import mock

import pytest

import alpacalyzer.utils.logger as logger_module


@pytest.fixture(autouse=True)
def setup_and_cleanup():
    """Set up test environment and clean up afterward"""
    # Save original values
    original_logs_dir = logger_module.LOGS_DIR

    # Reset the logger before each test
    logger_module.logger = logger_module.setup_logger()

    # Run the test
    yield

    # Clean up after test
    log = logger_module.logger
    for handler in log.handlers[:]:
        log.removeHandler(handler)
        handler.close()

    # Also clean analytics logger
    if hasattr(log, "_analytics_logger"):
        analytics_log = log._analytics_logger
        for handler in analytics_log.handlers[:]:
            analytics_log.removeHandler(handler)
            handler.close()

    # Restore original values
    logger_module.LOGS_DIR = original_logs_dir
    logger_module.logger = logger_module.setup_logger()


def test_logger_is_customlogger_instance():
    assert isinstance(logger_module.logger, logger_module.CustomLogger)


def test_logger_has_analyze_method():
    assert hasattr(logger_module.logger, "analyze")
    assert callable(logger_module.logger.analyze)


def test_analyze_logs_to_analytics_logger():
    with mock.patch.object(logger_module.logger._analytics_logger, "debug") as mock_debug:
        logger_module.logger.analyze("Test message")
        mock_debug.assert_called_once_with("Test message")


def test_logger_handlers_types():
    # Setup is handled by the fixture
    handler_types = [type(h) for h in logger_module.logger.handlers]
    assert logging.StreamHandler in handler_types
    assert logger_module.TimedRotatingFileHandler in handler_types


def test_console_handler_has_no_traceback_filter():
    found = False
    for handler in logger_module.logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            for filt in handler.filters:
                if isinstance(filt, logger_module.NoTracebackConsoleFilter):
                    found = True
    assert found


def test_logger_file_handlers_have_correct_filenames(tmp_path, monkeypatch):
    # Patch log file paths to tmp_path
    monkeypatch.setattr(logger_module, "LOGS_DIR", str(tmp_path))

    # Create a fresh logger with the patched path
    test_logger = logger_module.setup_logger()

    # Check handler filenames
    for handler in test_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            assert str(tmp_path) in handler.baseFilename
