from fastapi.testclient import TestClient

from repurposer import config
from repurposer.main import app

client = TestClient(app)


def test_config_reports_no_code_needed_by_default(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "")
    assert client.get("/config").json()["access_code_required"] is False


def test_wrong_code_is_rejected_before_any_claude_call(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "letmein")
    called = []
    monkeypatch.setattr("repurposer.main.call_claude", lambda *a: called.append(1) or "x")

    r = client.post("/repurpose", json={"script": "hi", "platform": "x"}, headers={"X-Access-Code": "nope"})

    assert r.status_code == 401
    assert called == []
    assert client.get("/config").json()["access_code_required"] is True


def test_right_code_gets_through(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "letmein")
    monkeypatch.setattr("repurposer.main.call_claude", lambda *a: "a post")

    r = client.post("/repurpose", json={"script": "hi", "platform": "x"}, headers={"X-Access-Code": "letmein"})

    assert r.status_code == 200
    assert r.json()["content"] == "a post"
