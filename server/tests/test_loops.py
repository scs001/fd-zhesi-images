"""task 4.1/4.2 验证：问闭环（确定性映射 + LLM 归一合并）与辩闭环（最强反驳 + 引用锚定）。

全离线：参照系用手造小样本 fixture 库（与 fd-zhesi-reference 同 schema 子集），
LLM 全部 monkeypatch 不真调网。30 条生活语言样本的命中率与「无凭空定义」
验收在 test_mapping_accuracy_30 / test_ask_anchoring_no_fabrication。
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fd_zhesi_api import cards, llm as llm_mod, loops, personal
from fd_zhesi_api.loops import QUESTION_DOMAINS

app = FastAPI()
app.include_router(cards.router)
app.include_router(loops.router)
client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-tok-alice"}

# ---------------------------------------------------------------------------
# 参照系 fixture（手造小样本；真实库在 ~/.fd-zhesi/reference.db，绝不写）
# ---------------------------------------------------------------------------

FW_Q = "Free will: compatibilism, libertarianism, or no free will?"
GOD_Q = "God: theism or atheism?"
ZOMBIE_Q = ("Zombies: inconceivable, conceivable but not metaphysically possible,"
            " or metaphysically possible?")
MIND_Q = "Mind: physicalism or non-physicalism?"
METAETH_Q = "Meta-ethics: moral realism or moral anti-realism?"
KNOW_Q = "Knowledge: empiricism or rationalism?"
TROLLEY_Q = ("Trolley problem (five straight ahead, one on side track, turn requires"
             " switching, what ought one do?): switch or don't switch?")

_FIXTURE_STANCES = [
    ("2020", FW_Q, "compatibilism", "相容论（自由意志与决定论可以并存）", 59.2),
    ("2020", FW_Q, "libertarianism", "自由意志论（人有非决定论的自由）", 18.8),
    ("2020", FW_Q, "no free will", "无自由意志（决定论成立）", 11.2),
    ("2009", FW_Q, "compatibilism", "相容论（自由意志与决定论可以并存）", 59.1),
    ("2009", FW_Q, "libertarianism", "自由意志论（人有非决定论的自由）", 14.0),
    ("2020", GOD_Q, "theism", "有神论（神存在）", 67.1),
    ("2020", GOD_Q, "atheism", "无神论（神不存在）", 16.8),
    ("2020", ZOMBIE_Q, "inconceivable", "不可设想", 35.6),
    ("2020", ZOMBIE_Q, "conceivable but not metaphysically possible", "可设想但形而上不可能", 37.7),
    ("2020", ZOMBIE_Q, "metaphysically possible", "形而上可能", 16.4),
    ("2020", MIND_Q, "physicalism", "物理主义（心灵完全是物理的）", 52.0),
    ("2020", MIND_Q, "non-physicalism", "非物理主义", 31.0),
    ("2020", METAETH_Q, "moral realism", "道德实在论（道德事实客观存在）", 62.1),
    ("2020", METAETH_Q, "moral anti-realism", "道德反实在论", 26.0),
    ("2020", KNOW_Q, "empiricism", "经验论（知识源于经验）", 40.0),
    ("2020", KNOW_Q, "rationalism", "唯理论（理性是知识之源）", 35.0),
    ("2020", TROLLEY_Q, "switch", "扳道岔（救五舍一）", 63.0),
    ("2020", TROLLEY_Q, "don't switch", "不扳（不干预）", 25.0),
]

_FIXTURE_CONCEPTS = [
    ("free will", "Free Will", "https://plato.stanford.edu/entries/freewill/", "freewill snippet"),
    ("compatibilism", "Compatibilism", "https://plato.stanford.edu/entries/compatibilism/", "compat snippet"),
    ("determinism", "Causal Determinism", "https://plato.stanford.edu/entries/determinism-causal/", "det snippet"),
    ("qualia", "Qualia", "https://plato.stanford.edu/entries/qualia/", "qualia snippet"),
    ("dualism", "Dualism", "https://plato.stanford.edu/entries/dualism/", "dualism snippet"),
    ("realism", "Realism", "https://plato.stanford.edu/entries/realism/", "realism snippet"),
    ("empiricism", "Empiricism", "https://plato.stanford.edu/entries/rationalism-empiricism/", "emp snippet"),
    ("epistemology", "Epistemology", "https://plato.stanford.edu/entries/epistemology/", "epi snippet"),
    ("Kant", "Kant", "https://plato.stanford.edu/entries/kant/", "kant snippet"),
    ("utilitarianism", "The History of Utilitarianism", "https://plato.stanford.edu/entries/utilitarianism-history/", "util snippet"),
]

# term/url 全集，用于「无凭空定义」校验
_KNOWN_CONCEPTS = {(t, u) for t, _, u, _ in _FIXTURE_CONCEPTS}


def _make_ref_db(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE concepts (
            term TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
            snippet TEXT, retrieved_at TEXT NOT NULL, PRIMARY KEY (term, url));
        CREATE TABLE stances (
            survey_round TEXT NOT NULL, question TEXT NOT NULL, question_zh TEXT,
            option TEXT NOT NULL, option_zh TEXT, pct REAL, retrieved_at TEXT NOT NULL,
            category TEXT, multi_select INTEGER, tabulation TEXT, respondents INTEGER,
            PRIMARY KEY (survey_round, question, option));
        CREATE TABLE philosophers (
            atlas_id INTEGER PRIMARY KEY, name_pt TEXT NOT NULL, name_en TEXT,
            name_zh TEXT, birth_year INTEGER, death_year INTEGER, school TEXT,
            school_en TEXT, school_zh TEXT, region TEXT, region_en TEXT, region_zh TEXT,
            individualism REAL, materialism REAL, rationalism REAL, determinism REAL,
            transcendence REAL, universalism REAL, influence_score REAL,
            wikidata_qid TEXT, ingested_at TEXT NOT NULL);
        CREATE TABLE relations (
            atlas_id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL, weight REAL NOT NULL, polarity TEXT NOT NULL,
            ingested_at TEXT NOT NULL);
        """
    )
    for rd, q, opt, opt_zh, pct in _FIXTURE_STANCES:
        conn.execute(
            "INSERT INTO stances (survey_round, question, option, option_zh, pct,"
            " retrieved_at, respondents) VALUES (?,?,?,?,?,?,?)",
            (rd, q, opt, opt_zh, pct, "2026-01-01", 1785 if rd == "2020" else 931),
        )
    for t, title, url, snip in _FIXTURE_CONCEPTS:
        conn.execute(
            "INSERT INTO concepts (term, title, url, snippet, retrieved_at) VALUES (?,?,?,?,?)",
            (t, title, url, snip, "2026-01-01"),
        )
    conn.execute(
        "INSERT INTO philosophers (atlas_id, name_pt, name_en, name_zh, ingested_at)"
        " VALUES (?,?,?,?,?)", (33, "Kant", "Immanuel Kant", "伊曼努爾·康德", "2026-01-01"))
    conn.execute(
        "INSERT INTO philosophers (atlas_id, name_pt, name_en, name_zh, ingested_at)"
        " VALUES (?,?,?,?,?)", (11, "Hume", "David Hume", "大衛·休謨", "2026-01-01"))
    conn.execute(
        "INSERT INTO relations (source_id, target_id, weight, polarity, ingested_at)"
        " VALUES (?,?,?,?,?)", (11, 33, 0.9, "critical", "2026-01-01"))
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    ref = tmp_path / "reference.db"
    _make_ref_db(ref)
    monkeypatch.setenv("FD_ZHESI_REF_DB", str(ref))
    monkeypatch.setenv("FD_ZHESI_DB", str(tmp_path / "personal.db"))
    monkeypatch.setenv("FD_ZHESI_AUTH_DEV_TOKENS", "dev-tok-alice=alice")
    monkeypatch.delenv("FD_ZHESI_LLM_API_KEY", raising=False)


