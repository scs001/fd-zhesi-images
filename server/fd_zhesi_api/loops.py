"""问/辩两闭环（task 4.1/4.2）：平民语言进、哲学坐标出；最强反驳、引用锚定。

main.py 挂载（接线时加两行）：
    from .loops import router as loops_router
    app.include_router(loops_router)

铁律：
- 确定性映射层永远可用（无 LLM/LLM 失败也能出结果，engine=deterministic）；
- 概念定义只锚定参照系 concepts 表行，不编造（concepts 查不到就返回空）；
- 参照系库（fd-zhesi-reference，env FD_ZHESI_REF_DB）只读，绝不写；
  个人层写入只经 personal.* 既有函数；
- 辩闭环输出的每个引用 cite id 必须存在于候选集，校验不过的引用剥除
  （宁删勿假），无引用锚的论证不出现在输出。
"""

from __future__ import annotations

import json
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import llm, personal
from .auth import require_user

router = APIRouter(prefix="/api/v1", tags=["loops"])

# ---------------------------------------------------------------------------
# 生活语言 → 立场问题：确定性映射表（task 4.1 第 1 层，不依赖 LLM）
#
# 覆盖 PhilPapers Survey 2009/2020 经典问题集的 28 个问题域；question 必须
# 与参照系 stances.question 精确一致（大小写不敏感）。keywords 中英混合：
# 中文子串匹配、英文按词边界匹配；terms 是 concepts 表的锚定词条（查不到
# 即返回空，不编造定义）。
# ---------------------------------------------------------------------------

