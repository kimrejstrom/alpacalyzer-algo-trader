# Debugging Procedures

> For complex bugs (especially trading logic), see [Hypothesis-Driven Debugging Guide](debugging-guide.md).

## Debugging Test Failures

**CRITICAL: Follow this exact process!**

```bash
# Step 1: Run ONCE and save output
uv run pytest tests > test-output.txt 2>&1

# Step 2: Identify failing tests
cat test-output.txt | grep "FAILED"

# Step 3: Read error messages BEFORE looking at code
cat test-output.txt | grep -A 20 "Error:"

# Step 4: Run ONLY failing test file
uv run pytest tests/test_failing_module.py -vv
```

**Never run the full test suite repeatedly during debugging!**

## Debugging Runtime Issues

### Log Files

- Log files are stored in `logs/`
- Use structured JSON logging via the `events/` module
- Parse logs with `scripts/agent_metrics_summary.py` for metrics

### Common Issues

**Alpaca API Errors:**

- Verify API keys in `.env`
- Check paper trading vs live trading mode
- Ensure sufficient buying power

**LLM/Agent Errors:**

- Check API key configuration
- Verify `USE_NEW_LLM=true` in `.env` for new LLM abstraction
- Review prompts in `src/alpacalyzer/gpt/`

**Strategy Errors:**

- Check strategy configuration in `.env`
- Verify technical indicators are calculating correctly
- Review position sizing logic
