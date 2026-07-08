"""Unit tests for the fake server harness used in local smoke checks."""

import importlib.util
from pathlib import Path


def _load_fake_server_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_fake_server.py"
    spec = importlib.util.spec_from_file_location("run_fake_server", script_path)
    assert spec and spec.loader, "Expected scripts/run_fake_server.py to be importable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_port_prefers_fake_server_port(monkeypatch):
    fake_server = _load_fake_server_module()

    monkeypatch.setenv("FAKE_SERVER_PORT", "43210")
    monkeypatch.setenv("PORT", "8000")
    assert fake_server._resolve_port() == 43210


def test_resolve_port_falls_back_to_port(monkeypatch):
    fake_server = _load_fake_server_module()

    monkeypatch.delenv("FAKE_SERVER_PORT", raising=False)
    monkeypatch.setenv("PORT", "8001")
    assert fake_server._resolve_port() == 8001


def test_resolve_port_defaults_to_8000(monkeypatch):
    fake_server = _load_fake_server_module()

    monkeypatch.delenv("FAKE_SERVER_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert fake_server._resolve_port() == 8000