QUESTION_DOMAINS: list[dict] = [
    {
        "key": "free-will",
        "question": "Free will: compatibilism, libertarianism, or no free will?",
        "keywords": ["自由意志", "决定论", "宿命论", "宿命", "命运", "早已注定", "注定",
                      "自由吗", "有没有自由", "free will", "determinism", "fatalism",
                      "fate", "destiny", "predetermined"],
        "terms": ["free will", "compatibilism", "determinism"],
    },
    {
        "key": "god",
        "question": "God: theism or atheism?",
        "keywords": ["上帝", "造物主", "神存在", "神是否存在", "有神论", "无神论",
                      "老天爷", "god", "theism", "atheism", "deity", "creator"],
        "terms": [],
    },
    {
        "key": "moral-realism",
        "question": "Meta-ethics: moral realism or moral anti-realism?",
        "keywords": ["道德客观", "道德是客观", "对错是客观", "善恶是客观", "客观道德",
                      "道德相对", "道德是主观", "对错只是习惯", "道德是对", "道德还是习惯",
                      "道德是习惯", "道德真的", "moral realism",
                      "moral anti-realism", "objective moral", "morality objective",
                      "moral facts", "moral relativism"],
        "terms": ["realism"],
    },
    {
        "key": "physicalism",
        "question": "Mind: physicalism or non-physicalism?",
        "keywords": ["物理主义", "心灵就是大脑", "意识只是大脑", "灵魂", "非物质的心灵",
                      "心灵能", "心灵能不能", "物质解释", "心灵可以完全",
                      "physicalism", "non-physicalism", "immaterial soul",
                      "immaterial souls", "mind just the brain", "mind is the brain",
                      "soul", "souls"],
        "terms": ["dualism"],
    },
    {
        "key": "hard-problem",
        "question": "Hard problem of consciousness (is there one?): yes or no?",
        "keywords": ["意识难题", "主观体验", "主观感受", "感受质", "是什么感觉",
                      "qualia", "hard problem", "subjective experience",
                      "what it is like", "phenomenal consciousness", "consciousness"],
        "terms": ["qualia"],
    },
    {
        "key": "zombies",
        "question": "Zombies: inconceivable, conceivable but not metaphysically possible, or metaphysically possible?",
        "keywords": ["哲学僵尸", "僵尸", "内心体验", "没有意识的人", "zombie", "zombies",
                      "no inner life", "no conscious experience"],
        "terms": ["qualia", "dualism"],
    },
    {
        "key": "trolley-switch",
        "question": "Trolley problem (five straight ahead, one on side track, turn requires switching, what ought one do?): switch or don't switch?",
        "keywords": ["电车难题", "电车", "拉杆", "扳道岔", "切换轨道", "side track",
                      "flip the switch", "switch the trolley", "trolley"],
        "terms": ["utilitarianism", "justice"],
    },
    {
        "key": "footbridge",
        "question": "Footbridge (pushing man off bridge will save five on track below, what ought one do?): push or don't push?",
        "keywords": ["推胖子", "天桥", "推下桥", "footbridge", "push the man"],
        "terms": ["utilitarianism"],
    },
    {
        "key": "normative-ethics",
        "question": "Normative ethics: deontology, consequentialism, or virtue ethics?",
        "keywords": ["义务论", "后果主义", "功利主义", "美德伦理", "德性伦理", "动机还是",
                      "deontology", "consequentialism", "virtue ethics", "utilitarianism"],
        "terms": ["utilitarianism", "justice"],
    },
    {
        "key": "personal-identity",
        "question": "Personal identity: biological view, psychological view, or further-fact view?",
        "keywords": ["同一个我", "还是同一个人", "还是同一个我", "二十年后的我", "同一性", "还是原来的我", "还是我吗", "我还是我", "换了身体",
                      "记忆连续", "personal identity", "same person"],
        "terms": [],
    },
    {
        "key": "teletransporter",
        "question": "Teletransporter (new matter): survival or death?",
        "keywords": ["传送器", "复制出一个新", "teletransporter", "teleporter"],
        "terms": [],
    },
    {
        "key": "knowledge-empiricism",
        "question": "Knowledge: empiricism or rationalism?",
        "keywords": ["经验论", "唯理论", "经验主义", "理性主义", "来自经验", "经验观察",
                      "知识来自", "天赋观念", "empiricism", "rationalism",
                      "innate ideas", "derived from experience"],
        "terms": ["empiricism", "epistemology", "Kant"],
    },
    {
        "key": "external-world",
        "question": "External world: idealism, skepticism, or non-skeptical realism?",
        "keywords": ["外部世界", "缸中之脑", "世界真实", "一切都是幻觉", "可能是一场梦",
                      "怀疑论", "唯心", "模拟世界", "brain in a vat", "external world",
                      "skepticism", "idealism", "simulation"],
        "terms": ["idealism", "epistemology", "Hegel"],
    },
    {
        "key": "truth",
        "question": "Truth: correspondence, deflationary, or epistemic?",
        "keywords": ["真理", "什么是真", "一句话为真", "为真", "与事实符合", "符合事实",
                      "correspondence theory", "what is truth", "truth"],
        "terms": ["realism", "pragmatism"],
    },
    {
        "key": "science-realism",
        "question": "Science: scientific realism or scientific anti-realism?",
        "keywords": ["科学实在", "科学理论是真的", "未观测实体", "理论实体", "电子", "夸克",
                      "scientific realism", "scientific anti-realism", "unobservable",
                      "electrons", "quarks"],
        "terms": ["realism"],
    },
    {
        "key": "abstract-objects",
        "question": "Abstract objects: Platonism or nominalism?",
        "keywords": ["抽象对象", "数学对象", "数字存在", "数字真实存在", "柏拉图主义",
                      "唯名论", "共相", "abstract objects", "platonism", "nominalism",
                      "mathematical objects", "universals"],
        "terms": ["nominalism"],
    },
    {
        "key": "a-priori",
        "question": "A priori knowledge: yes or no?",
        "keywords": ["先验知识", "先天知识", "先验真理", "不依赖经验", "先验地知道",
                      "a priori", "synthetic a priori"],
        "terms": ["epistemology", "Kant"],
    },
    {
        "key": "chinese-room",
        "question": "Chinese room: understands or doesn't understand?",
        "keywords": ["中文房间", "图灵测试", "机器理解", "真的理解", "机器能思考",
                      "机器有意识", "人工智能有心灵", "chinese room", "turing test",
                      "machine understanding", "really understands", "ai understands"],
        "terms": [],
    },
    {
        "key": "moral-cognitivism",
        "question": "Moral judgment: cognitivism or non-cognitivism?",
        "keywords": ["道德判断有真假", "道德判断", "道德语句", "认知主义", "非认知主义",
                      "cognitivism", "non-cognitivism", "moral sentences"],
        "terms": [],
    },
    {
        "key": "meaning-of-life",
        "question": "Meaning of life: subjective, objective, or nonexistent?",
        "keywords": ["人生意义", "人生的意义", "生命的意义", "生活意义", "活着的意义",
                      "meaning of life", "purpose of life", "what makes life meaningful"],
        "terms": ["existentialism", "daoism", "zen", "stoicism"],
    },
    {
        "key": "abortion",
        "question": "Abortion (first trimester, no special circumstances): permissible or impermissible?",
        "keywords": ["堕胎", "人工流产", "abortion"],
        "terms": [],
    },
    {
        "key": "capital-punishment",
        "question": "Capital punishment: permissible or impermissible?",
        "keywords": ["死刑", "capital punishment", "death penalty"],
        "terms": ["justice"],
    },
    {
        "key": "politics",
        "question": "Politics: capitalism or socialism?",
        "keywords": ["资本主义", "社会主义", "市场经济", "capitalism", "socialism"],
        "terms": ["justice"],
    },
    {
        "key": "political-philosophy",
        "question": "Political philosophy: communitarianism, egalitarianism, or libertarianism?",
        "keywords": ["平等主义", "自由至上主义", "社群主义", "分配正义", "egalitarianism",
                      "libertarianism", "communitarianism", "distributive justice"],
        "terms": ["justice"],
    },
    {
        "key": "well-being",
        "question": "Well-being: hedonism, desire satisfaction, or objective list?",
        "keywords": ["幸福是什么", "什么是幸福", "过得好", "美好生活", "well-being",
                      "wellbeing", "hedonism", "what makes a life go well", "the good life"],
        "terms": ["stoicism"],
    },
    {
        "key": "experience-machine",
        "question": "Experience machine (would you enter?): yes or no?",
        "keywords": ["体验机", "快乐机器", "虚拟幸福", "experience machine",
                      "nozick's machine"],
        "terms": [],
    },
    {
        "key": "time",
        "question": "Time: A-theory or B-theory?",
        "keywords": ["时间流逝", "时间真的在流", "时间的流动", "a-theory", "b-theory",
                      "passage of time"],
        "terms": [],
    },
    {
        "key": "newcomb",
        "question": "Newcomb's problem: one box or two boxes?",
        "keywords": ["纽康姆", "纽科姆", "newcomb", "one box or two"],
        "terms": [],
    },
]

