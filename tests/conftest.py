from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _suppress_event_emitter():
    """Prevent EventEmitter singleton from registering Console/File handlers during tests."""
    from alpacalyzer.events.emitter import EventEmitter

    EventEmitter._instance = None
    # Create a bare emitter with no handlers so events are silently dropped
    instance = EventEmitter()
    EventEmitter._instance = instance
    yield
