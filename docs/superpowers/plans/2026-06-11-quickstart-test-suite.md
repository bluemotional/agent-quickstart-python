# agent-quickstart-python — Standalone Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone, multi-platform test suite to the quickstart — pytest for `server/`, `bun test` for `web/` — plus GitHub Actions CI across `{ubuntu, macos, windows} × Python {3.10, 3.13}`, and bump the documented Python floor 3.8 → 3.10.

**Architecture:** Characterization/regression tests for existing, working code (the single managed backend). The one cloud call (`AgoraAgent.create_async_session`) is monkeypatched; everything else runs for real (FastAPI `TestClient`, pure web functions). No `llm/` — this repo has none.

**Tech Stack:** pytest + httpx (`TestClient`); `bun test`; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-11-quickstart-test-suite-design.md`

**Repo & branch:** `agent-quickstart-python` (local folder `/Users/zhangqianze/Documents/agent-quickstart-python`), branch `test/add-suite` (already created off `main`).

**Verbatim source for the web tests:** `/Users/zhangqianze/Documents/agent-recipes-python/web/src/{services/api.test.ts,lib/conversation.test.ts}` — the `api.ts`/`conversation.ts` modules are byte-identical, so the tests copy directly.

---

## Conventions

- Conventional Commits, lowercase after prefix, present tense, NO AI attribution / NO `Co-Authored-By`, no `--no-verify`. If a commit fails on git identity, prefix with `git -c user.email="qianze.zhang@hotmail.com"`.
- **No venv exists yet.** Create one in Task 1 and reuse it.
- "Tests" are the `pytest`/`bun test` runs. These are written to **pass against existing code**; a failure is a real finding — surface it, don't weaken the test.

---

## Task 1: Server test scaffolding (venv + `requirements-dev.txt` + `conftest.py`)

**Files:**
- Create: `server/requirements-dev.txt`, `server/tests/__init__.py` (empty), `server/tests/conftest.py`

- [ ] **Step 1: Create `server/requirements-dev.txt`**

```
pytest>=7.4
httpx>=0.24
```

- [ ] **Step 2: Create empty `server/tests/__init__.py`** (0 bytes)

```python
```

- [ ] **Step 3: Create `server/tests/conftest.py`**

```python
"""Shared fixtures for the server test suite.

Standalone: no Agora cloud, no real credentials. A deterministic fake env is
injected, and python-dotenv is neutralized so a developer's real
`server/.env.local` cannot override the test env (server.py loads it with
override=True).
"""
import importlib
import os
import sys

import pytest

# Make `import server` / `import agent` resolve to server/src/*.
_SERVER_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SERVER_SRC not in sys.path:
    sys.path.insert(0, _SERVER_SRC)

FAKE_ENV = {
    "AGORA_APP_ID": "0123456789abcdef0123456789abcdef",
    "AGORA_APP_CERTIFICATE": "fedcba9876543210fedcba9876543210",
}


