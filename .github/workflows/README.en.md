# GitHub Actions configuration

The `epic-gamer.yml` workflow (`Epic Freebies Helper (Scheduled)`) supports
manual dispatch and runs every three days on its schedule.

## Required configuration

Open `Settings` → `Secrets and variables` → `Actions`.

Secrets:

| Name | Purpose |
| --- | --- |
| `EPIC_EMAIL` | Epic account email |
| `EPIC_PASSWORD` | Epic account password |
| `LLM_API_KEY` | API key for the selected LLM service |

Variables (same-named Secrets are also accepted):

| Name | Purpose |
| --- | --- |
| `LLM_PROVIDER` | `openai`, `openai-responses`, `gemini`, or `claude` |
| `LLM_BASE_URL` | Custom API root; may be empty for an official API |
| `LLM_MODEL` | A model that supports image input |

A Variable takes precedence over a same-named Secret. `LLM_API_KEY` is read only
from a Secret.

## OpenAI-format example

```text
LLM_PROVIDER=openai
LLM_API_KEY=your-key
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-vision-model
```

An existing `/v1` is preserved. If no version segment exists, the app appends
`/v1`. Do not append `/chat/completions`.

## Other protocols

| Protocol | Generated request path |
| --- | --- |
| `openai-responses` | `/v1/responses` |
| `gemini` | `/v1beta/models/{model}:generateContent` |
| `claude` | `/v1/messages` |

Gemini uses `/v1beta`, unlike the other three protocols.

## Running and troubleshooting

After initial configuration, manually run `Epic Freebies Helper (Scheduled)` from
the `Actions` page. The workflow uploads:

- `epic-runtime-*`: runtime state and challenge artifacts
- `epic-logs-*`: logs
- `epic-screenshots-*`: screenshots

GitHub shows only artifacts that contain files. When reporting a problem from a
private fork, attach the relevant artifacts after removing account data, keys,
cookies, and other sensitive values.

Legacy `OPENAI_*`, `GEMINI_*`, and `GLM_*` variables are no longer read.
