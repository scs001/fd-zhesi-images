"""个人层立场卡 API（task 3.2）。

全路由要求用户授权（task 3.3）；数据只落个人层自有库（物理分库铁律）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import personal
from .auth import require_user

router = APIRouter(prefix="/api/v1/cards", tags=["stance-cards"])


class CardCreate(BaseModel):
    question: str = Field(min_length=1)
    position: str = Field(min_length=1)
    reasons: str | None = None
    question_ref: str | None = None  # 参照系坐标，如 "survey-2020:free will"


class ObjectionIn(BaseModel):
    objection: str = Field(min_length=1)


class ResponseIn(BaseModel):
    my_response: str = Field(min_length=1)
    stability: str | None = Field(default=None)


class ChangeIn(BaseModel):
    position: str = Field(min_length=1)
    reasons: str | None = None


def _db():
    conn = personal.connect()
    personal.migrate(conn)
    return conn


@router.post("", status_code=201)
def create_card(body: CardCreate, user_id: str = Depends(require_user)) -> dict:
    conn = _db()
    try:
        card = personal.create_card(
            conn, user_id, body.question, body.position, body.reasons, body.question_ref
        )
        personal.audit(conn, user_id, "card.create", card["id"], "allowed")
        return card
    finally:
        conn.close()


@router.get("")
def list_cards(status: str = "active", user_id: str = Depends(require_user)) -> dict:
    if status not in ("active", "sealed"):
        raise HTTPException(422, "status 只支持 active/sealed")
    conn = _db()
    try:
        return {"results": personal.list_cards(conn, user_id, status)}
    finally:
        conn.close()


@router.get("/annals")
def annals(user_id: str = Depends(require_user)) -> dict:
    conn = _db()
    try:
        return {"results": personal.list_annals(conn, user_id)}
    finally:
        conn.close()


@router.get("/{card_id}")
def get_card(card_id: str, user_id: str = Depends(require_user)) -> dict:
    conn = _db()
    try:
        card = personal.get_card(conn, user_id, card_id)
        if not card:
            raise HTTPException(404, "卡不存在或不属于该用户")
        return card
    finally:
        conn.close()


@router.post("/{card_id}/objection")
def objection(card_id: str, body: ObjectionIn, user_id: str = Depends(require_user)) -> dict:
    """最强反驳入卡（4.2 辩闭环调用面；呈现与来源引用由 4.2 生成）。"""
    conn = _db()
    try:
        card = personal.record_objection(conn, user_id, card_id, body.objection)
        if not card:
            raise HTTPException(404, "卡不存在或已封存")
        return card
    finally:
        conn.close()


@router.post("/{card_id}/response")
def response(card_id: str, body: ResponseIn, user_id: str = Depends(require_user)) -> dict:
    conn = _db()
    try:
        card = personal.record_response(
            conn, user_id, card_id, body.my_response, body.stability
        )
        if not card:
            raise HTTPException(404, "卡不存在或已封存")
        return card
    finally:
        conn.close()


@router.post("/{card_id}/change")
def change(card_id: str, body: ChangeIn, user_id: str = Depends(require_user)) -> dict:
    """立场变更：旧卡封存入年轮、新卡开卡，历史可回溯。"""
    conn = _db()
    try:
        card = personal.change_position(conn, user_id, card_id, body.position, body.reasons)
        if not card:
            raise HTTPException(404, "卡不存在或已封存")
        personal.audit(conn, user_id, "card.change", card_id, "allowed",
                       detail=f"superseded_by={card['id']}")
        return card
    finally:
        conn.close()
