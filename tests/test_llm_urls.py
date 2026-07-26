import pytest

from llm.urls import LLMProvider, build_endpoint, normalize_base_url


@pytest.mark.parametrize(
    ("provider", "base_url", "expected"),
    [
        ("openai", "https://llm.example.com", "https://llm.example.com/v1"),
        ("openai", "https://llm.example.com/v1", "https://llm.example.com/v1"),
        ("openai-responses", "https://llm.example.com/api", "https://llm.example.com/api/v1"),
        ("claude", "https://llm.example.com/", "https://llm.example.com/v1"),
        ("gemini", "https://llm.example.com", "https://llm.example.com/v1beta"),
        ("gemini", "https://llm.example.com/v1beta", "https://llm.example.com/v1beta"),
    ],
)
def test_normalize_base_url(provider, base_url, expected):
    assert normalize_base_url(provider, base_url) == expected


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("openai", "https://api.example.com/v1/chat/completions"),
        ("openai-responses", "https://api.example.com/v1/responses"),
        ("claude", "https://api.example.com/v1/messages"),
        ("gemini", "https://api.example.com/v1beta/models/vision-model:generateContent"),
    ],
)
def test_build_endpoint_uses_native_protocol(provider, expected):
    assert build_endpoint(provider, "https://api.example.com", model="vision-model") == expected


def test_existing_openai_v1_is_not_duplicated():
    endpoint = build_endpoint(
        LLMProvider.OPENAI, "https://api.example.com/v1", model="vision-model"
    )
    assert endpoint == "https://api.example.com/v1/chat/completions"


def test_full_matching_endpoint_is_preserved():
    endpoint = build_endpoint(
        LLMProvider.OPENAI_RESPONSES, "https://api.example.com/v1/responses", model="vision-model"
    )
    assert endpoint == "https://api.example.com/v1/responses"


@pytest.mark.parametrize(
    "base_url",
    [
        "not-a-url",
        "https://user:secret@api.example.com",
        "https://api.example.com?token=secret",
        "https://api.example.com/#fragment",
    ],
)
def test_invalid_base_url_is_rejected(base_url):
    with pytest.raises(ValueError):
        normalize_base_url("openai", base_url)


@pytest.mark.parametrize(
    ("provider", "wrong_endpoint"),
    [
        ("openai", "https://api.example.com/v1/messages"),
        ("openai-responses", "https://api.example.com/v1/chat/completions"),
        ("claude", "https://api.example.com/v1/responses"),
        ("gemini", "https://api.example.com/v1/chat/completions"),
        ("openai", "https://api.example.com/v1beta/models/model:generateContent"),
    ],
)
def test_cross_protocol_full_endpoint_is_rejected(provider, wrong_endpoint):
    with pytest.raises(ValueError):
        build_endpoint(provider, wrong_endpoint, model="vision-model")
