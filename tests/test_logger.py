import logging
from unittest import mock

import pytest

import alpacalyzer.utils.logger as logger_module


@pytest.fixture
def logger(tmp_path, monkeypatch):
    """
    Provides a cleanly initialized logger instance for testing, with logs directed to a temporary path.

    This fixture ensures that each test runs in isolation by creating a new logger and patching
    the module's get_logger() function to return it.
    """
    # Patch the log directory to our temporary test directory
    monkeypatch.setattr(logger_module, "LOGS_DIR", str(tmp_path))

    # Create a new, isolated logger instance for this specific test
    test_logger = logger_module.setup_logger()

    # Patch the get_logger function to return our test-specific logger
    monkeypatch.setattr(logger_module, "get_logger", lambda: test_logger)

    yield test_logger

    # Teardown: clean up our test_logger's handlers to release file locks etc.
    for handler in test_logger.handlers[:]:
        test_logger.removeHandler(handler)
        handler.close()
    if hasattr(test_logger, "_analytics_logger"):
        analytics_log = test_logger._analytics_logger
        for handler in analytics_log.handlers[:]:
            analytics_log.removeHandler(handler)
            handler.close()


def test_logger_is_customlogger_instance(logger):
    """Verify that the logger is an instance of the custom logger class."""
    assert isinstance(logger, logger_module.CustomLogger)


def test_logger_has_analyze_method(logger):
    """Verify that the logger has the custom 'analyze' method."""
    assert hasattr(logger, "analyze")


def test_no_traceback_filter_functionality(logger):
    """Test that NoTracebackConsoleFilter actually removes exception info."""
    # Create a filter directly
    ntf = logger_module.NoTracebackConsoleFilter()

    # Create a test record with exception info
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Test error",
        args=(),
        exc_info=(Exception, Exception("Test exception"), None),
    )

    # Apply the filter
    result = ntf.filter(record)

    # Verify filter returns True (allowing record) but clears exception info
    assert result is True
    assert record.exc_info is None
    assert record.exc_text is None


def test_analyze_method_with_complex_arguments(logger):
    """Test that analyze method correctly forwards complex arguments to the analytics logger."""
    with mock.patch.object(logger._analytics_logger, "debug") as mock_debug:
        test_args = ("arg1", "arg2")
        test_kwargs = {"key1": "value1", "key2": "value2"}

        logger.analyze("Test with %s and %s", *test_args, **test_kwargs)

        mock_debug.assert_called_once_with("Test with %s and %s", *test_args, **test_kwargs)


def test_analytics_logger_initialization(logger):
    """Test that the analytics logger is correctly initialized."""
    # Verify analytics logger exists and has correct configuration
    assert hasattr(logger, "_analytics_logger")
    assert logger._analytics_logger.name == "app.analytics"
    assert logger._analytics_logger.propagate is False
    assert logger._analytics_logger.level == logging.DEBUG


def test_setup_analytics_handler(logger):
    """Test adding a custom handler to analytics logger."""
    # Create a test handler
    test_handler = logging.StreamHandler()

    # Add it to analytics logger
    logger.setup_analytics_handler(test_handler)

    # Verify it was added
    assert test_handler in logger._analytics_logger.handlers

    # Clean up
    logger._analytics_logger.removeHandler(test_handler)
    test_handler.close()
