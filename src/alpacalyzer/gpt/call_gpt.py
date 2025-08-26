import os
from typing import TypeVar, cast

from dotenv import load_dotenv
from openai import OpenAI

T = TypeVar("T")

# Global client variable
_client = None


def get_openai_client():
    """Get or initialize the OpenAI client."""
    global _client

    if _client is None:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "test")
        if api_key is None:
            raise ValueError("Missing OpenAI API Key")

        _client = OpenAI(api_key=api_key)

    return _client


def call_gpt_structured[T](messages, function_schema: type[T]) -> T | None:
    try:
        # Get client only when needed
        client = get_openai_client()

        response = client.responses.parse(
            model="gpt-5-mini",
            reasoning={"effort": "medium"},
            input=messages,
            text_format=function_schema,
        )
        return cast(T, response.output_parsed)
    except Exception as e:
        print(f"Error calling GPT: {e}")
        return None


def call_gpt_web[T](messages, function_schema: type[T]) -> T | None:
    try:
        # Get client only when needed
        client = get_openai_client()

        response = client.responses.parse(
            model="gpt-5-mini",
            tools=[{"type": "web_search_preview"}],
            input=messages,
            text_format=function_schema,
        )
        return cast(T, response.output_parsed)
    except Exception as e:
        print(f"Error calling GPT: {e}")
        return None
