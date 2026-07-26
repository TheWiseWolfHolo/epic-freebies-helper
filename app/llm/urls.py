"""Provider-aware Base URL normalization and endpoint construction."""

from __future__ import annotations

import re
from enum import Enum
from urllib.parse import quote, urlsplit, urlunsplit


class LLMProvider(str, Enum):
    OPENAI = "openai"
    OPENAI_RESPONSES = "openai-responses"
    GEMINI = "gemini"
    CLAUDE = "claude"


DEFAULT_BASE_URLS = {
    LLMProvider.OPENAI: "https://api.openai.com/v1",
    LLMProvider.OPENAI_RESPONSES: "https://api.openai.com/v1",
    LLMProvider.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
    LLMProvider.CLAUDE: "https://api.anthropic.com/v1",
}

_VERSION_SEGMENT = re.compile(r"(?:^|/)v\d+(?:beta\d*)?(?:/|$)", re.IGNORECASE)
_KNOWN_ENDPOINT_SUFFIXES = ("/chat/completions", "/responses", "/messages")


def _coerce_provider(provider: LLMProvider | str) -> LLMProvider:
    if isinstance(provider, LLMProvider):
        return provider
    return LLMProvider(str(provider).strip().lower())


def normalize_base_url(provider: LLMProvider | str, base_url: str | None) -> str:
    """Normalize a provider API root without duplicating its version segment."""
    provider = _coerce_provider(provider)
    candidate = (base_url or DEFAULT_BASE_URLS[provider]).strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("LLM_BASE_URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("LLM_BASE_URL must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("LLM_BASE_URL must not include a query string or fragment")

    path = parsed.path.rstrip("/")
    is_full_endpoint = path.endswith(_KNOWN_ENDPOINT_SUFFIXES) or path.endswith(":generateContent")
    if not is_full_endpoint and not _VERSION_SEGMENT.search(path):
        version = "v1beta" if provider is LLMProvider.GEMINI else "v1"
        path = f"{path}/{version}" if path else f"/{version}"

    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def build_endpoint(provider: LLMProvider | str, base_url: str | None, *, model: str) -> str:
    """Build the concrete request endpoint for one provider protocol."""
    provider = _coerce_provider(provider)
    normalized = normalize_base_url(provider, base_url)
    path = urlsplit(normalized).path

    expected_suffix = {
        LLMProvider.OPENAI: "/chat/completions",
        LLMProvider.OPENAI_RESPONSES: "/responses",
        LLMProvider.CLAUDE: "/messages",
    }.get(provider)

    if provider is LLMProvider.GEMINI:
        if path.endswith(":generateContent"):
            return normalized
        if path.endswith(_KNOWN_ENDPOINT_SUFFIXES):
            raise ValueError(
                "LLM_BASE_URL points to a different protocol endpoint; " "expected :generateContent"
            )
        model_id = quote(model.strip(), safe="-._")
        return f"{normalized}/models/{model_id}:generateContent"

    if path.endswith(":generateContent"):
        raise ValueError(
            f"LLM_BASE_URL points to a different protocol endpoint; expected {expected_suffix}"
        )
    if path.endswith(_KNOWN_ENDPOINT_SUFFIXES):
        if not path.endswith(expected_suffix):
            raise ValueError(
                f"LLM_BASE_URL points to a different protocol endpoint; expected {expected_suffix}"
            )
        return normalized
    return f"{normalized}{expected_suffix}"
