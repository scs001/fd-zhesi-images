"""谱闭环 + 张力簿 API（task 4.3 / 4.4）。

谱闭环：active 立场卡经 axis_map 归一为六轴增量，求和合成投影，并到参照
系 376 哲学家中找最近思想邻居；每次合成都是新版本、历史全保留（思想年轮
的投影面，spec「重合成保留历史」）。张力簿：active 卡两两组合对照
tension_map 的 curated 经典张力对，命中即入簿，重复检测不重复写。

投影语义（与 design D4「与种子数据同空间」对齐）：参照系哲学家六轴取值
0-10，故用户投影也锚定在同一 0-10 空间——各轴符号增量求和（clamp 到
[-10,10]）后加中性锚点 5.0，再 clamp 到 [0,10]，与哲学家邻居可直接算
欧氏距离。轴表版本随 axis_map.AXES_VERSION 存档，改表不破坏历史投影。

数据归属：投影与张力只落个人层自有库（personal，物理分库铁律）；参照系
库只读（仅 SELECT philosophers，绝不写）。
"""

from __future__ import annotations

import json
import math
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from . import personal
from .auth import require_user
from .axis_map import AXES, AXES_VERSION, resolve, resolve_question
from .tension_map import lookup_tension

router = APIRouter(prefix="/api/v1/synthesis", tags=["synthesis"])

SYNTHESIS_THRESHOLD = 5  # spec「立场积累达到合成阈值」：active 且可映射的卡各 ≥5
NEIGHBOR_COUNT = 8
NEUTRAL_ANCHOR = 5.0  # Atlas 六轴空间（0-10）的中点：无立场的中立位置


# ---- 领域逻辑（纯函数，测试直调） ----

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_axes(deltas_list: list[dict[str, float]]) -> dict[str, float]:
    """多张卡的轴增量 → 六轴投影（0-10 空间，见模块 docstring 的锚定语义）。"""
    axes: dict[str, float] = {}
    for axis in AXES:
        signed_sum = _clamp(sum(d.get(axis, 0.0) for d in deltas_list), -10.0, 10.0)
        axes[axis] = round(_clamp(NEUTRAL_ANCHOR + signed_sum, 0.0, 10.0), 2)
    return axes


def nearest_neighbors(
    axes: dict[str, float], ref_conn: sqlite3.Connection, limit: int = NEIGHBOR_COUNT,
) -> list[dict]:
    """参照系哲学家里按六轴欧氏距离取最近思想邻居（参照系只读）。"""
    rows = ref_conn.execute(
        "SELECT atlas_id, name_pt, name_en, name_zh,"
        " individualism, materialism, rationalism, determinism, transcendence,"
        " universalism FROM philosophers"
    ).fetchall()
    scored = []
    for r in rows:
        coords = [r[a] for a in AXES]
        if any(c is None for c in coords):
            continue  # 轴不完整的哲学家不参与（诚实：不臆造缺省值）
        dist = math.sqrt(sum((axes[a] - c) ** 2 for a, c in zip(AXES, coords)))
        scored.append({
            "atlas_id": r["atlas_id"],
            # Wikidata 回填缺名（en 345/zh 322）时回退 Atlas 原生 pt 名，不显示 NULL
            "name_en": r["name_en"] or r["name_pt"],
            "name_zh": r["name_zh"] or r["name_pt"],
            "distance": round(dist, 4),
        })
    scored.sort(key=lambda n: (n["distance"], n["atlas_id"]))
    return scored[:limit]


def _reference_conn() -> sqlite3.Connection:
    """打开参照系库（只读用途）。不可用/未摄取 → 明确 503，不静默空结果。"""
    try:
        from fd_zhesi_reference.config import Settings
    except ImportError as exc:  # pragma: no cover —— 环境缺包
        raise HTTPException(503, f"参照系服务包不可用: {exc}") from exc
    try:
        conn = Settings.from_env().connect()
        n = conn.execute("SELECT COUNT(*) FROM philosophers").fetchone()[0]
        if not n:
            raise HTTPException(503, "参照系库无哲学家数据（未摄取）")
        return conn
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(503, f"参照系库不可用: {exc}") from exc


def _db() -> sqlite3.Connection:
    conn = personal.connect()
    personal.migrate(conn)
    return conn


def _resolve_cards(cards: list[dict]) -> tuple[list[tuple[dict, object]], list[dict]]:
    """active 卡分成（可映射卡, 归一结果）与 skipped（诚实列出映射不上的）。"""
    resolved: list[tuple[dict, object]] = []
    skipped: list[dict] = []
    for card in cards:
        r = resolve(card["question"], card["position"], card.get("question_ref"))
        if r is None:
            key = resolve_question(card["question"], card.get("question_ref"))
            reason = "position_not_mapped" if key else "question_not_mapped"
            skipped.append({
                "card_id": card["id"], "question": card["question"],
                "position": card["position"], "reason": reason,
            })
        else:
            resolved.append((card, r))
    return resolved, skipped


# ---- 谱闭环：投影与思想邻居（4.3） ----