_DOMAIN_INDEX = {d["key"]: d for d in QUESTION_DOMAINS}

_KW_CACHE: dict[str, re.Pattern[str]] = {}


def _kw_pattern(kw: str) -> re.Pattern[str]:
    pat = _KW_CACHE.get(kw)
    if pat is None:
        pat = re.compile(rf"(?<![a-z0-9]){re.escape(kw.lower())}(?![a-z0-9])")
        _KW_CACHE[kw] = pat
    return pat


def _kw_hit(kw: str, raw: str, low: str) -> bool:
    """中文关键词按子串、英文关键词按词边界（大小写不敏感）匹配。"""
    if any("\u4e00" <= ch <= "\u9fff" for ch in kw):
        return kw in raw
    return bool(_kw_pattern(kw).search(low))


def map_domains(text: str, cap: int = 5) -> list[dict]:
    """确定性映射：生活语言 → 命中的问题域（按命中关键词长度降序，越长越具体）。"""
    raw = (text or "").strip()
    low = raw.lower()
    scored: list[tuple[int, int, dict]] = []
    for order, d in enumerate(QUESTION_DOMAINS):
        best = max((len(k) for k in d["keywords"] if _kw_hit(k, raw, low)), default=0)
        if best:
            scored.append((-best, order, d))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [d for _, _, d in scored[:cap]]


# ---------------------------------------------------------------------------
# 参照系访问（只读！）
# ---------------------------------------------------------------------------


def _ref_conn() -> sqlite3.Connection:
    try:
        from fd_zhesi_reference.config import Settings
    except ImportError as exc:  # 环境未装参照系包：降级，不崩
        raise RuntimeError(f"fd_zhesi_reference 不可用: {exc}") from exc
    return Settings.from_env().connect()


