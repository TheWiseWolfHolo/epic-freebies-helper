"""Native HTTP implementations of the supported multimodal LLM protocols."""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, TypeVar

import httpx
from loguru import logger
from pydantic import BaseModel

from llm.urls import LLMProvider, build_endpoint

ResponseT = TypeVar("ResponseT", bound=BaseModel)

_MAX_ERROR_BODY = 1500
_REQUEST_ATTEMPTS = 3
_REQUEST_TIMEOUT_SECONDS = 120.0


def _schema_name(schema: type[BaseModel]) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", schema.__name__)[:64] or "captcha_response"


def _data_uri(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _base64_image(path: Path) -> tuple[str, str]:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return mime_type, base64.b64encode(path.read_bytes()).decode("ascii")


def _json_instruction(schema: type[BaseModel]) -> str:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
    return (
        "Return only one JSON value that strictly matches this JSON Schema. "
        "Do not wrap it in Markdown or add explanations.\n"
        f"{schema_json}"
    )


def _extract_json_value(text: str) -> Any:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", candidate, re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    starts = [index for token in ("{", "[") if (index := candidate.find(token)) >= 0]
    if not starts:
        raise ValueError("LLM response does not contain JSON")
    start = min(starts)
    closing = "}" if candidate[start] == "{" else "]"
    end = candidate.rfind(closing)
    if end <= start:
        raise ValueError("LLM response contains incomplete JSON")
    return json.loads(candidate[start : end + 1])


class NativeLLMProvider:
    """Common request, validation, retry, and artifact behavior."""

    def __init__(self, *, provider: LLMProvider, api_key: str, base_url: str | None, model: str):
        self.provider = provider
        self.api_key = api_key.strip()
        self.model = model.strip()
        if not self.api_key:
            raise ValueError("LLM_API_KEY must not be empty")
        if not self.model:
            raise ValueError("LLM_MODEL must not be empty")
        self.endpoint = build_endpoint(provider, base_url, model=self.model)
        self._last_response: dict[str, Any] | None = None

    async def generate_with_images(
        self,
        *,
        images: list[Path],
        response_schema: type[ResponseT],
        user_prompt: str | None = None,
        description: str | None = None,
        **kwargs,
    ) -> ResponseT:
        valid_images = [Path(path) for path in images if path and Path(path).is_file()]
        payload, headers = self._build_request(
            images=valid_images,
            response_schema=response_schema,
            user_prompt=user_prompt,
            description=description,
            kwargs=kwargs,
        )
        data = await self._post(payload=payload, headers=headers)
        self._last_response = data
        text = self._extract_text(data)
        parsed = _extract_json_value(text)
        return response_schema.model_validate(parsed)

    def cache_response(self, path: Path) -> None:
        if self._last_response is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self._last_response, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Failed to cache {} response: {!r}", self.provider.value, exc)

    async def _post(self, *, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        timeout = httpx.Timeout(_REQUEST_TIMEOUT_SECONDS, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, _REQUEST_ATTEMPTS + 1):
                try:
                    response = await client.post(self.endpoint, headers=headers, json=payload)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt == _REQUEST_ATTEMPTS:
                        raise
                    logger.warning(
                        "{} transport failure; retrying ({}/{}) | error={!r}",
                        self.provider.value,
                        attempt,
                        _REQUEST_ATTEMPTS,
                        exc,
                    )
                    await asyncio.sleep(attempt)
                    continue

                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < _REQUEST_ATTEMPTS:
                        logger.warning(
                            "{} transient HTTP {}; retrying ({}/{})",
                            self.provider.value,
                            response.status_code,
                            attempt,
                            _REQUEST_ATTEMPTS,
                        )
                        await asyncio.sleep(attempt)
                        continue

                if response.is_error:
                    body = response.text[:_MAX_ERROR_BODY]
                    raise RuntimeError(
                        f"{self.provider.value} request failed with HTTP "
                        f"{response.status_code}: {body}"
                    )
                try:
                    return response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        f"{self.provider.value} returned a non-JSON HTTP response"
                    ) from exc

        raise RuntimeError(f"{self.provider.value} request failed without a response")

    def _build_request(
        self,
        *,
        images: list[Path],
        response_schema: type[BaseModel],
        user_prompt: str | None,
        description: str | None,
        kwargs: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        raise NotImplementedError

    def _extract_text(self, data: dict[str, Any]) -> str:
        raise NotImplementedError


class OpenAIChatProvider(NativeLLMProvider):
    def _build_request(
        self,
        *,
        images: list[Path],
        response_schema: type[BaseModel],
        user_prompt: str | None,
        description: str | None,
        kwargs: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        system = "\n\n".join(
            part for part in (description, _json_instruction(response_schema)) if part
        )
        content: list[dict[str, Any]] = []
        if user_prompt:
            content.append({"type": "text", "text": user_prompt})
        content.extend(
            {"type": "image_url", "image_url": {"url": _data_uri(image)}} for image in images
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        return payload, {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("OpenAI Chat response does not contain choices")
        content = (choices[0].get("message") or {}).get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        raise ValueError("OpenAI Chat response does not contain text")


class OpenAIResponsesProvider(NativeLLMProvider):
    def _build_request(
        self,
        *,
        images: list[Path],
        response_schema: type[BaseModel],
        user_prompt: str | None,
        description: str | None,
        kwargs: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        user_content: list[dict[str, Any]] = []
        if user_prompt:
            user_content.append({"type": "input_text", "text": user_prompt})
        user_content.extend(
            {"type": "input_image", "image_url": _data_uri(image)} for image in images
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": description or ""}]},
                {"role": "user", "content": user_content},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": _schema_name(response_schema),
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                }
            },
        }
        return payload, {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_text(self, data: dict[str, Any]) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        parts: list[str] = []
        for output in data.get("output") or []:
            if not isinstance(output, dict) or output.get("type") != "message":
                continue
            for content in output.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    parts.append(str(content.get("text") or ""))
        if parts:
            return "\n".join(parts)
        raise ValueError("OpenAI Responses response does not contain output text")


class GeminiProvider(NativeLLMProvider):
    def _build_request(
        self,
        *,
        images: list[Path],
        response_schema: type[BaseModel],
        user_prompt: str | None,
        description: str | None,
        kwargs: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        parts: list[dict[str, Any]] = []
        if user_prompt:
            parts.append({"text": user_prompt})
        for image in images:
            mime_type, encoded = _base64_image(image)
            parts.append({"inlineData": {"mimeType": mime_type, "data": encoded}})

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": response_schema.model_json_schema(),
            },
        }
        if description:
            payload["systemInstruction"] = {"parts": [{"text": description}]}
        return payload, {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    def _extract_text(self, data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini response does not contain candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
        if text:
            return text
        raise ValueError("Gemini response does not contain text")


class ClaudeProvider(NativeLLMProvider):
    def _build_request(
        self,
        *,
        images: list[Path],
        response_schema: type[BaseModel],
        user_prompt: str | None,
        description: str | None,
        kwargs: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        content: list[dict[str, Any]] = []
        if user_prompt:
            content.append({"type": "text", "text": user_prompt})
        for image in images:
            mime_type, encoded = _base64_image(image)
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime_type, "data": encoded},
                }
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": description or "",
            "messages": [{"role": "user", "content": content}],
            "output_config": {
                "format": {"type": "json_schema", "schema": response_schema.model_json_schema()}
            },
        }
        return payload, {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _extract_text(self, data: dict[str, Any]) -> str:
        content = data.get("content") or []
        text = "\n".join(
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
        if text:
            return text
        raise ValueError("Claude response does not contain text")


_PROVIDER_TYPES = {
    LLMProvider.OPENAI: OpenAIChatProvider,
    LLMProvider.OPENAI_RESPONSES: OpenAIResponsesProvider,
    LLMProvider.GEMINI: GeminiProvider,
    LLMProvider.CLAUDE: ClaudeProvider,
}


def create_llm_provider(settings: Any) -> NativeLLMProvider:
    provider = LLMProvider(str(settings.LLM_PROVIDER).strip().lower())
    api_key = settings.LLM_API_KEY
    if hasattr(api_key, "get_secret_value"):
        api_key = api_key.get_secret_value()
    return _PROVIDER_TYPES[provider](
        provider=provider,
        api_key=str(api_key or ""),
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )
