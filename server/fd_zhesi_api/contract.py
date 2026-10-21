"""剧创结构卡契约（task 5.1）：版本化 JSON API，向后兼容，授权范围受控。

契约口径（design D6 / spec「剧创结构卡契约」）：
- 剧创（或任何 consumer）取卡必须同时满足：用户令牌 + 用户对该 consumer 的
  有效授权（grants 表，范围到卡类：stance/tension）
- 响应带 contract_version；新增字段只做增量，不删不改既有字段
- 每次跨线取卡写审计留痕（consumer + user + 卡类）
"""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import personal
from .auth import require_user

router = APIRouter(prefix="/api/v1", tags=["contract"])

CONTRACT_VERSION = "1"


class GrantIn(BaseModel):
    consumer: str = Field(min_length=1)
    card_kinds: list[str] = Field(min_length=1)


def _db():
    conn = personal.connect()
    personal.migrate(conn)
    return conn


@router.post("/grants", status_code=201)
def create_grant(body: GrantIn, user_id: str = Depends(require_user)) -> dict:
    conn = _db()
    try:
        out = personal.grant(conn, user_id, body.consumer, body.card_kinds)
        personal.audit(conn, user_id, "grant.create", body.consumer, "allowed")
        return out
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        conn.close()


@router.get("/contract/cards")
def contract_cards(consumer: str, user_id: str = Depends(require_user)) -> dict:
    """剧创取结构卡：立场卡（含张力簿条目的卡 id 关联）按授权范围返回。"""
    conn = _db()
    try:
        g = personal.active_grant(conn, user_id, consumer)
        if not g or "stance" not in g["card_kinds"]:
            personal.audit(conn, user_id, "contract.cards", consumer, "denied",
                           detail="no active grant for stance")
            raise HTTPException(403, f"用户未对 {consumer} 开放立场卡")
        cards = personal.list_cards(conn, user_id, "active")
        tensions = []
        if "tension" in g["card_kinds"]:
            rows = conn.execute(
                "SELECT * FROM tensions WHERE user_id=? AND status='open'", (user_id,)
            ).fetchall()
            tensions = [
                {
                    "id": r["id"],
                    "card_ids": json.loads(r["card_ids"]),
                    "description": r["description"],
                    "source": r["source"],
                }
                for r in rows
            ]
        personal.audit(conn, user_id, "contract.cards", consumer, "allowed",
                       detail=f"kinds={g['card_kinds']} cards={len(cards)}")
        # 契约字段集：只增不删不改；剧创侧按 contract_version 消费
        return {
            "contract_version": CONTRACT_VERSION,
            "consumer": consumer,
            "cards": [
                {
                    "id": c["id"],
                    "question": c["question"],
                    "question_ref": c["question_ref"],
                    "position": c["position"],
                    "stability": c["stability"],
                    "strongest_objection": c["strongest_objection"],
                    "as_of": c["updated_at"],
                }
                for c in cards
            ],
            "tensions": tensions,
        }
    finally:
        conn.close()
