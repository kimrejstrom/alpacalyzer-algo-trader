"""Tests for standardized logger."""

import logging

import pytest

import alpacalyzer.utils.logger as logger_module


@pytest.fixture
def _clean_logger(tmp_path, monkeypatch):
    """Provides a cleanly initialized logger for testing."""
    monkeypatch.setattr(logger_module, "LOGS_DIR", str(tmp_path))
    # Reset the cached root logger so setup_logger creates fresh
    monkeypatch.setattr(logger_module, "_root_logger", None)
    root = logger_module.setup_logger()
    monkeypatch.setattr(logger_module, "_root_logger", root)

    yield root

    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()


def test_logger_is_standard_logger(_clean_logger):
    """Logger is a standard logging.Logger instance."""
    assert isinstance(_clean_logger, logging.Logger)


def test_logger_has_file_and_console_handlers(_clean_logger):
    """Logger has exactly two handlers: file and console."""
    assert len(_clean_logger.handlers) == 2
    handler_types = {type(h).__name__ for h in _clean_logger.handlers}
    assert "TimedRotatingFileHandler" in handler_types
    assert "StreamHandler" in handler_types


def test_no_traceback_filter_functionality():
    """NoTracebackConsoleFilter removes exception info from console output."""
    ntf = logger_module.NoTracebackConsoleFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Test error",
        args=(),
        exc_info=(Exception, Exception("Test exception"), None),
    )

    result = ntf.filter(record)

    assert result is True
    assert record.exc_info is None
    assert record.exc_text is None


def test_get_logger_returns_root_when_no_name():
    """get_logger() with no name returns the root app logger."""
    logger1 = logger_module.get_logger()
    logger2 = logger_module.get_logger()
    assert logger1 is logger2
    assert logger1.name == "app"


def test_get_logger_with_name_returns_child():
    """get_logger('component') returns a child logger under 'app'."""
    child = logger_module.get_logger("engine")
    assert child.name == "app.engine"
    assert isinstance(child, logging.Logger)


def test_child_logger_inherits_handlers(_clean_logger):
    """Child loggers propagate to the root app logger's handlers."""
    child = logger_module.get_logger("scanner")
    # Child should have no handlers of its own (propagates to parent)
    assert len(child.handlers) == 0
    assert child.propagate is True


def test_file_format_includes_component(_clean_logger, tmp_path):
    """File handler format includes component name, level, and timestamp."""
    file_handler = next(h for h in _clean_logger.handlers if isinstance(h, logging.handlers.TimedRotatingFileHandler))
    formatter = file_handler.formatter
    assert formatter is not None

    # Format a record and check structure
    record = logging.LogRecord(
        name="app.engine",
        level=logging.INFO,
        pathname="engine.py",
        lineno=42,
        msg="Processing signal",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)

    # Should contain: timestamp, level, component, message
    assert "INFO" in formatted
    assert "engine" in formatted
    assert "Processing signal" in formatted


def test_console_format_includes_component(_clean_logger):
    """Console handler format includes component name."""
    console_handler = next(h for h in _clean_logger.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler))
    formatter = console_handler.formatter
    assert formatter is not None

    record = logging.LogRecord(
        name="app.scanner",
        level=logging.INFO,
        pathname="scanner.py",
        lineno=10,
        msg="Found 5 tickers",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)

    assert "scanner" in formatted
    assert "Found 5 tickers" in formatted


def test_root_logger_shows_app_as_component(_clean_logger):
    """Root logger (no child name) shows 'app' as component."""
    file_handler = next(h for h in _clean_logger.handlers if isinstance(h, logging.handlers.TimedRotatingFileHandler))
    formatter = file_handler.formatter

    record = logging.LogRecord(
        name="app",
        level=logging.WARNING,
        pathname="main.py",
        lineno=1,
        msg="Something happened",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)

    assert "WARNING" in formatted
    assert "app" in formatted
    assert "Something happened" in formatted