@pytest.fixture
def fake_env(monkeypatch):
    """Inject a deterministic env and stop dotenv from clobbering it."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    return dict(FAKE_ENV)


class FakeAgent:
    """Stand-in for the real Agent (mirrors scripts/run_fake_server.py)."""

    def __init__(self):
        self.started = []
        self.stopped = []

    async def start(self, channel_name, agent_uid, user_uid, output_audio_codec=None):
        self.started.append((channel_name, agent_uid, user_uid, output_audio_codec))
        return {
            "agent_id": f"fake-agent-{agent_uid}",
            "channel_name": channel_name,
            "status": "started",
        }

    async def stop(self, agent_id):
        self.stopped.append(agent_id)


@pytest.fixture
def server_module(fake_env):
    """Import server.py fresh, with the fake env + neutralized dotenv applied."""
    sys.modules.pop("server", None)
    sys.modules.pop("agent", None)
    import server

    importlib.reload(server)
    return server


@pytest.fixture
def client(server_module):
    """A FastAPI TestClient whose agent is a FakeAgent (no cloud)."""
    from fastapi.testclient import TestClient

    fake = FakeAgent()
    server_module.agent = fake
    test_client = TestClient(server_module.app)
    test_client.fake_agent = fake
    return test_client
```

- [ ] **Step 4: Create the venv and install deps**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python/server
python3 -m venv venv
venv/bin/python -m pip install -q --upgrade pip
venv/bin/python -m pip install -q -r requirements.txt -r requirements-dev.txt
```
Expected: installs cleanly (FastAPI, uvicorn, agora-agents, pytest, httpx). Needs PyPI access.

- [ ] **Step 5: Smoke the harness**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python/server
venv/bin/python -c "import sys; sys.path.insert(0,'src'); import os
os.environ.update({'AGORA_APP_ID':'0'*32,'AGORA_APP_CERTIFICATE':'f'*32})
import server; print('server imports; agent is', 'set' if server.agent else 'None')"
```
Expected: `server imports; agent is set`.

- [ ] **Step 6: Commit** (`venv/` is gitignored)

```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python
git add server/requirements-dev.txt server/tests/__init__.py server/tests/conftest.py
git commit -m "test(server): add pytest scaffolding (dev deps + conftest fixtures)"
```

---

## Task 2: Server route tests (`test_server.py`)

**Files:**
- Create: `server/tests/test_server.py`

- [ ] **Step 1: Write the tests**

```python
"""FastAPI route tests via TestClient + FakeAgent (no Agora cloud)."""


def test_get_config_returns_envelope_and_token(client):
    response = client.get("/get_config")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["msg"] == "success"
    data = body["data"]
    assert data["app_id"] == "0123456789abcdef0123456789abcdef"
    assert isinstance(data["token"], str) and len(data["token"]) > 0
    assert data["uid"] and data["uid"] != "0"
    assert data["channel_name"].startswith("ai-conversation-")
    assert data["agent_uid"]


def test_get_config_remaps_zero_uid_and_honors_channel(client):
    response = client.get("/get_config", params={"uid": 0, "channel": "test-channel"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["uid"] != "0"
    assert data["channel_name"] == "test-channel"


def test_start_agent_calls_agent_and_returns_shape(client):
    response = client.post(
        "/startAgent",
        json={"channelName": "ch", "rtcUid": 111, "userUid": 222},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == {
        "agent_id": "fake-agent-111",
        "channel_name": "ch",
        "status": "started",
    }
    assert client.fake_agent.started == [("ch", 111, 222, None)]


def test_start_agent_forwards_output_audio_codec(client):
    client.post(
        "/startAgent",
        json={
            "channelName": "ch",
            "rtcUid": 111,
            "userUid": 222,
            "parameters": {"output_audio_codec": "opus"},
        },
    )
    assert client.fake_agent.started[-1] == ("ch", 111, 222, "opus")


def test_stop_agent(client):
    response = client.post("/stopAgent", json={"agentId": "fake-agent-111"})
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert client.fake_agent.stopped == ["fake-agent-111"]


def test_value_error_maps_to_400(client, server_module):
    class BadAgent:
        async def start(self, **kwargs):
            raise ValueError("bad input")

        async def stop(self, *args):
            pass

    server_module.agent = BadAgent()
    response = client.post(
        "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
    )
    assert response.status_code == 400
    assert "bad input" in response.json()["detail"]


def test_runtime_error_maps_to_500(client, server_module):
    class BoomAgent:
        async def start(self, **kwargs):
            raise RuntimeError("explode")

        async def stop(self, *args):
            pass

    server_module.agent = BoomAgent()
    response = client.post(
        "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
    )
    assert response.status_code == 500


def test_misconfigured_agent_returns_500(client, server_module):
    server_module.agent = None
    assert client.get("/get_config").status_code == 500
    assert (
        client.post(
            "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
        ).status_code
        == 500
    )
    assert client.post("/stopAgent", json={"agentId": "x"}).status_code == 500
```

- [ ] **Step 2: Run**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python/server
venv/bin/python -m pytest tests/test_server.py -v
```
Expected: 8 passed. (If `test_get_config_*` fails on token generation with fake creds, report it — a real finding.)

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python
git add server/tests/test_server.py
git commit -m "test(server): cover get_config/startAgent/stopAgent routes and error mapping"
```

---

## Task 3: Agent wiring + validation tests (`test_agent.py`)

**Files:**
- Create: `server/tests/test_agent.py`

- [ ] **Step 1: Write the tests**

```python
"""Agent env validation + managed-OpenAI wiring (SDK session monkeypatched)."""
import asyncio
import sys

import pytest


def _fresh_agent_module():
    sys.modules.pop("agent", None)
    import agent

    return agent


@pytest.mark.parametrize("missing", ["AGORA_APP_ID", "AGORA_APP_CERTIFICATE"])
def test_agent_requires_env(fake_env, monkeypatch, missing):
    monkeypatch.delenv(missing, raising=False)
    agent = _fresh_agent_module()
    with pytest.raises(ValueError):
        agent.Agent()


def test_agent_constructs_with_full_env(fake_env):
    agent = _fresh_agent_module()
    instance = agent.Agent()
    assert instance.app_id == "0123456789abcdef0123456789abcdef"
    assert instance.client is not None


def test_start_wires_managed_openai_and_returns_shape(fake_env, monkeypatch):
    agent = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-agent-id"

        async def stop(self):
            captured["stopped"] = True

    def fake_create_async_session(self, **kwargs):
        captured["llm"] = self.llm
        captured["channel"] = kwargs.get("channel")
        captured["remote_uids"] = kwargs.get("remote_uids")
        return FakeSession()

    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", fake_create_async_session)

    instance = agent.Agent()
    result = asyncio.run(instance.start(channel_name="ch", agent_uid=111, user_uid=222))

    assert result == {
        "agent_id": "test-agent-id",
        "channel_name": "ch",
        "status": "started",
    }
    # The LLM stage is the managed OpenAI vendor (gpt-4o-mini), NOT CustomLLM.
    assert captured["llm"]["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["llm"]["params"]["model"] == "gpt-4o-mini"
    assert captured["llm"]["style"] == "openai"
    assert "vendor" not in captured["llm"]  # managed OpenAI has no custom vendor key
    assert captured["channel"] == "ch"
    assert captured["remote_uids"] == ["222"]


def test_start_validates_arguments(fake_env, monkeypatch):
    agent = _fresh_agent_module()
    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", lambda self, **k: None)
    instance = agent.Agent()
    with pytest.raises(ValueError):
        asyncio.run(instance.start(channel_name="", agent_uid=1, user_uid=2))
    with pytest.raises(ValueError):
        asyncio.run(instance.start(channel_name="c", agent_uid=0, user_uid=2))


def test_stop_uses_active_session_then_falls_back(fake_env, monkeypatch):
    agent = _fresh_agent_module()

    class FakeSession:
        def __init__(self):
            self.stopped = False

        async def start(self):
            return "agent-xyz"

        async def stop(self):
            self.stopped = True

    session = FakeSession()
    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", lambda self, **k: session)
    instance = agent.Agent()

    fallback_calls = []

    async def fake_stop_agent(agent_id):
        fallback_calls.append(agent_id)

    monkeypatch.setattr(instance.client, "stop_agent", fake_stop_agent)

    asyncio.run(instance.start(channel_name="ch", agent_uid=111, user_uid=222))
    asyncio.run(instance.stop("agent-xyz"))
    assert session.stopped is True
    assert fallback_calls == []

    asyncio.run(instance.stop("unknown-id"))
    assert fallback_calls == ["unknown-id"]
```

- [ ] **Step 2: Run the file, then the whole server suite**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python/server
venv/bin/python -m pytest tests/test_agent.py -v
venv/bin/python -m pytest tests -v
```
Expected: all pass. (`captured["llm"]` asserts the real managed `OpenAI.to_config()` shape — verified: `url`=`https://api.openai.com/v1/chat/completions`, `params.model`=`gpt-4o-mini`, `style`=`openai`, **no** `vendor` key.)

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python
git add server/tests/test_agent.py
git commit -m "test(server): cover Agent env validation, managed-OpenAI wiring, and stop fallback"
```

---

## Task 4: Web unit tests (copy verbatim)

**Files:**
- Create: `web/src/services/api.test.ts`, `web/src/lib/conversation.test.ts`

- [ ] **Step 1: Copy the two test files verbatim from the custom-llm repo**

Run:
```bash
cp /Users/zhangqianze/Documents/agent-recipes-python/web/src/services/api.test.ts \
   /Users/zhangqianze/Documents/agent-quickstart-python/web/src/services/api.test.ts
cp /Users/zhangqianze/Documents/agent-recipes-python/web/src/lib/conversation.test.ts \
   /Users/zhangqianze/Documents/agent-quickstart-python/web/src/lib/conversation.test.ts
```

- [ ] **Step 2: Confirm the modules under test are identical (so the tests apply unchanged)**

Run:
```bash
diff /Users/zhangqianze/Documents/agent-recipes-python/web/src/services/api.ts \
     /Users/zhangqianze/Documents/agent-quickstart-python/web/src/services/api.ts && echo "api.ts identical"
diff /Users/zhangqianze/Documents/agent-recipes-python/web/src/lib/conversation.ts \
     /Users/zhangqianze/Documents/agent-quickstart-python/web/src/lib/conversation.ts && echo "conversation.ts identical"
```
Expected: `api.ts identical` and `conversation.ts identical`.

- [ ] **Step 3: Run the web tests**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python/web
bun install
bun test
```
Expected: 6 tests pass. (`bun test` discovers only `*.test.ts`, so the existing `web/scripts/verify-*.ts` aren't run.)

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python
git add web/src/services/api.test.ts web/src/lib/conversation.test.ts
git commit -m "test(web): cover the api client and transcript normalization helpers"
```

---

## Task 5: GitHub Actions CI (`.github/workflows/ci.yml`)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  backend:
    name: backend (py${{ matrix.python-version }} / ${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.10", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: server tests
        working-directory: server
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
          pytest tests -v

  web:
    name: web (bun)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
      - run: bun test
        working-directory: web
```

- [ ] **Step 2: Structural validation**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python
grep -nE "^  (backend|web):|os: \[|python-version: \[|pytest tests|bun test" .github/workflows/ci.yml
grep -nP "\t" .github/workflows/ci.yml && echo "HAS TABS (bad)" || echo "no tabs"
```
Expected: both jobs, the matrix, `pytest tests`, `bun test`; `no tabs`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run pytest matrix (ubuntu/macos/windows x py3.10,3.13) and bun web tests"
```

---

## Task 6: Bump documented Python floor 3.8 → 3.10

**Files:**
- Modify: `README.md`, `server/README.md`, `docs/ai/L0_repo_card.md`, `docs/ai/L1/01_setup.md`

- [ ] **Step 1: `README.md` — badge + prerequisite**

Change line 4:
```
[![Python](https://img.shields.io/badge/python-%3E%3D3.8-blue)](https://www.python.org/)
```
to:
```
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
```
Change line 11:
```
- [Python 3.8+](https://www.python.org/)
```
to:
```
- [Python 3.10+](https://www.python.org/)
```

- [ ] **Step 2: `server/README.md:139`**

Change `- Python >= 3.8` to `- Python >= 3.10`.

- [ ] **Step 3: `docs/ai/L0_repo_card.md` — version + `Last Reviewed`**

Change line 11:
```
| Language      | Python 3.8+ (FastAPI + uvicorn) backend + Next.js 16 / React 19 web  |
```
to:
```
| Language      | Python 3.10+ (FastAPI + uvicorn) backend + Next.js 16 / React 19 web  |
```
Change the `Last Reviewed` row from `2026-05-28` to `2026-06-11`.

- [ ] **Step 4: `docs/ai/L1/01_setup.md` — two mentions**

Change `- **Python** ≥ 3.8 (README + \`server/README.md\`).` to `- **Python** ≥ 3.10 (README + \`server/README.md\`).`
Change `install Python ≥ 3.8.` to `install Python ≥ 3.10.`

- [ ] **Step 5: Add a tests note to `README.md`**

Find the `## Commands` section's closing fenced block and add this paragraph right after it:
```markdown

Tests run standalone (no Agora cloud needed): `pytest` in `server/`, `bun test` in `web/`. CI runs them on Linux/macOS/Windows × Python 3.10 & 3.13.
```

- [ ] **Step 6: Confirm no `3.8` remains and commit**

Run:
```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python
grep -rn "3\.8" README.md server/README.md docs/ai/L0_repo_card.md docs/ai/L1/01_setup.md && echo "STILL HAS 3.8 (fix it)" || echo "(no 3.8 left — good)"
git add README.md server/README.md docs/ai/L0_repo_card.md docs/ai/L1/01_setup.md
git commit -m "docs: raise Python floor to 3.10, note the test suite, bump L0 Last Reviewed"
```

---

## Task 7: Full local run + regression check

**Files:** none (runs everything).

- [ ] **Step 1: Run the server suite**

Run: `cd /Users/zhangqianze/Documents/agent-quickstart-python/server && venv/bin/python -m pytest tests -v`
Expected: all pass.

- [ ] **Step 2: Run the web tests**

Run: `cd /Users/zhangqianze/Documents/agent-quickstart-python/web && bun test`
Expected: all pass.

- [ ] **Step 3: No-regression on the existing verify gate**

Run: `cd /Users/zhangqianze/Documents/agent-quickstart-python && python3 -m py_compile server/src/server.py server/src/agent.py && echo "backend compile OK"`
Expected: `backend compile OK` (the new test files don't affect the app modules).

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test: pass full local suite" || echo "nothing to commit"
```

---

## Task 8: Push + open PR

**Files:** none (git only).

- [ ] **Step 1: Push**

```bash
cd /Users/zhangqianze/Documents/agent-quickstart-python
git push -u origin test/add-suite
```

- [ ] **Step 2: Open the PR** (REST — the GraphQL `gh pr create` path 401s under the lapsed SSO session)

```bash
REPO=AgoraIO-Conversational-AI/agent-quickstart-python
gh api -X POST "repos/$REPO/pulls" \
  -f title="test: add standalone multi-platform test suite + CI" \
  -f head="test/add-suite" -f base="main" \
  -f body="Ports the recipe test suite to the quickstart: pytest for server/ (FastAPI routes + Agent wiring, cloud mocked) and bun tests for web/ (api client + transcript helpers), plus GitHub Actions CI across {ubuntu,macos,windows} x Python {3.10,3.13}. Standalone: no Agora cloud, ngrok, or creds. Also raises the documented Python floor 3.8 -> 3.10 (6 mentions across README/server-README/docs-ai) and bumps L0 Last Reviewed. Verified locally: pytest + bun test all pass. (Sub-project 1 of 3; Docker image + nightly follow.)" \
  --jq '{number, url: .html_url, state}'
```
Expected: a JSON object with the new PR number + URL.

---

## Self-Review notes (for the implementer)

- **Tests must pass against existing code.** A failure is a real finding (e.g. token generation with fake creds). Unlike custom-llm, this repo's `Agent` has no custom-key default, so the dead-guard bug we fixed there is **not** expected here.
- **The mock seam** is `agora_agent.agentkit.Agent.create_async_session`; the captured `self.llm` is the real managed `OpenAI.to_config()` (`url`/`params.model`/`style`, no `vendor`).
- **dotenv neutralization** in `conftest.py` is load-bearing — without it a real `server/.env.local` (loaded `override=True`) would clobber the deterministic test env.
- **Doc bump scope (decision A):** only the 6 version mentions + L0 `Last Reviewed` + the README tests note. Do **not** rewrite `docs/ai/L1/05_workflows.md`/`01_setup.md` prose to add test/CI sections.
- **Portability:** this is sub-project 1 of 3; the Docker image and nightly reuse this repo's `ci.yml` (and a `docker.yml`), so this cycle deliberately does NOT add `workflow_call`.
