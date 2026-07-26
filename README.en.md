# Epic Freebies Helper

[简体中文](README.md)

Automatically signs in to the Epic Games Store, checks the current free games,
and claims titles that are not already owned. It can run in GitHub Actions,
locally, or with Docker, and uses a vision-capable LLM when an hCaptcha challenge
needs to be solved.

This project does not require a particular model vendor or relay.
`LLM_PROVIDER` selects a request protocol, not a vendor brand.

## Features

- Sign-in, free-game discovery, order-history checks, and checkout automation
- Scheduled GitHub Actions run every three days, plus manual dispatch
- Camoufox support with Playwright Firefox fallback
- Four native LLM request protocols
- Log, screenshot, and challenge artifacts for troubleshooting

## Quick start with GitHub Actions

1. Fork this repository.
2. Enable `Epic Freebies Helper (Scheduled)` on the fork's `Actions` page.
3. Open `Settings` → `Secrets and variables` → `Actions`.
4. Create these Secrets:

| Name | Example | Purpose |
| --- | --- | --- |
| `EPIC_EMAIL` | `you@example.com` | Epic account email |
| `EPIC_PASSWORD` | `your-password` | Epic account password |
| `LLM_PROVIDER` | `openai` | Request protocol; defaults to `openai` |
| `LLM_API_KEY` | `sk-...` | API key for the selected service |
| `LLM_BASE_URL` | `https://llm.example.com/v1` | Custom API root |
| `LLM_MODEL` | `your-vision-model` | Must accept image input |

`LLM_PROVIDER`, `LLM_BASE_URL`, and `LLM_MODEL` may instead be GitHub Actions
Variables. The workflow prefers a Variable and falls back to the same-named
Secret. Keep the API key in a Secret.

If an earlier setup used `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and
`OPENAI_MODEL`, rename them to `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`.
`EPIC_EMAIL`, `EPIC_PASSWORD`, and `LLM_PROVIDER=openai` stay unchanged.

Run the workflow manually once after configuration. GitHub will then run it on
the three-day schedule.

## LLM protocols

| `LLM_PROVIDER` | Request endpoint | Version appended when missing |
| --- | --- | --- |
| `openai` | `POST /v1/chat/completions` | `/v1` |
| `openai-responses` | `POST /v1/responses` | `/v1` |
| `gemini` | `POST /v1beta/models/{model}:generateContent` | `/v1beta` |
| `claude` | `POST /v1/messages` | `/v1` |

### Base URL behavior

- An existing custom URL such as `https://your-host/v1` is valid as-is.
- If you enter `https://your-host`, the app appends `/v1`; Gemini appends
  `/v1beta`.
- Existing version segments are preserved, so `/v1/v1` is never produced.
- Enter the API root. Do not append `/chat/completions`, `/responses`,
  `/messages`, or `:generateContent`.
- `LLM_BASE_URL` can be empty when using an official API.
- A compatible service must actually implement the selected protocol. Similar
  endpoint naming alone does not make request bodies interchangeable.

## Local run

Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/) are required.

```powershell
git clone https://github.com/TheWiseWolfHolo/epic-freebies-helper.git
cd epic-freebies-helper
Copy-Item .env.example .env
uv sync
uv run camoufox fetch
$env:ENABLE_APSCHEDULER = "false"
uv run app/deploy.py
```

Edit `.env` with the Epic and LLM settings. In local `.env` files, wrap values
containing `$`, `\`, `#`, or a backtick in single quotes. GitHub Actions Secrets
are unaffected.

## Docker

Copy the Docker environment template, edit it, then run:

```powershell
Set-Location docker
Copy-Item .env.example .env
# Edit .env
docker compose up -d
docker compose logs -f
```

The Compose file uses this project's GHCR image. If the desired version has not
been published, build it from the repository root:

```powershell
docker build -f docker/Dockerfile -t epic-freebies-helper .
```

## Operational notes

- Epic sign-in risk checks and captchas vary with region, public IP, and account
  state. An automated run is not guaranteed to succeed every time.
- Accounts with 2FA may stop at the second-factor step. Consider a separate
  account based on your own security needs; do not weaken a primary account only
  for automation.
- A successful workflow may not produce an email when a title is already owned.
  Use the order-history and claim results in the logs.
- Maintainers cannot inspect Actions in a private fork. Attach sanitized logs,
  screenshots, or artifacts when reporting an issue.
- Follow the terms of Epic Games, your model service, and GitHub. You are
  responsible for account and automation risks.

See [Advanced configuration](docs/advanced.en.md) and the
[maintenance log](docs/maintenance-log.md) for more detail.

## Lineage

This project continues work from the open-source Epic automation community,
including:

- [Ronchy2000/epic-freebies-helper](https://github.com/Ronchy2000/epic-freebies-helper)
- [QIN2DIM/epic-awesome-gamer](https://github.com/QIN2DIM/epic-awesome-gamer)
- [10000ge10000/epic-kiosk](https://github.com/10000ge10000/epic-kiosk)

Licensed under the [GNU General Public License v3.0](LICENSE).
