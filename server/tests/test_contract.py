"""task 5.1 契约测试：授权边界、字段完整性、向后兼容（新增字段不破坏 v1 消费方）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fd_zhesi_api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-tok-alice"}


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("FD_ZHESI_DB", str(tmp_path / "personal.db"))
    monkeypatch.setenv("FD_ZHESI_AUTH_DEV_TOKENS", "dev-tok-alice=alice")


def _seed_card():
    r = client.post("/api/v1/cards", json={
        "question": "free will", "position": "compatibilism",
        "reasons": "日常经验", "question_ref": "survey-2020:free will",
    }, headers=AUTH)
    assert r.status_code == 201
    return r.json()


def test_denied_without_grant() -> None:
    _seed_card()
    r = client.get("/api/v1/contract/cards", params={"consumer": "juchuang"}, headers=AUTH)
    assert r.status_code == 403  # 未授权：剧创取不到（spec 授权边界继承）


def test_grant_scoped_delivery() -> None:
    card = _seed_card()
    r = client.post("/api/v1/grants", json={"consumer": "juchuang", "card_kinds": ["stance"]},
                    headers=AUTH)
    assert r.status_code == 201

    r = client.get("/api/v1/contract/cards", params={"consumer": "juchuang"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["contract_version"] == "1"
    assert body["consumer"] == "juchuang"
    assert len(body["cards"]) == 1
    c = body["cards"][0]
    # 契约字段集完整性（v1）：剧创依赖的每个字段都在
    assert set(c) == {"id", "question", "question_ref", "position",
                      "stability", "strongest_objection", "as_of"}
    assert c["id"] == card["id"] and c["position"] == "compatibilism"
    # 张力未授权 → 不下发张力数据
    assert body["tensions"] == []

    # 开放 tension 后（空张力簿）字段仍在
    client.post("/api/v1/grants", json={"consumer": "juchuang", "card_kinds": ["stance", "tension"]},
                headers=AUTH)
    body2 = client.get("/api/v1/contract/cards", params={"consumer": "juchuang"},
                       headers=AUTH).json()
    assert "tensions" in body2 and body2["contract_version"] == "1"


def test_backward_compat_additive_only() -> None:
    """契约演进只增字段：模拟 v1 消费方按旧字段集取子集，不受新增字段影响。"""
    _seed_card()
    client.post("/api/v1/grants", json={"consumer": "juchuang", "card_kinds": ["stance"]},
                headers=AUTH)
    body = client.get("/api/v1/contract/cards", params={"consumer": "juchuang"}, headers=AUTH).json()
    v1_fields = {"id", "question", "question_ref", "position",
                 "stability", "strongest_objection", "as_of"}
    for c in body["cards"]:
        consumed = {k: c[k] for k in v1_fields}  # 旧消费方按已知字段取子集
        assert consumed["position"]
    assert set(body["cards"][0]) >= v1_fields  # 新字段只能是超集


def test_grant_validation() -> None:
    r = client.post("/api/v1/grants", json={"consumer": "juchuang", "card_kinds": ["secret"]},
                    headers=AUTH)
    assert r.status_code == 422
