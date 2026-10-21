"""骨架验证：healthz 与 version。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from fd_zhesi_api import __version__
from fd_zhesi_api.main import app

client = TestClient(app)


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "fd-zhesi-api"
    assert body["version"] == __version__


def test_version() -> None:
    resp = client.get("/api/version")
    assert resp.status_code == 200
    assert resp.json()["version"] == __version__