def _stance_rows_for_question(conn: sqlite3.Connection, survey_round: str, q: str) -> list[sqlite3.Row]:
    """先精确（大小写不敏感）再前缀匹配；前缀命中多题时取最短题（最贴近的短标签）。"""
    rows = conn.execute(
        "SELECT * FROM stances WHERE survey_round=? AND question=? COLLATE NOCASE",
        (survey_round, q),
    ).fetchall()
    if rows:
        return sorted(rows, key=lambda r: -(r["pct"] or 0))
    rows = conn.execute(
        "SELECT * FROM stances WHERE survey_round=? AND question LIKE ?"
        " ORDER BY LENGTH(question), question",
        (survey_round, q + "%"),
    ).fetchall()
    if rows:
        first = rows[0]["question"]
        rows = [r for r in rows if r["question"] == first]
        return sorted(rows, key=lambda r: -(r["pct"] or 0))
    return []


def _rounds_to_try(conn: sqlite3.Connection) -> list[str]:
    rounds: list[str] = []
    latest = conn.execute("SELECT MAX(survey_round) FROM stances").fetchone()
    if latest and latest[0]:
        rounds.append(str(latest[0]))
    for r in ("2020", "2009"):
        if r not in rounds:
            rounds.append(r)
    return rounds


def _stance_question_payload(conn: sqlite3.Connection, question: str) -> dict | None:
    """问题 → {question, survey_round, question_ref, options[{option,label_zh,pct}], provenance}。"""
    for rd in _rounds_to_try(conn):
        rows = _stance_rows_for_question(conn, rd, question)
        if rows:
            q = rows[0]["question"]
            options = [
                {"option": r["option"], "label_zh": r["option_zh"] or r["option"], "pct": r["pct"]}
                for r in rows
            ]
            return {
                "question": q,
                "survey_round": rd,
                "question_ref": f"survey-{rd}:{q}",
                "options": options,
                "provenance": {
                    "source": "philpapers-survey",
                    "survey_round": rd,
                    "respondents": rows[0]["respondents"] if "respondents" in rows[0].keys() else None,
                },
            }
    return None


def _concept_cards(conn: sqlite3.Connection, terms: list[str], cap: int = 6) -> list[dict]:
    """概念卡只来自 concepts 表行（锚定 SEP），查不到就空——不编造定义。"""
    out: list[dict] = []
    seen: set[str] = set()
    for t in terms:
        rows = conn.execute(
            "SELECT term, title, url, snippet FROM concepts WHERE term=? COLLATE NOCASE LIMIT 3",
            (t,),
        ).fetchall()
        for r in rows:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            out.append({
                "term": r["term"],
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
                "provenance": {"source": "sep", "url": r["url"]},
            })
            if len(out) >= cap:
                return out
    return out


def _terms_for_question(question: str) -> list[str]:
    for d in QUESTION_DOMAINS:
        if d["question"].lower() == (question or "").strip().lower():
            return d["terms"]
    terms: list[str] = []
    for d in map_domains(question or "", cap=3):
        for t in d["terms"]:
            if t not in terms:
                terms.append(t)
    return terms


# ---------------------------------------------------------------------------
# LLM 归一层（可选增强；失败即降级，不重试）
# ---------------------------------------------------------------------------


def _parse_json(content: str) -> object | None:
    s = content.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _llm_pick_questions(text: str, domains: list[dict]) -> list[str] | None:
    """LLM 从候选清单严格选 1-3 个问题（不许发明）。返回 None 表示网关未配置。"""
    lines = "\n".join(f"{i}. {d['question']}" for i, d in enumerate(domains, 1))
    messages = [
        {"role": "system", "content": (
            "你是哲学问答导航员，把用户的生活语言问题映射到最贴近的经典立场问题。"
            "只能从候选清单里选，绝不发明新问题。只输出 JSON。"
        )},
        {"role": "user", "content": (
            f"用户的问题：{text}\n\n候选立场问题清单：\n{lines}\n\n"
            "选出最贴近的 1-3 个（确实都不贴近可为 0 个）。"
            '只输出 JSON：{"indices": [编号, ...]}'
        )},
    ]
    content = llm.chat(messages)
    if content is None:
        return None
    data = _parse_json(content)
    idx = data.get("indices") if isinstance(data, dict) else None  # type: ignore[attr-defined]
    if not isinstance(idx, list) or not all(
        isinstance(i, int) and not isinstance(i, bool) and 1 <= i <= len(domains) for i in idx
    ):
        raise llm.LLMError("ask 归一层返回的 indices 非法")
    return [domains[i - 1]["question"] for i in idx]


