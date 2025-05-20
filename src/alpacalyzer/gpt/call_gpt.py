import os
from typing import TypeVar, cast

from dotenv import load_dotenv
from openai import OpenAI

T = TypeVar("T")

load_dotenv()
client = OpenAI()
api_key = os.getenv("OPENAI_API_KEY", "test")
if api_key is None:
    raise ValueError("Missing OpenAI API Key")
client.api_key = api_key


def call_gpt_structured(messages, function_schema: type[T]) -> T | None:
    try:
        response = client.beta.chat.completions.parse(
            model="o3-mini",
            reasoning_effort="medium",
            messages=messages,
            response_format=function_schema,
        )
        return cast(T, response.choices[0].message.parsed)
    except Exception as e:
        print(f"Error calling GPT: {e}")
        return None
