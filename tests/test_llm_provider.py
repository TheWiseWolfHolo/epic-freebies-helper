from pathlib import Path

import pytest
from pydantic import BaseModel

from llm.provider import (
    ClaudeProvider,
    GeminiProvider,
    OpenAIChatProvider,
    OpenAIResponsesProvider,
    _extract_json_value,
)
from llm.urls import LLMProvider


class ExampleResult(BaseModel):
    answer: str


@pytest.fixture
def image_path(tmp_path: Path) -> Path:
    path = tmp_path / "challenge.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return path


def _build(provider_type, provider, image_path):
    adapter = provider_type(
        provider=provider,
        api_key="secret",
        base_url="https://api.example.com",
        model="vision-model",
    )
    return adapter._build_request(
        images=[image_path],
        response_schema=ExampleResult,
        user_prompt="Solve this",
        description="Return the answer",
        kwargs={},
    )


def test_openai_chat_payload_uses_messages_and_image_url(image_path):
    payload, headers = _build(OpenAIChatProvider, LLMProvider.OPENAI, image_path)

    assert payload["model"] == "vision-model"
    assert payload["messages"][1]["content"][1]["type"] == "image_url"
    assert payload["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert headers["Authorization"] == "Bearer secret"


def test_openai_responses_payload_uses_input_image_and_json_schema(image_path):
    payload, _ = _build(OpenAIResponsesProvider, LLMProvider.OPENAI_RESPONSES, image_path)

    assert payload["input"][1]["content"][1]["type"] == "input_image"
    assert payload["text"]["format"]["type"] == "json_schema"


def test_gemini_payload_uses_inline_data(image_path):
    payload, headers = _build(GeminiProvider, LLMProvider.GEMINI, image_path)

    assert payload["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/png"
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert headers["x-goog-api-key"] == "secret"


def test_claude_payload_uses_native_image_block(image_path):
    payload, headers = _build(ClaudeProvider, LLMProvider.CLAUDE, image_path)

    assert payload["messages"][0]["content"][1]["type"] == "image"
    assert payload["messages"][0]["content"][1]["source"]["type"] == "base64"
    assert payload["output_config"]["format"]["type"] == "json_schema"
    assert headers["x-api-key"] == "secret"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"answer":"ok"}', {"answer": "ok"}),
        ('```json\n{"answer":"ok"}\n```', {"answer": "ok"}),
        ('Result: {"answer":"ok"} done', {"answer": "ok"}),
    ],
)
def test_extract_json_value(raw, expected):
    assert _extract_json_value(raw) == expected


def test_empty_credentials_are_rejected():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        OpenAIChatProvider(
            provider=LLMProvider.OPENAI, api_key="", base_url=None, model="vision-model"
        )