# ---------------------------------------------------------------------------
# 4.1 问闭环 API
# ---------------------------------------------------------------------------


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/ask")
def ask(body: AskIn, user_id: str = Depends(require_user)) -> dict:
    """平民语言进、哲学坐标出：确定性映射层 + 可选 LLM 归一层。"""
    det = map_domains(body.text)
    chosen: list[dict] = list(det)
    engine = "deterministic"

    if llm.is_configured():
        try:
            picks = _llm_pick_questions(body.text, QUESTION_DOMAINS)
            if picks is not None:  # None=未配置；列表（可空）=调用成功
                engine = "llm"
                for q in picks:
                    d = next((x for x in QUESTION_DOMAINS if x["question"] == q), None)
                    if d and d not in chosen:
                        chosen.append(d)
        except llm.LLMError:
            chosen = list(det)  # 失败降级：只用确定性层

    conn = personal.connect()
    try:
        personal.migrate(conn)
        personal.audit(conn, user_id, "loops.ask", None, "allowed",
                       detail=f"det={len(det)} engine={engine}")
    finally:
        conn.close()

    concept_cards: list[dict] = []
    stance_questions: list[dict] = []
    reason: str | None = None
    try:
        rc = _ref_conn()
        try:
            for d in chosen[:5]:
                payload = _stance_question_payload(rc, d["question"])
                if payload:
                    stance_questions.append(payload)
            terms: list[str] = []
            for d in chosen[:5]:
                for t in d["terms"]:
                    if t not in terms:
                        terms.append(t)
            concept_cards = _concept_cards(rc, terms)
        finally:
            rc.close()
    except (RuntimeError, sqlite3.Error):
        reason = "reference_unavailable"

    if reason is None and not chosen:
        reason = "no_match"
    elif reason is None and not stance_questions and not concept_cards:
        reason = "not_indexed"

    return {
        "text": body.text,
        "engine": engine,
        "domains": [d["key"] for d in chosen[:5]],
        "concept_cards": concept_cards,
        "stance_questions": stance_questions,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# 4.2 辩闭环：检索召回候选论证 + 生成 + 引用校验
# ---------------------------------------------------------------------------


class ObjectionIn(BaseModel):
    card_id: str = Field(min_length=1)


def _match_stance_distribution(conn: sqlite3.Connection, card: dict) -> dict | None:
    """定位该卡在 stances 的同题分布：question_ref 精确/前缀 → 卡问题直配 → 关键词映射。"""
    ref = (card.get("question_ref") or "").strip()
    m = re.match(r"^survey-(\d{4}):(.+)$", ref, re.IGNORECASE)
    if m:
        rows = _stance_rows_for_question(conn, m.group(1), m.group(2).strip())
        if rows:
            return {"survey_round": m.group(1), "question": rows[0]["question"], "rows": rows}
    q = (card.get("question") or "").strip()
    for rd in _rounds_to_try(conn):
        rows = _stance_rows_for_question(conn, rd, q)
        if rows:
            return {"survey_round": rd, "question": rows[0]["question"], "rows": rows}
    for d in map_domains(q, cap=3):
        for rd in _rounds_to_try(conn):
            rows = _stance_rows_for_question(conn, rd, d["question"])
            if rows:
                return {"survey_round": rd, "question": rows[0]["question"], "rows": rows}
    return None


def _opposing_options(dist: dict, position: str) -> list[dict]:
    """对立选项 = 除用户 position 外按 pct 降序（「传统中的对立面」检索召回）。"""
    pos = (position or "").strip().lower()
    out = []
    for r in dist["rows"]:
        opt = (r["option"] or "").strip()
        opt_zh = (r["option_zh"] or "").strip()
        if pos and (opt.lower() == pos or (opt_zh and opt_zh.lower() == pos)):
            continue
        out.append({"option": opt, "option_zh": r["option_zh"], "pct": r["pct"]})
    out.sort(key=lambda o: -(o["pct"] or 0))
    return out


def _critical_relations(conn: sqlite3.Connection, terms: list[str], cap: int = 3) -> list[dict]:
    """参照系 relations 的 critical 边：仅当概念词条对得上某位哲学家时召回（对得上才要）。"""
    ids: list[int] = []
    for t in terms:
        for r in conn.execute(
            "SELECT atlas_id FROM philosophers WHERE name_en=? COLLATE NOCASE"
            " OR name_en LIKE ? OR name_zh=?",
            (t, f"% {t}", t),
        ).fetchall():
            if r["atlas_id"] not in ids:
                ids.append(r["atlas_id"])
    out: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for aid in ids:
        rows = conn.execute(
            "SELECT r.source_id, r.target_id, r.weight, s.name_en AS sname, t.name_en AS tname"
            " FROM relations r"
            " JOIN philosophers s ON r.source_id = s.atlas_id"
            " JOIN philosophers t ON r.target_id = t.atlas_id"
            " WHERE r.polarity='critical' AND (r.source_id=? OR r.target_id=?)",
            (aid, aid),
        ).fetchall()
        for r in rows:
            key = (r["source_id"], r["target_id"])
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "id": f"atlas-critical:{r['source_id']}-{r['target_id']}",
                "source": "philosophy-atlas",
                "label": f"{r['sname']} → {r['tname']}（批判边 weight {r['weight']}）",
            })
            if len(out) >= cap:
                return out
    return out


