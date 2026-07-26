# ADR 0001: Use native protocol adapters for LLM access

- Status: Accepted
- Date: 2026-07-26

## Context

The previous configuration exposed vendor-specific Gemini and GLM settings and
patched a Gemini SDK globally to redirect requests. That made configuration
semantics unclear, coupled unrelated providers to one SDK, and caused relay
defaults to look like project requirements.

The project needs custom API roots and four request formats: OpenAI Chat
Completions, OpenAI Responses, Gemini GenerateContent, and Claude Messages.

## Decision

Expose one provider-neutral configuration:

- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

Implement each supported wire protocol directly with HTTP. Normalize Base URLs
centrally, append `/v1` when missing for OpenAI, Responses, and Claude, and
append `/v1beta` for Gemini. Inject the selected adapter into the
provider-neutral hCaptcha reasoners from one local integration point.

Do not provide a default third-party relay, recommended vendor, hidden provider
fallback, or cross-provider key fallback.

## Consequences

- Users can point each protocol at an official API or a genuinely compatible
  custom service.
- Request and response behavior is explicit and testable without global SDK
  mutation.
- Legacy `OPENAI_*`, `GEMINI_*`, and `GLM_*` environment variables are removed.
- All hCaptcha tasks use one configured model.
- The injection point depends on private `hcaptcha-challenger` reasoner fields;
  this dependency is isolated in `app/llm/agent.py` and must be checked when the
  library is upgraded.
