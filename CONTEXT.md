# Domain glossary

## Provider protocol

The wire format selected by `LLM_PROVIDER`. Supported values are `openai`,
`openai-responses`, `gemini`, and `claude`. It does not identify or endorse a
vendor; a compatible service may implement one of these protocols.

## Base URL

The API root supplied through `LLM_BASE_URL`. It may contain a service-specific
path prefix and an existing version segment, but should normally not include the
final operation endpoint.

## Request endpoint

The complete URL used for one operation, such as `/v1/chat/completions` or
`/v1/messages`. It is derived from the Provider protocol, normalized Base URL,
and, for Gemini, the model identifier.

## LLM model

The vision-capable model selected by `LLM_MODEL`. All hCaptcha reasoners use the
same configured model.

## Native protocol adapter

An implementation that constructs the documented request and parses the
documented response for one Provider protocol without translating all traffic
through another vendor SDK.

## hCaptcha agent injection

The single integration seam where the selected native protocol adapter is
assigned to the provider-neutral reasoners created by `hcaptcha-challenger`.
