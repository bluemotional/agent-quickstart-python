"""FastAPI route tests via TestClient + FakeAgent (no Agora cloud)."""

import importlib.util
from pathlib import Path


def _load_fake_server_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_fake_server.py"
    spec = importlib.util.spec_from_file_location("run_fake_server", script_path)
    assert spec and spec.loader, "Expected scripts/run_fake_server.py to be importable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_fake_server_uses_explicit_fake_port(monkeypatch):
    fake_server = _load_fake_server_module()

    monkeypatch.setenv("FAKE_SERVER_PORT", "43123")
    assert fake_server._resolve_port() == 43123


def test_fake_server_falls_back_to_port(monkeypatch):
    fake_server = _load_fake_server_module()

    monkeypatch.delenv("FAKE_SERVER_PORT", raising=False)
    monkeypatch.setenv("PORT", "8001")
    assert fake_server._resolve_port() == 8001


def test_fake_server_defaults_to_8000(monkeypatch):
    fake_server = _load_fake_server_module()

    monkeypatch.delenv("FAKE_SERVER_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert fake_server._resolve_port() == 8000
