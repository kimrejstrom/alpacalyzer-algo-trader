import pytest

from alpacalyzer.prompts import load_prompt


def test_load_prompt_valid():
    """Test loading a valid prompt file."""
    prompt = load_prompt("trading_strategist")
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "Chart Pattern Analyst GPT" in prompt


def test_load_prompt_invalid():
    """Test loading a non-existent prompt file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_prompt")


def test_all_prompts_loadable():
    """Verify all markdown prompt files can be loaded."""
    prompt_files = [
        "trading_strategist",
        "portfolio_manager",
        "opportunity_finder_reddit",
        "opportunity_finder_candidates",
        "ben_graham_agent",
        "bill_ackman_agent",
        "cathie_wood_agent",
        "charlie_munger",
        "quant_agent",
        "sentiment_agent",
        "warren_buffet_agent",
    ]
    for name in prompt_files:
        prompt = load_prompt(name)
        assert len(prompt) > 0, f"Prompt {name} is empty"
