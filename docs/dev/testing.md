# Testing

## Test Structure

```
tests/
├── conftest.py              # Fixtures (OpenAI client auto-mocked!)
├── test_agents/             # Agent tests
├── test_scanners/           # Scanner tests
├── test_strategies/         # Strategy tests (new)
├── test_technical_analysis.py
└── test_*.py
```

## Key Testing Patterns

### OpenAI Mocking

OpenAI mocking is automatic via `conftest.py`:

```python
# No need to mock in individual tests!
# The fixture does it automatically
def test_agent_analysis(mock_openai_client):
    mock_openai_client.chat.completions.create.return_value = ...
```

### Trading Logic Tests

Trading logic tests should mock Alpaca API:

```python
from unittest.mock import MagicMock

def test_place_order(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_client",
                       lambda: mock_client)
    # Test order placement
```

### Running Tests

```bash
# Run all tests
uv run pytest tests

# Run specific test file
uv run pytest tests/test_momentum_strategy.py -v

# Run with verbose output
uv run pytest tests/ -vv
```

### Debugging Test Failures

See [debugging.md](debugging.md) for the exact process.
