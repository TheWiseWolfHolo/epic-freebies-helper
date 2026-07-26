# Advanced configuration and troubleshooting

## Configuration model

The project exposes one provider-neutral LLM configuration:

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-vision-model
```

`LLM_PROVIDER` selects the wire protocol. The API key, Base URL, and model must
all belong to the same service.

## Protocol requests

### `openai`

- Request: `POST {base}/chat/completions`
- Images: OpenAI Chat Completions `image_url` data URIs
- Structured output: JSON Object plus the response schema in the prompt

### `openai-responses`

- Request: `POST {base}/responses`
- Images: Responses API `input_image` data URIs
- Structured output: `text.format` JSON Schema

### `gemini`

- Request: `POST {base}/models/{model}:generateContent`
- Images: native Gemini `inlineData`
- Structured output: `responseMimeType=application/json` and
  `responseJsonSchema`
- API key: `x-goog-api-key` header

### `claude`

- Request: `POST {base}/messages`
- Images: native Claude base64 image blocks
- Structured output: `output_config.format` JSON Schema
- API key: `x-api-key` header

All adapters share retry handling, HTTP error reporting, JSON extraction,
Pydantic schema validation, and response caching.

## Base URL normalization

The app normalizes `LLM_BASE_URL` to an API root before adding the protocol
endpoint:

1. Remove a trailing slash.
2. Reject non-HTTP(S) URLs, query strings, and fragments.
3. When no version segment exists:
   - append `/v1` for `openai`, `openai-responses`, and `claude`
   - append `/v1beta` for `gemini`
4. Preserve an existing version segment.
5. Append the selected protocol endpoint.

As a result, `https://host.example/v1` stays unchanged and
`https://host.example` becomes `https://host.example/v1`; `/v1/v1` is not
produced. Gemini uses `/v1beta`, so do not apply the OpenAI `/v1` convention to
it manually.

Full endpoints are recognized, but entering the API root is recommended. It
makes protocol mismatches visible when changing `LLM_PROVIDER`.

## GitHub Actions variables

Recommended storage:

- Secrets: `EPIC_EMAIL`, `EPIC_PASSWORD`, `LLM_API_KEY`
- Variables: `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`

The last three may also be same-named Secrets for migration compatibility.
Variables take precedence.

Legacy variables are not read:

- `OPENAI_*`
- `GEMINI_*`
- `GLM_*`
- the four per-task hCaptcha model overrides

Every hCaptcha reasoner uses `LLM_MODEL`, preventing one challenge from silently
crossing protocols or models.

## Common failures

### `Invalid LLM configuration: LLM_API_KEY is empty`

The current environment does not provide `LLM_API_KEY`. Store it as a GitHub
Actions Secret.

### `Invalid LLM configuration: LLM_MODEL is empty`

No model was selected. It must support image input.

### HTTP 404

Check that:

- `LLM_PROVIDER` matches the protocol implemented by the service
- `LLM_BASE_URL` is an API address, not a dashboard address
- the service does not require an additional fixed path prefix
- a full endpoint was not paired with another protocol

### HTTP 401 / 403

Verify that the key belongs to the selected service, has access to the model,
and uses the authentication headers expected by that protocol.

### Schema validation failure

The service may be ignoring structured-output controls, or the model may not be
reliable for image-to-JSON work. The app surfaces this error. Inspect the logs
and cached hCaptcha response for the original output.

## Implementation boundary

`app/llm/provider.py` owns protocol serialization and parsing,
`app/llm/urls.py` owns URLs, and `app/llm/agent.py` is the only injection point
for the private `hcaptcha-challenger` reasoners. If a dependency update breaks
that seam, repair this file instead of introducing another global monkey patch.
