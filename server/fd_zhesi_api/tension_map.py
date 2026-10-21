"""已知立场间张力对表（task 4.4 张力簿，纯数据 + 判定函数）。

保守 curated（spec「宁缺毋滥」）：只收哲学史上真实著名、教科书级的立场
组合张力——同一问题的直接对立表态（用户同时持两卡即自相矛盾），或跨
问题但构成上明确不相容的经典组合。每条带一句话哲学史背景（source），
不编造冲突；没把握的组合不入表。

question_key/position 与 axis_map 同一套坐标（检测先经 axis_map.resolve
归一，映射不上的卡不参与张力检测——自由文本立场的比对属问闭环后续）。
"""

from __future__ import annotations

# questions=(q_a, q_b)、positions=(p_a, p_b)：a×b 与 b×a 等价（无序对）。
TENSION_PAIRS: list[dict] = [
    {
        "questions": ("god", "god"),
        "positions": ("theism", "atheism"),
        "description": "同时持有神论与无神论：对「上帝是否存在」的直接对立表态。",
        "source": "经典张力: 有神论与无神论是自然神学传统与启蒙无神论传统间最直接的对立。",
    },
    {
        "questions": ("meta_ethics", "meta_ethics"),
        "positions": ("moral realism", "moral anti-realism"),
        "description": "同持道德实在论与道德反实在论：道德事实是否存在，直接对立。",
        "source": "经典张力: 20 世纪元伦理学主线之争（Moore 式实在论 vs Ayer/Stevenson 非认知主义）。",
    },
    {
        "questions": ("meta_ethics", "meta_ethics"),
        "positions": ("moral realism", "error theory"),
        "description": "同持道德实在论与错误论：错误论断言一切肯定性道德判断皆为假。",
        "source": "经典张力: Mackie《伦理学：发明对与错》(1977) 的错误论直接否定道德实在论。",
    },
    {
        "questions": ("morality", "morality"),
        "positions": ("non-naturalism", "error theory"),
        "description": "同持道德非自然主义与错误论：一者肯定非自然道德事实，一者断言其不存在。",
        "source": "经典张力: Moore 式非自然主义与 Mackie 式错误论在道德形而上学上不相容。",
    },
    {
        "questions": ("morality", "morality"),
        "positions": ("naturalist realism", "expressivism"),
        "description": "同持自然主义道德实在论与表达主义：道德判断有真值 vs 只是态度表达。",
        "source": "经典张力: 实在论与表达主义的元伦理学百年对立（Cornell realism vs Blackburn/Gibbard）。",
    },
    {
        "questions": ("mind", "mind"),
        "positions": ("physicalism", "non-physicalism"),
        "description": "同持物理主义与非物理主义：心灵是否可还原为物理，直接对立。",
        "source": "经典张力: 心灵哲学本体论之争（Smart/Armstrong 物理主义 vs 反物理主义传统）。",
    },
    {
        "questions": ("mind", "consciousness"),
        "positions": ("physicalism", "dualism"),
        "description": "物理主义心灵观与意识的实体二元论不相容：二元论否认心灵随附于物理。",
        "source": "经典张力: 笛卡尔式二元论与当代物理主义关于意识地位的根本冲突。",
    },
    {
        "questions": ("mind", "zombies"),
        "positions": ("physicalism", "metaphysically possible"),
        "description": "物理主义与「哲学僵尸形而上可能」不相容：僵尸可能则现象属性不随附物理。",
        "source": "经典张力: Chalmers(1996) 僵尸可设想性论证被公认为反物理主义的标准论证。",
    },
    {
        "questions": ("mind", "external_world"),
        "positions": ("physicalism", "idealism"),
        "description": "物理主义与观念论不相容：观念论否认物质实体的心灵独立存在。",
        "source": "经典张力: 贝克莱式观念论（esse est percipi）与物理主义本体论直接冲突。",
    },
    {
        "questions": ("knowledge", "knowledge"),
        "positions": ("empiricism", "rationalism"),
        "description": "同持经验主义与理性主义：知识源于经验还是理性，直接对立表态。",
        "source": "经典张力: 近代哲学认识论主轴（Locke/Hume vs Descartes/Leibniz）。",
    },
    {
        "questions": ("knowledge", "a_priori"),
        "positions": ("empiricism", "yes"),
        "description": "彻底经验主义与承认先验知识不相容：经验主义否认独立于经验的知识。",
        "source": "经典张力: Hume 的经验主义原则与 Leibniz-Kant 先验知识传统冲突（「休谟的叉子」）。",
    },
    {
        "questions": ("knowledge", "a_priori"),
        "positions": ("rationalism", "no"),
        "description": "理性主义与否认先验知识不相容：先验知识是理性主义的根基。",
        "source": "经典张力: 否认先验知识即掏空理性主义（Leibniz 对 Locke《人类理解论》的回应）。",
    },
    {
        "questions": ("free_will", "free_will"),
        "positions": ("libertarianism", "no free will"),
        "description": "同持自由意志论与「无自由意志」：自由意志是否存在，直接对立。",
        "source": "经典张力: 形而上学自由意志论与硬决定论之争（Kane vs Pereboom/Honderich）。",
    },
    {
        "questions": ("free_will", "psr"),
        "positions": ("libertarianism", "true"),
        "description": "自由意志论与充足理由律不相容：万物皆有充分理由则无原初的自由行动。",
        "source": "经典张力: Spinoza 依充足理由律否认意志自由，与自由意志论者对立。",
    },
    {
        "questions": ("abstract_objects", "abstract_objects"),
        "positions": ("Platonism", "nominalism"),
        "description": "同持柏拉图主义与唯名论：抽象对象是否存在，直接对立。",
        "source": "经典张力: 共相问题的千年之争（Plato/Frege vs Ockham/Goodman）。",
    },
    {
        "questions": ("moral_principles", "moral_principles"),
        "positions": ("moral generalism", "moral particularism"),
        "description": "同持道德普遍主义与道德殊义论：道德是否由普遍原则支配，直接对立。",
        "source": "经典张力: Kant 式普遍道德法则 vs Dancy 殊义论（particularism）。",
    },
    {
        "questions": ("well_being", "well_being"),
        "positions": ("hedonism", "objective list"),
        "description": "同持快乐主义与客观清单论：福祉仅是快乐还是包含客观善，直接对立。",
        "source": "经典张力: Bentham/Mill 快乐主义与 Aristotle/Nussbaum 客观清单论之争。",
    },
    {
        "questions": ("consciousness", "consciousness"),
        "positions": ("dualism", "eliminativism"),
        "description": "同持意识二元论与取消主义：感受质有本体地位 vs 意识概念终将被取消。",
        "source": "经典张力: 笛卡尔传统与 Churchland 式取消主义关于意识存在的对立。",
    },
    {
        "questions": ("metaphilosophy", "metaphilosophy"),
        "positions": ("naturalism", "non-naturalism"),
        "description": "同持哲学自然主义与非自然主义：哲学是否连续于自然科学，直接对立。",
        "source": "经典张力: Quine 式自然化哲学与 Strawson 式先验/概念传统之争。",
    },
    {
        "questions": ("politics", "politics"),
        "positions": ("libertarianism", "communitarianism"),
        "description": "同持自由至上主义与社群主义：个人自由优先还是共同体优先，直接对立。",
        "source": "经典张力: Nozick 自由至上主义与 Sandel/MacIntyre 社群主义的当代政治哲学对立。",
    },
]


def _pair_key(questions: tuple[str, str], positions: tuple[str, str]) -> tuple:
    return tuple(sorted(zip(questions, positions)))


# 无序对索引：(q,p)×(q,p) → 条目
_TENSION_INDEX: dict[tuple, dict] = {}
for _entry in TENSION_PAIRS:
    _TENSION_INDEX[_pair_key(_entry["questions"], _entry["positions"])] = _entry


def lookup_tension(qa: str, pa: str, qb: str, pb: str) -> dict | None:
    """两已归一立场 (question_key, position) 是否构成已知张力对；无则 None。"""
    return _TENSION_INDEX.get(_pair_key((qa, qb), (pa, pb)))
