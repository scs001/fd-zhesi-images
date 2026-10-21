"""task 4.3 / 4.4 验证：谱闭环（六轴投影+思想邻居，版本化历史）与张力簿。

全离线：个人层用临时 DB，参照系用手造 fixture（12 位哲学家的六轴行，
其中 1 位轴不全——诚实跳过）。真 376 人参照系的实跑演示另行为之（见
任务汇报），不入测试套件。
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from fd_zhesi_api.main import app
from fd_zhesi_api.synthesis import router as synthesis_router

# main.py 挂载行（接线期由主代理加入）：app.include_router(synthesis_router)
if not any(getattr(r, "path", "") == "/api/v1/synthesis/project" for r in app.routes):
    app.include_router(synthesis_router)

client = TestClient(app)
AUTH = {"Authorization": "Bearer tok-alice"}
AUTH_BOB = {"Authorization": "Bearer tok-bob"}
AUTH_CAROL = {"Authorization": "Bearer tok-carol"}
AUTH_DAVE = {"Authorization": "Bearer tok-dave"}


def _make_ref_db(path) -> str:
    """手造参照系 fixture：12 位哲学家六轴（1 位轴缺 → 不参与邻居）。"""
    from fd_zhesi_reference.schema import DDL

    conn = sqlite3.connect(path)
    for ddl in DDL:
        conn.executescript(ddl)
    # atlas_id, name_pt, name_en, name_zh, ind, mat, rat, det, tra, uni
    rows = [
        (1, "Plato", "Plato", "柏拉图", 3, 0, 10, 6, 10, 10),
        (2, "Aristotle", "Aristotle", "亚里士多德", 4, 6, 8, 7, 5, 8),
        (3, "Augustine", "Augustine", "奥古斯丁", 2, 1, 9, 7, 10, 9),
        (4, "Aquinas", "Aquinas", "阿奎那", 2, 4, 8, 7, 9, 8),
        (5, "Democritus", "Democritus", "德谟克利特", 5, 10, 7, 10, 0, 7),
        (6, "Hume", "Hume", "休谟", 7, 7, 4, 8, 1, 4),
        (7, "Kant", "Kant", "康德", 5, 3, 9, 6, 6, 10),
        (8, "Mill", "Mill", "密尔", 8, 6, 5, 6, 2, 8),
        (9, "Marx", "Marx", "马克思", 2, 10, 6, 9, 0, 9),
        (10, "Nietzsche", "Nietzsche", "尼采", 10, 5, 7, 9, 3, 1),
        (11, "Confucius", "Confucius", "孔子", 3, 5, 6, 5, 3, 7),
        (12, "Pyrrho", "Pyrrho", "皮浪", 6, 4, None, 4, 2, 3),  # 轴不全
    ]
    conn.executemany(
        "INSERT INTO philosophers (atlas_id, name_pt, name_en, name_zh,"
        " individualism, materialism, rationalism, determinism, transcendence,"
        " universalism, ingested_at) VALUES (?,?,?,?,?,?,?,?,?,?, '2026-01-01T00:00:00')",
        rows,
    )
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("FD_ZHESI_DB", str(tmp_path / "personal.db"))
    monkeypatch.setenv(
        "FD_ZHESI_AUTH_DEV_TOKENS",
        "tok-alice=alice,tok-bob=bob,tok-carol=carol,tok-dave=dave",
    )
    monkeypatch.setenv("FD_ZHESI_REF_DB", _make_ref_db(tmp_path / "reference.db"))


def _card(question: str, position: str, question_ref: str | None = None,
          headers: dict = AUTH) -> dict:
    r = client.post(
        "/api/v1/cards",
        json={"question": question, "position": position, "question_ref": question_ref},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


# 15 张可映射：有神论-理性主义-超越集群（邻居应落在 Plato/Augustine 一带）
MAPPED_15 = [
    ("God: theism or atheism?", "theism"),
    ("Free will: compatibilism, libertarianism, or no free will?", "libertarianism"),
    ("Meta-ethics: moral realism, moral anti-realism, or error theory?", "moral realism"),
    ("Abstract objects: Platonism or nominalism?", "Platonism"),
    ("A priori knowledge: yes or no?", "yes"),
    ("Knowledge: empiricism or rationalism?", "rationalism"),
    ("Mind: physicalism or non-physicalism?", "non-physicalism"),
    ("Personal identity: psychological view, biological view, or further-fact view?",
     "further-fact view"),
    ("Meaning of life: subjective, objective, or nonexistent?", "objective"),
    ("Metaphilosophy: naturalism or non-naturalism?", "non-naturalism"),
    ("Moral principles: moral generalism or moral particularism?", "moral generalism"),
    ("Normative ethics: deontology, consequentialism, or virtue ethics?", "deontology"),
    ("Aesthetic value: objective or subjective?", "objective"),
    ("Teletransporter (new matter): survival or death?", "survival"),
    ("Well-being: hedonism, desire satisfaction, or objective list?", "objective list"),
]

# 2 张诚实跳过：问题不在表 / 选项不在表
SKIPPED_2 = [
    ("Trolley problem (five straight ahead, one on side track, turn requires"
     " switching): switch or don't switch?", "switch"),                       # 问题未映射
    ("External world: idealism, skepticism, or non-skeptical realism?",
     "skepticism"),                                                            # 选项未映射
]


# ---- axis_map 单元 ----

def test_axis_map_resolve_variants() -> None:
    from fd_zhesi_api.axis_map import resolve

    # 照抄 survey 问题串（大小写/空白/尾问号差异都应命中）
    r = resolve("Free will: compatibilism, libertarianism, or no free will?",
                "compatibilism")
    assert r and r.deltas == {"determinism": 1.5}
    # 短别名
    assert resolve("Free will", "compatibilism").deltas == {"determinism": 1.5}
    # question_ref canonical 坐标兜底（自由文本问题映射不上时）
    r = resolve("自由意志是真是假？", "no free will",
                question_ref="survey-2020:free will")
    assert r and r.deltas == {"determinism": 2.0}
    # 映射不上：未知问题 / 已知问题的未收录选项
    assert resolve("Sleeping beauty: one-third or one-half?", "one-third") is None
    assert resolve("External world: idealism, skepticism, or non-skeptical realism?",
                   "skepticism") is None


def test_compute_axes_clamp_and_anchor() -> None:
    from fd_zhesi_api.synthesis import compute_axes

    axes = compute_axes([{"transcendence": 2.0}] * 8)   # +16 → 签名和 clamp 10 → 5+10 → 10
    assert axes["transcendence"] == 10.0
    axes = compute_axes([{"materialism": -2.0}] * 6)    # -12 → -10 → 5-10 → 0
    assert axes["materialism"] == 0.0
    axes = compute_axes([])                              # 无立场 → 中性锚点
    assert axes == {"individualism": 5.0, "materialism": 5.0, "rationalism": 5.0,
                    "determinism": 5.0, "transcendence": 5.0, "universalism": 5.0}


# ---- 4.3 谱闭环 ----

def test_projection_requires_auth() -> None:
    for method, path in (("post", "/api/v1/synthesis/project"),
                         ("get", "/api/v1/synthesis/projections")):
        r = getattr(client, method)(path)
        assert r.status_code == 401


def test_projection_15_mapped_cards() -> None:
    """15 张可映射卡 → 投影（8 邻居 + axes_version），映射不上的诚实列出。"""
    ids = [_card(q, p)["id"] for q, p in MAPPED_15]
    skipped_cards = [_card(q, p) for q, p in SKIPPED_2]

    r = client.post("/api/v1/synthesis/project", headers=AUTH)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["axes_version"] == "1"
    assert set(body["axes"]) == {"individualism", "materialism", "rationalism",
                                 "determinism", "transcendence", "universalism"}
    assert all(0.0 <= v <= 10.0 for v in body["axes"].values())
    # 有神论-超越集群：transcendence 顶格、materialism 触底
    assert body["axes"]["transcendence"] == 10.0
    assert body["axes"]["materialism"] == 0.0
    # 邻居：8 位、距离升序、含双语名；fixture 中轴不全的 Pyrrho 不参与
    assert len(body["neighbors"]) == 8
    assert all({"atlas_id", "name_en", "name_zh", "distance"} <= set(n)
               for n in body["neighbors"])
    dists = [n["distance"] for n in body["neighbors"]]
    assert dists == sorted(dists)
    assert all(n["name_en"] != "Pyrrho" for n in body["neighbors"])
    assert body["neighbors"][0]["name_en"] == "Plato"  # 该集群最近邻
    # 基于哪些卡：15 张可映射卡；映射不上的 2 张诚实列出
    assert sorted(body["based_on_cards"]) == sorted(ids)
    assert body["mappable_count"] == 15
    assert {(s["card_id"], s["reason"]) for s in body["skipped"]} == {
        (skipped_cards[0]["id"], "question_not_mapped"),
        (skipped_cards[1]["id"], "position_not_mapped"),
    }


def test_reprojection_keeps_history() -> None:
    """改 3 张卡重合成 → 两版本并存、最新在前、based_on_cards 可对比。"""
    cards = {q: _card(q, p)["id"] for q, p in MAPPED_15}
    v1 = client.post("/api/v1/synthesis/project", headers=AUTH).json()
    assert v1["axes"]["transcendence"] == 10.0

    # 变更 3 张：theism→atheism、a priori yes→no、rationalism→empiricism
    for q, new_pos in (("God: theism or atheism?", "atheism"),
                       ("A priori knowledge: yes or no?", "no"),
                       ("Knowledge: empiricism or rationalism?", "empiricism")):
        r = client.post(f"/api/v1/cards/{cards[q]}/change",
                        json={"position": new_pos}, headers=AUTH)
        assert r.status_code == 200, r.text

    v2 = client.post("/api/v1/synthesis/project", headers=AUTH).json()
    assert v2["id"] != v1["id"]
    # transcendence 在该集群本已顶格（clamp 10 不再升）；看明确移位的两轴：
    assert v2["axes"]["rationalism"] < v1["axes"]["rationalism"]    # 9.5 → 3.5
    assert v2["axes"]["materialism"] > v1["axes"]["materialism"]    # 0 → 1
    assert v2["axes"] != v1["axes"]

    r = client.get("/api/v1/synthesis/projections", headers=AUTH)
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 2                       # 历史保留（思想年轮）
    assert results[0]["id"] == v2["id"]            # 最新在前
    assert results[1]["id"] == v1["id"]
    old, new = set(v1["based_on_cards"]), set(v2["based_on_cards"])
    assert len(old & new) == 12                    # 12 张未变
    assert len(old - new) == 3 and len(new - old) == 3


def test_projection_below_threshold_412() -> None:
    """active 卡 <5 → 412；active ≥5 但可映射 <5 → 同样 412（带提示）。"""
    for q, p in MAPPED_15[:4]:
        _card(q, p, headers=AUTH_BOB)
    r = client.post("/api/v1/synthesis/project", headers=AUTH_BOB)
    assert r.status_code == 412
    assert "阈值" in r.json()["detail"]

    for _ in range(5):  # 5 张 active 但全映射不上（时间 A/B 理论不入表）
        _card("Time: A-theory or B-theory?", "A-theory", headers=AUTH_BOB)
    r = client.post("/api/v1/synthesis/project", headers=AUTH_BOB)
    assert r.status_code == 412
    assert "可映射" in r.json()["detail"]


def test_projection_reference_unavailable_503(tmp_path, monkeypatch) -> None:
    """参照系库空/不可用 → 明确 503（不静默产出无邻居投影）。"""
    monkeypatch.setenv("FD_ZHESI_REF_DB", str(tmp_path / "empty-ref.db"))
    for q, p in MAPPED_15:
        _card(q, p)
    r = client.post("/api/v1/synthesis/project", headers=AUTH)
    assert r.status_code == 503
    assert "参照系" in r.json()["detail"]


# ---- 4.4 张力簿 ----

# 3 组已知张力组合
TENSION_SETS = [
    [("God: theism or atheism?", "theism"),
     ("God: theism or atheism?", "atheism")],
    [("Mind: physicalism or non-physicalism?", "physicalism"),
     ("Zombies: inconceivable, conceivable but not metaphysically possible, or"
      " metaphysically possible?", "metaphysically possible")],
    [("Knowledge: empiricism or rationalism?", "empiricism"),
     ("A priori knowledge: yes or no?", "yes")],
]


def test_detect_tensions_three_known_hits() -> None:
    for pair in TENSION_SETS:
        for q, p in pair:
            _card(q, p, headers=AUTH_CAROL)

    r = client.post("/api/v1/synthesis/detect-tensions", headers=AUTH_CAROL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created"]) == 3                # 3 组已知张力全部命中
    assert body["open_count"] == 3
    assert all(t["source"].startswith("经典张力: ") for t in body["created"])
    assert all(len(t["card_ids"]) == 2 for t in body["created"])

    # GET 列表
    r = client.get("/api/v1/synthesis/tensions", headers=AUTH_CAROL)
    results = r.json()["results"]
    assert len(results) == 3
    assert all(x["status"] == "open" for x in results)

    # 重复检测不产生重复行
    r = client.post("/api/v1/synthesis/detect-tensions", headers=AUTH_CAROL)
    assert r.json()["created"] == []
    assert r.json()["open_count"] == 3
    from fd_zhesi_api import personal

    conn = personal.connect()
    rows = conn.execute("SELECT COUNT(*) FROM tensions").fetchone()[0]
    conn.close()
    assert rows == 3


def test_detect_tensions_zero_false_positives() -> None:
    """3 组无张力组合零误报（宁缺毋滥）。"""
    coherent_sets = [
        # 自然主义集群
        [("God: theism or atheism?", "atheism"),
         ("Mind: physicalism or non-physicalism?", "physicalism"),
         ("Free will: compatibilism, libertarianism, or no free will?", "compatibilism"),
         ("Science: scientific realism or scientific anti-realism?", "scientific realism"),
         ("Meta-ethics: moral realism or moral anti-realism?", "moral realism")],
        # 理性主义-普遍主义集群
        [("Political philosophy: communitarianism, egalitarianism, or libertarianism?",
          "libertarianism"),
         ("Normative ethics: deontology, consequentialism, or virtue ethics?", "deontology"),
         ("A priori knowledge: yes or no?", "yes"),
         ("Knowledge: empiricism or rationalism?", "rationalism"),
         ("Moral principles: moral generalism or moral particularism?", "moral generalism")],
        # 客观价值集群
        [("Morality: non-naturalism, naturalist realism, constructivism, expressivism,"
          " or error theory?", "naturalist realism"),
         ("Well-being: hedonism, desire satisfaction, or objective list?", "objective list"),
         ("Meaning of life: subjective, objective, or nonexistent?", "objective"),
         ("Aesthetic value: objective or subjective?", "objective"),
         ("Metaphilosophy: naturalism or non-naturalism?", "naturalism")],
    ]
    for s in coherent_sets:
        for q, p in s:
            _card(q, p, headers=AUTH_DAVE)

    r = client.post("/api/v1/synthesis/detect-tensions", headers=AUTH_DAVE)
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == []                    # 零误报
    assert body["checked_pairs"] > 0                # 确实做了两两扫描


def test_detect_tensions_requires_auth() -> None:
    r = client.post("/api/v1/synthesis/detect-tensions")
    assert r.status_code == 401
    r = client.get("/api/v1/synthesis/tensions")
    assert r.status_code == 401


def test_tensions_user_isolation() -> None:
    for pair in TENSION_SETS[:1]:
        for q, p in pair:
            _card(q, p, headers=AUTH_CAROL)
    client.post("/api/v1/synthesis/detect-tensions", headers=AUTH_CAROL)
    r = client.get("/api/v1/synthesis/tensions", headers=AUTH_DAVE)
    assert r.json()["results"] == []                # 张力簿按用户隔离