@router.post("/project", status_code=201)
def project(user_id: str = Depends(require_user)) -> dict:
    """合成六轴投影 + 最近 8 位思想邻居；每次调用产生新版本，历史保留。"""
    conn = _db()
    try:
        cards = personal.list_cards(conn, user_id, "active")
        if len(cards) < SYNTHESIS_THRESHOLD:
            raise HTTPException(
                412,
                f"active 立场卡 {len(cards)} 张，不足合成阈值 {SYNTHESIS_THRESHOLD} 张；"
                "继续表态积累后再合成",
            )
        resolved, skipped = _resolve_cards(cards)
        if len(resolved) < SYNTHESIS_THRESHOLD:
            raise HTTPException(
                412,
                f"active 立场卡 {len(cards)} 张，但可映射到六轴的仅 {len(resolved)} 张"
                f"（不足 {SYNTHESIS_THRESHOLD}）；请在经典立场问题上继续表态后再合成",
            )
        axes = compute_axes([r.deltas for _, r in resolved])
        ref = _reference_conn()
        try:
            neighbors = nearest_neighbors(axes, ref)
        finally:
            ref.close()
        pid = personal.new_id()
        ts = personal.now()
        conn.execute(
            "INSERT INTO projections (id, user_id, axes_version, axes, neighbors,"
            " based_on_cards, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                pid, user_id, AXES_VERSION,
                json.dumps(axes, ensure_ascii=False),
                json.dumps(neighbors, ensure_ascii=False),
                json.dumps([card["id"] for card, _ in resolved]),
                ts,
            ),
        )
        conn.commit()
        personal.audit(conn, user_id, "synthesis.project", pid, "allowed",
                       detail=f"mappable={len(resolved)}, skipped={len(skipped)}")
        return {
            "id": pid,
            "axes_version": AXES_VERSION,
            "axes": axes,
            "neighbors": neighbors,
            "based_on_cards": [card["id"] for card, _ in resolved],
            "active_count": len(cards),
            "mappable_count": len(resolved),
            "skipped": skipped,
            "created_at": ts,
        }
    finally:
        conn.close()


@router.get("/projections")
def list_projections(user_id: str = Depends(require_user)) -> dict:
    """历史投影版本列表，最新在前（重合成保留历史，可对比变迁）。"""
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT * FROM projections WHERE user_id=?"
            " ORDER BY rowid DESC",  # rowid=插入序 → 严格最新在前（时间戳同微秒也不乱序）
            (user_id,),
        ).fetchall()
        return {
            "results": [
                {
                    "id": r["id"],
                    "axes_version": r["axes_version"],
                    "axes": json.loads(r["axes"]),
                    "neighbors": json.loads(r["neighbors"]),
                    "based_on_cards": json.loads(r["based_on_cards"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        }
    finally:
        conn.close()


# ---- 张力簿：一致性检测（4.4） ----

def _tension_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "card_ids": json.loads(r["card_ids"]),
        "description": r["description"],
        "source": r["source"],
        "status": r["status"],
        "created_at": r["created_at"],
        "resolved_at": r["resolved_at"],
    }


@router.post("/detect-tensions")
def detect_tensions(user_id: str = Depends(require_user)) -> dict:
    """扫 active 卡两两组合对照 curated 张力对；命中入簿，重复检测不重复写。"""
    conn = _db()
    try:
        cards = personal.list_cards(conn, user_id, "active")
        resolved, _skipped = _resolve_cards(cards)
        existing = conn.execute(
            "SELECT card_ids, description FROM tensions WHERE user_id=?",
            (user_id,),
        ).fetchall()
        seen = {
            (frozenset(json.loads(r["card_ids"])), r["description"]) for r in existing
        }
        created: list[dict] = []
        for i in range(len(resolved)):
            for j in range(i + 1, len(resolved)):
                card_a, ra = resolved[i]
                card_b, rb = resolved[j]
                entry = lookup_tension(ra.question_key, ra.position,
                                       rb.question_key, rb.position)
                if not entry:
                    continue  # 宁缺毋滥：无已知张力不生成记录
                card_ids = sorted([card_a["id"], card_b["id"]])
                dedupe_key = (frozenset(card_ids), entry["description"])
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                tid = personal.new_id()
                ts = personal.now()
                conn.execute(
                    "INSERT INTO tensions (id, user_id, card_ids, description,"
                    " source, status, created_at) VALUES (?,?,?,?,?,'open',?)",
                    (tid, user_id, json.dumps(card_ids), entry["description"],
                     entry["source"], ts),
                )
                created.append({
                    "id": tid,
                    "card_ids": card_ids,
                    "description": entry["description"],
                    "source": entry["source"],
                    "status": "open",
                    "created_at": ts,
                })
        conn.commit()
        open_count = conn.execute(
            "SELECT COUNT(*) FROM tensions WHERE user_id=? AND status='open'",
            (user_id,),
        ).fetchone()[0]
        if created:
            personal.audit(conn, user_id, "synthesis.detect_tensions",
                           user_id, "allowed", detail=f"new={len(created)}")
        return {"created": created, "open_count": open_count,
                "checked_pairs": len(resolved) * (len(resolved) - 1) // 2}
    finally:
        conn.close()


@router.get("/tensions")
def list_tensions(status: str | None = None, user_id: str = Depends(require_user)) -> dict:
    """张力簿列表（最新在前）；status 可选过滤 open/resolved。"""
    if status and status not in ("open", "resolved"):
        raise HTTPException(422, "status 只支持 open/resolved")
    conn = _db()
    try:
        sql = "SELECT * FROM tensions WHERE user_id=?"
        params: list = [user_id]
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY rowid DESC"
        rows = conn.execute(sql, params).fetchall()
        return {"results": [_tension_row(r) for r in rows]}
    finally:
        conn.close()