def _citation_candidates(
    rc: sqlite3.Connection, dist: dict, opposing: list[dict], terms: list[str]
) -> list[dict]:
    """引用候选集：survey 对立选项 + concepts 的 SEP 条目 + relations critical 边。"""
    rd, q = dist["survey_round"], dist["question"]
    cands: list[dict] = []
    for o in opposing[:5]:
        cands.append({
            "id": f"survey-{rd}:{q}:{o['option']}",
            "source": "philpapers-survey",
            "label": f"{o['pct']}% {o['option']}（{o['option_zh'] or o['option']}）",
        })
    for c in _concept_cards(rc, terms, cap=3):
        cands.append({
            "id": f"sep:{c['url']}",
            "source": "sep",
            "label": f"SEP《{c['title']}》",
            "url": c["url"],
        })
    cands.extend(_critical_relations(rc, terms))
    return cands


_CITE_ID_RE = re.compile(r"(?:(?:survey-\d{4}|sep|atlas-critical):[^\s，。；、）)]+)")


def _scrub_invalid_ids(text: str, valid: set[str]) -> str:
    """正文里混入的非法 cite id 一律剥除（宁删勿假）。"""

    def repl(m: re.Match[str]) -> str:
        return m.group(0) if m.group(0) in valid else ""

    return _CITE_ID_RE.sub(repl, text).strip()


def _deterministic_objection(
    card: dict, dist: dict, opposing: list[dict], sep_cards: list[dict]
) -> tuple[str, list[str]]:
    """无 LLM/LLM 失败的模板反驳：对立选项 pct + 通俗释义 + SEP 条目。"""
    top = opposing[0]
    pct = f"{top['pct']:.1f}" if isinstance(top["pct"], (int, float)) else "若干"
    zh = top["option_zh"] or top["option"]
    text = (
        f"在你的立场「{card['position']}」之外，哲学传统中站得最稳的对立面是"
        f"「{top['option']}」：PhilPapers {dist['survey_round']} 年调查中 {pct}% 的受访"
        f"职业哲学家站在了它一边——{zh}。你的立场需要正面回应这一多数传统。"
    )
    cites = [f"survey-{dist['survey_round']}:{dist['question']}:{top['option']}"]
    if sep_cards:
        s = sep_cards[0]
        text += f"参见 SEP《{s['title']}》：{s['url']}。"
        cites.append(f"sep:{s['url']}")
    return text, cites


