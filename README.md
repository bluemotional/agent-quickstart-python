# Realtime Voice Agent for Railway

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Bun](https://img.shields.io/badge/bun-latest-black)](https://bun.sh/)

Deploy an Agora voice agent on Railway with Python and Next.js.

Bring your own Agora credentials.

This repository provides a deployable Agora voice agent template for Railway and serves as the Railway template source for `bluemotional/agent-quickstart-python`.

Build a production-style voice agent with a Next.js web client and Python FastAPI backend. This template includes live transcript, agent visualizer ([Agent UIKit](https://agoraio-conversational-ai.github.io/agent-uikit/)), and managed STT/LLM/TTS defaults.

## Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Bun](https://bun.sh/)
- [Agora CLI](https://github.com/AgoraIO/cli)

## Deploy on Railway

This template is meant to be published as a Railway template listing.

The Railway template listing is the primary discovery surface. The GitHub repository is `bluemotional/agent-quickstart-python`, the developer-controlled fork used as the template source repo.

### Template Identity

- Template name: `Realtime Voice Agent`
- Subtitle: `Built with Agora, Python, and Next.js`
- Primary CTA: `Deploy on Railway`
- Credential note: `Bring your own Agora credentials`

### Get Your Credentials

These are the deployer's own Agora credentials, not the template author's.

1. Run `agora login`
2. Run `agora project use <project>`
3. Run `agora project env --with-secrets`
4. Copy `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE`
5. Paste them into Railway Variables

### Deploy

Deploy `web` as a Next.js app and `server` as a reachable Python service.
Railway builds both services from source and installs their runtime dependencies during deployment, so there is no separate SDK download step for users.

Set the `server` service root directory to `server` and point its config file at `/server/railway.json`.
Do the same for `web` with root directory `web` and config file `/web/railway.json`.

Browser-facing `/api/*` routes in Next proxy to FastAPI via the `server` service's private domain and listening port:

```bash
AGENT_BACKEND_URL=http://${{server.RAILWAY_PRIVATE_DOMAIN}}:${{server.PORT}}
```

Set backend env values:

```bash
AGORA_APP_ID=your_agora_app_id
AGORA_APP_CERTIFICATE=your_agora_app_certificate
AGENT_GREETING=optional_custom_greeting
```

This repository is intended to be published as `bluemotional/agent-quickstart-python`, the Railway template source repo. The official Agora quickstart remains upstream only.

## Run Locally

Use this path if you want to run **this Railway template source repo** locally:

```bash
git clone https://github.com/bluemotional/agent-quickstart-python.git
cd agent-quickstart-python
agora login
agora project use <your-project>
bun run setup
agora project env write server/.env.local
bun run doctor:local
bun run dev
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

If the agent does not join or transcripts do not appear, run **`agora project doctor --deep`** to check credentials, feature enablement, network reachability, and local env binding.

### Optional: scaffold a fresh official quickstart instead

If you want the upstream general-purpose quickstart rather than this Railway-oriented fork:

1. Install the Agora CLI and sign in
2. Run `agora init my-python-demo --template python`
3. `cd my-python-demo && bun run setup && bun run dev`

To export local env values from the Agora CLI-bound project:

```bash
agora project use <your-project>
agora project env write server/.env.local
rg "^(AGORA_APP_ID|AGORA_APP_CERTIFICATE)=" server/.env.local
```

Railway uses `server/` for the Python service and `web/` for the Next.js service. The template includes `railway.json` files in both service directories, and Railway service settings should point at `/server/railway.json` and `/web/railway.json` because config-as-code files do not follow the root-directory path.

## Environment variables

Primary backend env file: [`server/.env.example`](server/.env.example).

| Variable | Required | Default | Notes |
| --- | :---: | :---: | --- |
| `AGORA_APP_ID` | ✅ | — | Agora Console -> Project -> App ID |
| `AGORA_APP_CERTIFICATE` | ✅ | — | Agora Console -> Project -> App Certificate (server only) |
| `AGENT_GREETING` |  | built-in greeting | Optional opening line override |
| `PORT` |  | `8000` | FastAPI server port |
| `AGENT_BACKEND_URL` (web deploy) | ✅ | — | Required in deployed `web` app when proxying to the `server` service over Railway private networking |

> **Default vs BYOK** — this quickstart defaults to Agora-managed STT + LLM + TTS in the backend. Enable BYOK by uncommenting provider blocks in `server/src/agent.py` and adding matching keys.

## Commands

```bash
# Dev
bun run setup
bun run dev

# Quality
bun run doctor
bun run doctor:local
bun run verify:backend

# CI / pre-ship
bun run verify:web
bun run verify:local
bun run verify
```

Run `bun run verify` before shipping web-only changes, and `bun run verify:local` when backend behavior changed.

Tests run standalone (no Agora cloud needed): `pytest` in `server/`, `bun test` in `web/`. CI runs them on Linux/macOS/Windows × Python 3.10 & 3.13.

## Architecture

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./.github/images/system-architecture-dark.svg">
  <img src="./.github/images/system-architecture.svg" alt="System architecture">
</picture>

The browser talks to Next.js `/api/*` routes. In local mode, Next rewrites those routes to FastAPI using `AGENT_BACKEND_URL=http://localhost:8000`; FastAPI owns token generation and agent start/stop logic.

## What You Get

- Next.js web client (`web/`) with transcript UI and agent visualizer
- FastAPI backend (`server/`) for token generation and agent lifecycle
- `/api/get_config`, `/api/startAgent`, and `/api/stopAgent` browser-facing contract
- Managed default pipeline (Deepgram STT, OpenAI LLM, MiniMax TTS)

## How It Works

1. Browser requests connection config from `/api/get_config`.
2. Backend generates combined RTC+RTM config and returns channel + token.
3. Browser joins RTC/RTM and starts streaming audio.
4. Browser calls `/api/startAgent`; backend starts the cloud agent session.
5. Browser receives transcript and state updates over RTM, and `/api/stopAgent` ends the session.

## Repo Map

- `web/` — Next.js 16 + React 19 + TypeScript frontend
- `server/` — Python FastAPI backend + Agora Agent Server SDK integration
- `ARCHITECTURE.md` — system-level flow and ownership boundaries
- `AGENTS.md` — contributor agent instructions

## Troubleshooting

- **Agent does not join or transcripts are missing:** run `agora project doctor --deep`.
- **Missing credentials:** run `agora project env write server/.env.local`.
- **Auth errors from backend:** confirm `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE` are set in `server/.env.local`.
- **Frontend cannot reach backend:** confirm `AGENT_BACKEND_URL=http://localhost:8000` in local frontend scripts.
- **Unsure who owns `/api/*`:** Next owns browser-facing `/api/*`; FastAPI owns `/get_config`, `/startAgent`, `/stopAgent`.

## More Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [AGENTS.md](./AGENTS.md)
- [docs/ai/L1/02_architecture.md](./docs/ai/L1/02_architecture.md) — full-stack topology and lifecycle
- [docs/ai/L1/03_code_map.md](./docs/ai/L1/03_code_map.md) — curated `web/` + `server/` file map

## License

Released under the [MIT License](./LICENSE).
