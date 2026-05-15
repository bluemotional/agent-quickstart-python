# Managed Agent Config

> **When to Read This:** Load this document when you are changing the agent's prompt, voice, VAD behavior, model selection, session options, or wiring a bring-your-own-key (BYOK) provider on the Python side.

## Where It Lives

All managed agent configuration is in `server/src/agent.py`. The browser sends `{ channelName, rtcUid, userUid }` to `POST /startAgent`, which the FastAPI handler forwards to `agent.start(...)`. That method builds an SDK-driven agent and creates an async session.

## The Agent Builder Chain

```python
from agora_agent.agentkit import AsyncAgora, AgoraAgent
from agora_agent.agentkit.vendors import OpenAI, DeepgramSTT, MiniMaxTTS

async def start(self, channel_name: str, rtc_uid: int, user_uid: int):
    agora = AsyncAgora(
        app_id=os.environ["AGORA_APP_ID"],
        app_certificate=os.environ["AGORA_APP_CERTIFICATE"],
    )
    agent = (
        AgoraAgent(agora=agora,
                   instructions=ADA_PROMPT,
                   greeting=os.environ.get("AGENT_GREETING") or DEFAULT_GREETING,
                   failure_message="Please wait a moment.")
        .with_stt(DeepgramSTT(model="nova-3", language="en"))
        .with_llm(OpenAI(model="gpt-4o-mini"))
        .with_tts(MiniMaxTTS(model="speech_2_6_turbo",
                              voice_id="English_captivating_female1"))
    )

    session = await agent.create_async_session(
        channel_name=channel_name,
        remote_uids=[str(user_uid)],
        enable_string_uid=False,
        idle_timeout=30,
        expires_in=3600,
        data_channel="rtm",
        advanced_features={"enable_rtm": True, "enable_tools": True},
        parameters={
            "data_channel": "rtm",
            "enable_error_message": True,
            "enable_metrics": True,
        },
        turn_detection={
            "start": {"type": "vad", ...},
            "end":   {"type": "vad", ...},
        },
    )
    await session.start()
    return session.agent_id, session.status
```

The exact field names track `agora-agent-server-sdk`. The requirement is unpinned in `server/requirements.txt`, so re-verify field names after upgrades.

## Editing Each Surface

### Change the prompt

Edit the `ADA_PROMPT` string constant at the top of `agent.py`. Keep it concise — long prompts amplify LLM latency.

### Change the greeting

Set `AGENT_GREETING` in `server/.env.local`, or change `DEFAULT_GREETING` in `agent.py`.

### Change VAD

Edit the `turn_detection` dict. Tuning notes:

- VAD `speech_threshold` — activation sensitivity (0.0–1.0). Lower values trigger on quieter audio.
- VAD `interrupt_duration_ms` — minimum user speech before the agent yields. Lower = more responsive interruptions.
- VAD `prefix_padding_ms` — audio captured before VAD triggers; raise if early phonemes are clipped.
- VAD `silence_duration_ms` — silence after speech before VAD ends the turn. Raise for slow speakers.

### Swap STT / LLM / TTS

Replace the corresponding constructor:

```python
.with_stt(DeepgramSTT(model="...", language="...", api_key=os.environ.get("DEEPGRAM_API_KEY")))
.with_llm(OpenAI(model="...", api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_BASE_URL")))
.with_tts(MiniMaxTTS(model="...", voice_id="...", api_key=os.environ.get("MINIMAX_API_KEY")))
```

For a BYOK provider, document the new env var in `server/.env.example`.

### Session-Level Tuning

- `idle_timeout` (seconds) — drop to 15 for short demos.
- `expires_in` (seconds) — keep aligned with `token_expire` in `get_config`.
- `enable_string_uid` — `False` keeps UIDs numeric for both RTC and RTM. Flipping to `True` requires matching changes in the browser join path.
- `data_channel` — `"rtm"` keeps transcripts and metrics flowing on RTM. `"sct"` is the alternative; the toolkit on the client side must match.

## Async Lifetime

`Agent` is constructed once at module import (`agent = Agent()` in `server.py`). Every request reuses the same instance. `Agent.start` returns the new session metadata; `Agent.stop(agent_id)` ends the corresponding session.

Do not hold per-request state on `Agent`. If you need correlation, use the returned `agent_id` and pass it through subsequent calls.

## Response Contract

`startAgent` returns:

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "agent_id": "string",
    "channel_name": "string",
    "status": "running"
  }
}
```

The client stores `agent_id` in `agoraData` and later passes it to `/api/stopAgent`.

## Verification

`bun run verify:backend` runs `py_compile` so syntax errors surface, but it does not exercise behavior. `bun run verify:local:fastapi` runs the FastAPI app with `FakeAgent` patched in to ensure routes match expected shapes without touching the real Agora cloud.

After editing `agent.py`, run:

```bash
bun run verify:backend
bun run verify:local:fastapi
bun run verify:web:api
```

## Failure Modes

| Symptom                                                | Cause                                                                  |
| ------------------------------------------------------ | ---------------------------------------------------------------------- |
| App fails to boot with `KeyError: 'AGORA_APP_ID'`      | Missing env vars; `Agent()` reads them at import time.                  |
| `400` from `/startAgent` on a valid request            | `Agent.start` raised `ValueError` — usually missing UID fields.         |
| Agent joins but never speaks                           | TTS BYOK key missing or wrong `voice_id`.                                |
| Agent state stuck in `IDLE`                            | `enable_rtm` missing from `advanced_features` or RTM not subscribed yet. |
| Transcript fragments arrive but no metrics             | `parameters.enable_metrics` not set.                                     |
| Import error on `from agora_agent.agentkit import ...` | SDK version mismatch; `pip install -r server/requirements.txt`.          |

## See Also

- [Back to Architecture](../02_architecture.md)
- [Back to Workflows](../05_workflows.md)
- [Session Lifecycle](session_lifecycle.md)
