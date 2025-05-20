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


def call_gpt_structured(messages, function_schema: type[T]) -> T | None:
    try:
        # Get client only when needed
        client = get_openai_client()

        response = client.beta.chat.completions.parse(
            model="o4-mini",
            reasoning_effort="medium",
            messages=messages,
            response_format=function_schema,
        )
        return cast(T, response.choices[0].message.parsed)
    except Exception as e:
        print(f"Error calling GPT: {e}")
        return None
