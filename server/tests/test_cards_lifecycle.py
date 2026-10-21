"""task 3.2/3.3 验证：立场卡全生命周期 + 访问控制（401 与审计留痕）。

用 dev-token 模式（FD_ZHESI_AUTH_DEV_TOKENS）做 API 级测试；
另附一个 JWKS JWT 直测（本地生成 RSA 密钥 + 本地 JWKS 文件服务）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fd_zhesi_api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-tok-alice"}
AUTH_BOB = {"Authorization": "Bearer dev-tok-bob"}


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("FD_ZHESI_DB", str(tmp_path / "personal.db"))
    monkeypatch.setenv(
        "FD_ZHESI_AUTH_DEV_TOKENS", "dev-tok-alice=alice,dev-tok-bob=bob"
    )


def _create(question="free will", position="compatibilism", reasons="日常经验") -> dict:
    r = client.post(
        "/api/v1/cards",
        json={"question": question, "position": position, "reasons": reasons,
              "question_ref": "survey-2020:free will"},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_unauthorized_denied_and_audited() -> None:
    """无 token / 错 token → 401，且审计表留痕（task 3.3 验证线）。"""
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic x"}):
        r = client.get("/api/v1/cards", headers=headers)
        assert r.status_code == 401
    from fd_zhesi_api import personal

    conn = personal.connect()
    rows = conn.execute(
        "SELECT user_id, action, outcome, detail FROM audit_log WHERE outcome='denied'"
    ).fetchall()
    conn.close()
    assert len(rows) >= 3
    assert all(r["user_id"] is None for r in rows)


def test_full_lifecycle() -> None:
    """表态建卡 → 反驳入卡 → 回应+现状更新 → 变更封存入年轮 → 回溯。"""
    card = _create()
    assert card["status"] == "active" and card["stability"] == "stable"
    cid = card["id"]

    # 最强反驳（4.2 的调用面）
    r = client.post(f"/api/v1/cards/{cid}/objection",
                    json={"objection": "Consequence argument: 若决定论为真，'能够另作选择'何解？"},
                    headers=AUTH)
    assert r.status_code == 200 and "Consequence" in r.json()["strongest_objection"]

    # 回应 + 现状转动摇
    r = client.post(f"/api/v1/cards/{cid}/response",
                    json={"my_response": "以来源条件解读'能够'", "stability": "wavering"},
                    headers=AUTH)
    assert r.status_code == 200
    assert r.json()["my_response"] and r.json()["stability"] == "wavering"

    # 立场变更：旧卡封存进年轮，新卡开卡
    r = client.post(f"/api/v1/cards/{cid}/change",
                    json={"position": "libertarianism", "reasons": "无法接受涌现被决定"},
                    headers=AUTH)
    assert r.status_code == 200
    new_card = r.json()
    assert new_card["id"] != cid and new_card["position"] == "libertarianism"

    # 旧卡 sealed；年轮有完整快照（含当时的反驳与回应）
    r = client.get(f"/api/v1/cards/{cid}", headers=AUTH)
    assert r.json()["status"] == "sealed" and r.json()["sealed_at"]
    annals = client.get("/api/v1/cards/annals", headers=AUTH).json()["results"]
    assert len(annals) == 1 and annals[0]["kind"] == "superseded"
    snap = annals[0]["snapshot"]
    assert snap["id"] == cid and snap["my_response"] and snap["strongest_objection"]

    # 旧卡的追问操作被拒（已封存）
    r = client.post(f"/api/v1/cards/{cid}/response", json={"my_response": "x"}, headers=AUTH)
    assert r.status_code == 404


def test_user_isolation() -> None:
    """双账号隔离：bob 看不到 alice 的卡。"""
    _create()
    r = client.get("/api/v1/cards", headers=AUTH_BOB)
    assert r.status_code == 200 and r.json()["results"] == []
    alice = client.get("/api/v1/cards", headers=AUTH).json()["results"]
    assert len(alice) == 1


def test_jwks_jwt_path(tmp_path, monkeypatch) -> None:
    """JWKS 路径（6.3 Logto 的形态）：本地 RSA 签发 token 能过、篡改被拒。"""
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk["kid"] = "k1"
    jwk["alg"] = "RS256"
    jwks_file = tmp_path / "jwks.json"
    jwks_file.write_text(json.dumps({"keys": [jwk]}))

    # PyJWKClient 只认 http/https：本地起临时 HTTP 服务喂 JWKS
    import http.server
    import socketserver
    import threading

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # 静音
            pass

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("FD_ZHESI_AUTH_JWKS", f"http://127.0.0.1:{port}/{jwks_file.name}")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("FD_ZHESI_AUTH_DEV_TOKENS", raising=False)

        def make(claims):
            return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})

        tok = make({"sub": "carol", "exp": 4102444800})
        r = client.get("/api/v1/cards", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200

        bad = make({"sub": "mallory", "exp": 4102444800})[:-3] + "xyz"
        r = client.get("/api/v1/cards", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401

        expired = make({"sub": "carol", "exp": 1000000000})
        r = client.get("/api/v1/cards", headers={"Authorization": f"Bearer {expired}"})
        assert r.status_code == 401
    finally:
        srv.shutdown()


def test_jwks_es384_path(tmp_path, monkeypatch) -> None:
    """Logto 1.42 实签算法 ES384 必须放行（线上 aloadtree ID token 实测踩坑）。"""
    import http.server
    import json
    import socketserver
    import threading

    import jwt
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP384R1())
    jwk = jwt.algorithms.ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid="ec1", alg="ES384")
    jwks_file = tmp_path / "jwks.json"
    jwks_file.write_text(json.dumps({"keys": [jwk]}))

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("FD_ZHESI_AUTH_JWKS", f"http://127.0.0.1:{port}/{jwks_file.name}")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("FD_ZHESI_AUTH_DEV_TOKENS", raising=False)
        tok = jwt.encode({"sub": "ec-user", "exp": 4102444800}, key, algorithm="ES384", headers={"kid": "ec1"})
        r = client.get("/api/v1/cards", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
    finally:
        srv.shutdown()
