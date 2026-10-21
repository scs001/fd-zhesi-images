"""E2E 验收剧本（task 7.1）：新用户全链 + 双账号隔离。

链路：生活语言提问 → 概念澄清 → 表态 → 承受最强反驳并回应 → 补足立场后合成投影
→ 张力检测 → 思想年轮 → 剧创结构卡（授权→取卡）。双账号各跑一遍并互查隔离。

用法（本地，真参照系库）：
  FD_ZHESI_DB=/tmp/e2e.db FD_ZHESI_AUTH_DEV_TOKENS="tok-a=alice,tok-b=bob" \
  python3 -m uvicorn fd_zhesi_api.main:app --port 8013 &
  python3 scripts/e2e_walkthrough.py --base http://127.0.0.1:8013
不带 LLM KEY 时走确定性引擎（同样有效——闭环不强依赖 LLM）。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# 六个经典问题域的生活语言问句（凑足投影阈值 ≥5 张可映射卡）
ASKS = [
    "我的选择真是我自己做的吗，还是一切早已注定",
    "道德是对的还是只是我们的习惯",
    "上帝存在吗",
    "心灵能不能完全用物质解释",
    "知识主要来自经验还是理性",
    "今天的我和二十年后的我是同一个我吗",
]
POSITIONS = {  # 立场标签对齐 axis_map 实际词条（宁少勿错的保守映射表）
    "free will": "compatibilism",
    "meta-ethics": "moral realism",
    "god": "atheism",
    "mind": "physicalism",
    "knowledge": "empiricism",
    "identity": "biological view",
}


def call(base: str, token: str, method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        base + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def run_account(base: str, token: str, who: str) -> list[str]:
    cards = []
    for text in ASKS:
        code, out = call(base, token, "POST", "/api/v1/ask", {"text": text})
        assert code == 200, f"{who} ask {code}: {out}"
        qs = out.get("stance_questions", [])
        assert qs, f"{who} ask 未命中立场问题: {text}"
        q = qs[0]
        qkey = next((k for k in POSITIONS if k in q["question"].lower()), None)
        assert qkey, f"{who} 问题无法映射预设立场: {q['question']}"
        code, card = call(base, token, "POST", "/api/v1/cards", {
            "question": q["question"], "position": POSITIONS[qkey],
            "reasons": f"{who} 的理由", "question_ref": q.get("question_ref"),
        })
        assert code == 201, f"{who} 建卡 {code}"
        cards.append(card)
    print(f"[{who}] 建卡 {len(cards)} 张")

    # 辩：对第一张卡要最强反驳并回应
    code, obj = call(base, token, "POST", "/api/v1/debate/strongest-objection",
                     {"card_id": cards[0]["id"]})
    assert code == 200, f"{who} 辩 {code}: {obj}"
    assert obj.get("objection") and obj.get("citations"), f"{who} 反驳缺内容或引用"
    code, r = call(base, token, "POST", f"/api/v1/cards/{cards[0]['id']}/response",
                   {"my_response": "我的回应", "stability": "wavering"})
    assert code == 200 and r["stability"] == "wavering"
    print(f"[{who}] 辩闭环 ok（{len(obj['citations'])} 引用，engine={obj.get('engine')}）")

    # 谱：投影（≥5 张可映射卡）
    code, proj = call(base, token, "POST", "/api/v1/synthesis/project")
    assert code == 201, f"{who} 投影 {code}: {proj}"
    assert proj["axes"] and len(proj["neighbors"]) >= 3
    print(f"[{who}] 投影 ok：六轴={ {k: round(v,1) for k,v in list(proj['axes'].items())[:2]} }… "
          f"邻居1={proj['neighbors'][0].get('name_en')}")

    # 变更一张立场 → 年轮
    code, changed = call(base, token, "POST", f"/api/v1/cards/{cards[0]['id']}/change",
                         {"position": "other", "reasons": "想法变了"})
    assert code == 200, f"{who} 变更 {code}"
    code, annals = call(base, token, "GET", "/api/v1/cards/annals")
    assert code == 200 and len(annals["results"]) >= 1
    print(f"[{who}] 年轮 ok（{len(annals['results'])} 条）")

    # 张力簿：同题对立组合在此剧本里不必然出现，检测不炸+可查即过（宁缺毋滥语义）
    code, det = call(base, token, "POST", "/api/v1/synthesis/detect-tensions")
    assert code == 200, f"{who} 张力检测 {code}"
    code, tl = call(base, token, "GET", "/api/v1/synthesis/tensions")
    assert code == 200
    print(f"[{who}] 张力簿 ok（{len(tl['results'])} 条，检测组合 {det.get('checked_pairs', '?')} 对）")

    # 剧创结构卡：授权 → 取卡
    code, _ = call(base, token, "POST", "/api/v1/grants",
                   {"consumer": "juchuang", "card_kinds": ["stance", "tension"]})
    assert code == 201
    code, contract = call(base, token, "GET", "/api/v1/contract/cards?consumer=juchuang")
    assert code == 200 and contract["contract_version"] == "1"
    assert len(contract["cards"]) >= 5
    print(f"[{who}] 结构卡 ok（{len(contract['cards'])} 张下发剧创）")
    return cards


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8013")
    args = ap.parse_args()

    a = run_account(args.base, "tok-a", "alice")
    b = run_account(args.base, "tok-b", "bob")

    # 隔离：bob 看不到 alice 的卡
    code, out = call(args.base, "tok-b", "GET", "/api/v1/cards?status=active")
    assert code == 200
    a_ids = {c["id"] for c in a}
    assert not a_ids & {c["id"] for c in out["results"]}, "隔离失败：bob 看到了 alice 的卡"
    code, out = call(args.base, "tok-b", "GET", f"/api/v1/cards/{a[0]['id']}")
    assert code == 404
    print("[隔离] bob 看不到 alice 的卡（列表+单查双验）")

    print("\nE2E 双账号全链通过：问→辩→谱→年轮→张力→剧创卡。全链留痕见服务端 audit_log。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