def _ask(text: str) -> dict:
    r = client.post("/api/v1/ask", json={"text": text}, headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def _create_card(question="free will", position="compatibilism",
                 question_ref="survey-2020:free will") -> str:
    r = client.post("/api/v1/cards", json={
        "question": question, "position": position, "reasons": "日常经验",
        "question_ref": question_ref,
    }, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _debate(card_id: str):
    return client.post("/api/v1/debate/strongest-objection",
                       json={"card_id": card_id}, headers=AUTH)


# ---------------------------------------------------------------------------
# 30 条生活语言样本（中文口语 20 + 英文 10）——task 4.1 验收集
# ---------------------------------------------------------------------------

SAMPLES: list[tuple[str, str]] = [
    # ---- 中文口语 20 条 ----
    ("人到底有没有自由意志，还是一切都早被决定了？", "free-will"),
    ("我的命运是不是出生的时候就已经定好了？", "free-will"),
    ("善恶对错是客观的，还是只是文化习惯？", "moral-realism"),
    ("如果上帝不存在，道德还有根基吗？", "god"),
    ("人的意识只是大脑里的电信号吗，还是真的有个灵魂？", "physicalism"),
    ("意识为什么这么难解释？机器会有主观体验吗？", "hard-problem"),
    ("有没有可能存在一个和你一模一样、却没有任何内心体验的人？", "zombies"),
    ("电车失控了，拉杆牺牲一个人救五个人，该拉吗？", "trolley-switch"),
    ("把胖子推下天桥去救五个人，这样做可以吗？", "footbridge"),
    ("判断一件事该不该做，看动机还是看结果？", "normative-ethics"),
    ("我身体的细胞几十年全换了一遍，我还是原来的我吗？", "personal-identity"),
    ("如果传送器复制出一个新肉体并销毁旧的，那个人还活着吗？", "teletransporter"),
    ("知识主要来自经验观察，还是靠理性先天推出来？", "knowledge-empiricism"),
    ("我们能证明外部世界存在吗，还是一切都可能是幻觉？", "external-world"),
    ("说一句话为「真」，是因为它与事实符合吗？", "truth"),
    ("科学理论里说的电子、夸克真的存在吗？", "science-realism"),
    ("有没有完全不依赖经验的知识，比如数学真理？", "a-priori"),
    ("计算机通过了图灵测试，它是真的理解中文吗？", "chinese-room"),
    ("人生的意义是主观感受，还是有客观答案？", "meaning-of-life"),
    ("怀孕早期没有任何特殊情况，堕胎在道德上允许吗？", "abortion"),
    # ---- 英文 10 条 ----
    ("Do we have free will, or is everything determined?", "free-will"),
    ("Is morality objective, or just a matter of cultural convention?", "moral-realism"),
    ("Does God exist, or is religious belief a delusion?", "god"),
    ("Is the mind just the brain, or do we have immaterial souls?", "physicalism"),
    ("Why does consciousness feel like anything at all? The hard problem, really.", "hard-problem"),
    ("Are philosophical zombies conceivable — beings physically identical to us but with no inner life?", "zombies"),
    ("In the trolley case, should you flip the switch to save five at the cost of one?", "trolley-switch"),
    ("Is all knowledge derived from experience, or are some truths known a priori?", "knowledge-empiricism"),
    ("Would you plug into Nozick's experience machine for a life of guaranteed bliss?", "experience-machine"),
    ("What makes a life go well — pleasure, getting what you want, or something else?", "well-being"),
]


def test_mapping_accuracy_30() -> None:
    """确定性映射层：30 条样本，top-1 命中 ≥80%（≥24/30），召回（在命中集内）≥90%。"""
    top1 = inset = 0
    misses: list[str] = []
    for text, expected in SAMPLES:
        keys = [d["key"] for d in loops.map_domains(text)]
        if keys and keys[0] == expected:
            top1 += 1
        if expected in keys:
            inset += 1
        else:
            misses.append(f"{expected} <- {text} (got {keys})")
    assert top1 >= 24, f"top-1 命中 {top1}/30 < 80%；未命中: {misses}"
    assert inset >= 27, f"召回 {inset}/30 过低；未命中: {misses}"


def test_ask_deterministic_chinese() -> None:
    out = _ask("人到底有没有自由意志，还是一切都早被决定了？")
    assert out["engine"] == "deterministic"
    assert out["reason"] is None
    assert out["domains"] and out["domains"][0] == "free-will"
    sq = out["stance_questions"][0]
    assert sq["question"] == FW_Q and sq["survey_round"] == "2020"
    assert sq["question_ref"] == f"survey-2020:{FW_Q}"
    assert sq["provenance"]["source"] == "philpapers-survey"
    opts = {o["option"]: o for o in sq["options"]}
    assert opts["compatibilism"]["label_zh"].startswith("相容论")
    assert opts["compatibilism"]["pct"] == pytest.approx(59.2)
    # 概念卡锚定 concepts 表（fixture 里的 SEP 行），provenance=sep
    assert out["concept_cards"], "free-will 域在 fixture 有概念词条，不该为空"
    for c in out["concept_cards"]:
        assert (c["term"], c["url"]) in _KNOWN_CONCEPTS
        assert c["provenance"]["source"] == "sep" and c["provenance"]["url"] == c["url"]


def test_ask_english() -> None:
    out = _ask("Do we have free will, or is everything determined?")
    assert out["domains"][0] == "free-will"
    assert any(q["question"] == FW_Q for q in out["stance_questions"])


def test_ask_no_match_not_silent() -> None:
    out = _ask("今天午饭吃什么好呢")
    assert out["domains"] == [] and out["concept_cards"] == [] and out["stance_questions"] == []
    assert out["reason"] == "no_match"


def test_ask_anchoring_no_fabrication() -> None:
    """全部 30 条样本：concept_cards 只能来自 concepts 表行、立场问题只能来自
    stances 表行——无凭空定义（task 4.1 验收）。"""
    known_questions = {q for _, q, *_ in _FIXTURE_STANCES}
    for text, _ in SAMPLES:
        out = _ask(text)
        for c in out["concept_cards"]:
            assert (c["term"], c["url"]) in _KNOWN_CONCEPTS, f"凭空概念卡: {c} ({text})"
        for sq in out["stance_questions"]:
            assert sq["question"] in known_questions, f"凭空立场问题: {sq} ({text})"
            assert sq["provenance"]["source"] == "philpapers-survey"


def test_ask_unauthorized() -> None:
    r = client.post("/api/v1/ask", json={"text": "自由意志"})
    assert r.status_code == 401


def test_ask_llm_merge(monkeypatch) -> None:
    """LLM 归一层：严格从清单选、与确定性层合并去重；LLM 失败 → 纯确定性。"""
    monkeypatch.setenv("FD_ZHESI_LLM_API_KEY", "dummy")
    god_idx = [d["question"] for d in QUESTION_DOMAINS].index(GOD_Q) + 1

    def fake_chat(messages, **kwargs):
        return f'{{"indices": [{god_idx}]}}'

    monkeypatch.setattr(llm_mod, "chat", fake_chat)
    out = _ask("人到底有没有自由意志，还是一切都早被决定了？")
    assert out["engine"] == "llm"
    assert "free-will" in out["domains"] and "god" in out["domains"]  # 合并去重
    assert len(out["domains"]) == len(set(out["domains"]))
    assert {q["question"] for q in out["stance_questions"]} == {FW_Q, GOD_Q}

    # LLM 抛异常 → 降级确定性
    def boom(messages, **kwargs):
        raise llm_mod.LLMError("gateway down")

    monkeypatch.setattr(llm_mod, "chat", boom)
    out = _ask("人到底有没有自由意志，还是一切都早被决定了？")
    assert out["engine"] == "deterministic" and out["domains"] == ["free-will"]

    # LLM 返回非 JSON → 降级确定性
    monkeypatch.setattr(llm_mod, "chat", lambda m, **k: "我不会输出 JSON")
    out = _ask("人到底有没有自由意志？")
    assert out["engine"] == "deterministic"


def test_debate_deterministic_free_will() -> None:
    cid = _create_card()
    r = _debate(cid)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["engine"] == "deterministic"
    assert out["question"] == FW_Q and out["survey_round"] == "2020"
    # 对立选项按 pct 降序，top=libertarianism（18.8%）
    assert out["opposing_options"][0]["option"] == "libertarianism"
    assert "%" in out["objection"] and "libertarianism" in out["objection"]
    assert "自由意志论" in out["objection"]  # 通俗释义入文
    # 引用全部在候选集内（survey 对立选项 + SEP），可解析
    ids = [c["id"] for c in out["citations"]]
    assert f"survey-2020:{FW_Q}:libertarianism" in ids
    assert any(i.startswith("sep:") for i in ids)
    for c in out["citations"]:
        if c["source"] == "philpapers-survey":
            opt = c["id"].rsplit(":", 1)[1]
            assert opt in {"libertarianism", "no free will"}
        elif c["source"] == "sep":
            assert c["id"] == "sep:" + c["url"] and c["url"].startswith("https://plato.stanford.edu/")
    # 卡上 strongest_objection 已更新
    got = client.get(f"/api/v1/cards/{cid}", headers=AUTH).json()
    assert got["strongest_objection"] == out["objection"]


def test_debate_atlas_critical_citation() -> None:
    """概念词条对得上哲学家时，relations 的 critical 边入候选（Kant 域）。"""
    cid = _create_card(question="knowledge", position="empiricism",
                       question_ref="survey-2020:knowledge")
    r = _debate(cid)
    assert r.status_code == 200
    out = r.json()
    ids = [c["id"] for c in out["citations"]]
    # 确定性模板只引 survey+sep，但候选集（opposing_options/citations 之外）含 atlas 边：
    # 直接验证内部组装也召回（对得上才要）
    rc = loops._ref_conn()
    try:
        cands = loops._citation_candidates(
            rc, {"survey_round": "2020", "question": KNOW_Q},
            loops._opposing_options(
                {"survey_round": "2020", "question": KNOW_Q,
                 "rows": loops._stance_rows_for_question(rc, "2020", KNOW_Q)}, "empiricism"),
            loops._terms_for_question(KNOW_Q),
        )
    finally:
        rc.close()
    assert any(c["id"] == "atlas-critical:11-33" for c in cands)
    assert all(i in {c['id'] for c in cands} for i in ids)


def test_debate_llm_citation_validation(monkeypatch) -> None:
    """引用校验铁律：LLM 引用的 cite 不在候选集 → 剥除；全部非法 → 降级模板。"""
    monkeypatch.setenv("FD_ZHESI_LLM_API_KEY", "dummy")
    cid = _create_card()
    valid_id = f"survey-2020:{FW_Q}:libertarianism"

    def fake_chat(messages, **kwargs):
        return (
            '{"objection": "多数传统的相容论者主张：即便决定论为真，'
            '「能够另作选择」仍可解读为来源条件意义上的自由，因此你的立场必须回应'
            '后果论证。", "citations": ["%s", "sep:https://example.com/fake-entry"]}'
            % valid_id
        )

    monkeypatch.setattr(llm_mod, "chat", fake_chat)
    out = _debate(cid).json()
    assert out["engine"] == "llm"
    ids = [c["id"] for c in out["citations"]]
    assert valid_id in ids
    assert "sep:https://example.com/fake-entry" not in ids  # 非法引用剥除
    assert all(c["source"] in ("philpapers-survey", "sep") for c in out["citations"])

    # LLM 零有效引用 → 无引用锚的论证不出现在输出 → 降级确定性模板
    def fake_chat_no_cite(messages, **kwargs):
        return '{"objection": "一段没有任何合法引用的反驳", "citations": ["made-up:1"]}'

    monkeypatch.setattr(llm_mod, "chat", fake_chat_no_cite)
    out2 = _debate(cid).json()
    assert out2["engine"] == "deterministic"
    assert out2["citations"], "模板反驳必须带引用锚"
    got = client.get(f"/api/v1/cards/{cid}", headers=AUTH).json()
    assert got["strongest_objection"] == out2["objection"]


def test_debate_404_unknown_and_sealed() -> None:
    assert _debate("nonexistent").status_code == 404
    cid = _create_card()
    r = client.post(f"/api/v1/cards/{cid}/change",
                    json={"position": "libertarianism"}, headers=AUTH)
    assert r.status_code == 200  # 旧卡封存
    assert _debate(cid).status_code == 404


def test_debate_422_not_indexed() -> None:
    cid = _create_card(question="今天午饭吃什么", position="吃面", question_ref=None)
    r = _debate(cid)
    assert r.status_code == 422
    assert r.json()["detail"]["reason"] == "not_indexed"


def test_debate_god_opposing_by_pct() -> None:
    cid = _create_card(question="God", position="theism", question_ref="survey-2020:god")
    out = _debate(cid).json()
    assert out["opposing_options"][0]["option"] == "atheism"
    assert f"survey-2020:{GOD_Q}:atheism" in [c["id"] for c in out["citations"]]


def test_llm_client_unit(monkeypatch) -> None:
    """网关客户端：无 KEY→None；有 KEY 失败→LLMError；正常→content。"""
    monkeypatch.delenv("FD_ZHESI_LLM_API_KEY", raising=False)
    assert llm_mod.chat([{"role": "user", "content": "hi"}]) is None

    monkeypatch.setenv("FD_ZHESI_LLM_API_KEY", "k")
    monkeypatch.delenv("FD_ZHESI_LLM_BASE_URL", raising=False)

    def boom(url, **kwargs):
        import httpx
        raise httpx.ConnectError("down")

    monkeypatch.setattr("httpx.post", boom)
    with pytest.raises(llm_mod.LLMError):
        llm_mod.chat([{"role": "user", "content": "hi"}])

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": " 答案 "}}]}

    monkeypatch.setattr("httpx.post", lambda url, **k: FakeResp())
    assert llm_mod.chat([{"role": "user", "content": "hi"}]) == "答案"
