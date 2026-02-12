"""Prompt loading utilities for externalized agent prompts."""

from importlib.resources import files

_PROMPTS_PACKAGE = "alpacalyzer.prompts"


def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt from the prompts package.

    Args:
        prompt_name: Name of the prompt file (without .md extension)

    Returns:
        The prompt content as a string

    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    try:
        prompt_file = files(_PROMPTS_PACKAGE).joinpath(f"{prompt_name}.md")
        return prompt_file.read_text(encoding="utf-8")
    except Exception as e:
        raise FileNotFoundError(f"Prompt '{prompt_name}' not found: {e}")