def _llm_objection(card: dict, dist: dict, cands: list[dict]) -> tuple[str, list[str]] | None:
    """LLM 写最强反驳：只准引用候选集内的 cite id；无有效引用返回 None（走模板）。"""
    lines = "\n".join(f"- {c['id']}  # {c['label']}" for c in cands)
    messages = [
        {"role": "system", "content": (
            "你是哲学辩论教练，为用户的立场构造来自哲学传统的最强反驳。"
            "铁律：只引用给定候选清单内的 cite id，不得编造引用，不得在正文里内联 cite id。"
            "只输出 JSON。"
        )},
        {"role": "user", "content": (
            f"用户立场卡：问题「{dist['question']}」（PhilPapers {dist['survey_round']} 调查题）；"
            f"我的立场：{card['position']}；我的理由：{card.get('reasons') or '（未填）'}。\n\n"
            f"可引用候选（cite id # 说明）：\n{lines}\n\n"
            "请写一段 100-200 字的最强反驳（中文，面向普通读者），把该立场最需要回应的对立"
            "论证讲清楚（可用对立选项的分布数据与 SEP 条目）。"
            '只输出 JSON：{"objection": "...", "citations": ["cite id", ...]}'
        )},
    ]
    content = llm.chat(messages)
    if content is None:
        return None
    data = _parse_json(content)
    if not isinstance(data, dict) or not isinstance(data.get("objection"), str) or not data["objection"].strip():
        raise llm.LLMError("辩闭环 LLM 返回非法")
    valid = {c["id"] for c in cands}
    cites = [c for c in (data.get("citations") or []) if isinstance(c, str) and c in valid]
    text = _scrub_invalid_ids(data["objection"].strip(), valid)
    if not cites:  # 无引用锚的论证不出现在输出 → 降级确定性模板
        return None
    return text, cites


@router.post("/debate/strongest-objection")
def strongest_objection(body: ObjectionIn, user_id: str = Depends(require_user)) -> dict:
    """最强反驳：检索召回候选 → 生成（LLM 或模板）→ 引用校验 → 回写立场卡。"""
    conn = personal.connect()
    try:
        personal.migrate(conn)
        card = personal.get_card(conn, user_id, body.card_id)
        if not card or card["status"] != "active":
            raise HTTPException(404, "卡不存在或已封存")

        try:
            rc = _ref_conn()
        except (RuntimeError, sqlite3.Error) as exc:
            raise HTTPException(422, {"reason": "reference_unavailable",
                                      "message": f"参照系不可用: {exc}"}) from exc
        try:
            dist = _match_stance_distribution(rc, card)
            if not dist:
                raise HTTPException(422, {
                    "reason": "not_indexed",
                    "message": f"「{card['question']}」在参照系 stances 无同题分布",
                })
            opposing = _opposing_options(dist, card["position"])
            terms = _terms_for_question(dist["question"])
            sep_cards = _concept_cards(rc, terms, cap=3)
            cands = _citation_candidates(rc, dist, opposing, terms)
        finally:
            rc.close()

        if not opposing:
            raise HTTPException(422, {"reason": "not_indexed",
                                      "message": "该题在 stances 无对立选项分布"})

        engine = "deterministic"
        result = None
        if llm.is_configured():
            try:
                result = _llm_objection(card, dist, cands)
                if result is not None:
                    engine = "llm"
            except llm.LLMError:
                result = None
        if result is None:
            text, cites = _deterministic_objection(card, dist, opposing, sep_cards)
        else:
            text, cites = result

        # 引用校验（spec 铁律）：输出的每个 cite id 必须在候选集内，否则剥除
        cand_ids = {c["id"] for c in cands}
        valid_cites = [c for c in cites if c in cand_ids]
        citations = [c for c in cands if c["id"] in set(valid_cites)]

        updated = personal.record_objection(conn, user_id, body.card_id, text)
        if not updated:
            raise HTTPException(404, "卡不存在或已封存")
        personal.audit(conn, user_id, "loops.objection", body.card_id, "allowed",
                       detail=f"engine={engine} cites={len(citations)}")

        return {
            "card_id": body.card_id,
            "question": dist["question"],
            "survey_round": dist["survey_round"],
            "opposing_options": opposing,
            "objection": text,
            "citations": citations,
            "engine": engine,
            "card": updated,
        }
    finally:
        conn.close()
