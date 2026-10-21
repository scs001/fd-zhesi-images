"""经典立场问题 → 六轴增量向量映射表（task 4.3 谱闭环，纯数据 + 判定函数）。

六轴沿用 Philosophy Atlas 轴系（design D4）：individualism / materialism /
rationalism / determinism / transcendence / universalism，参照系哲学家取值
0-10。本表给每个经典问题的每个选项一个 ±(0.5~2) 的轴增量（稀疏表示，零增量
省略），多卡增量求和后锚定到 Atlas 空间（见 synthesis.compute_axes）。

保守原则（spec「宁少勿错」）：只有选项与轴的哲学关联足够著名/直接才入表；
无把握的问题（如 A/B 理论、Newcomb、真理论）不入。问题串与选项标签照抄
PhilPapers Survey 2009/2020 官方串（与参照系 stances 表逐字一致），另配
短别名便于生活语言建卡后的精确匹配；模糊归一是问闭环（4.1）的事。
"""

from __future__ import annotations

from dataclasses import dataclass

AXES = (
    "individualism",
    "materialism",
    "rationalism",
    "determinism",
    "transcendence",
    "universalism",
)

AXES_VERSION = "1"  # 轴语义 + 增量表版本：表变更大版本 bump，投影历史仍可解释

# question_key → {
#   "questions": 照抄 survey 的问题串（2009/2020 逐字），
#   "aliases":   短别名（question_ref "survey-2020:<topic>" 的 topic 也按此匹配），
#   "options":   {选项标签（照抄 survey）: {轴: 增量}}，
# }
AXIS_MAP: dict[str, dict] = {
    "free_will": {
        "questions": ["Free will: compatibilism, libertarianism, or no free will?"],
        "aliases": ["free will", "自由意志"],
        "options": {
            "compatibilism": {"determinism": 1.5},
            "libertarianism": {"determinism": -2.0},
            "no free will": {"determinism": 2.0},
        },
    },
    "god": {
        "questions": ["God: theism or atheism?"],
        "aliases": ["god", "上帝"],
        "options": {
            "theism": {"transcendence": 2.0, "materialism": -1.0},
            "atheism": {"transcendence": -2.0, "materialism": 1.0},
        },
    },
    "meta_ethics": {
        "questions": [
            "Meta-ethics: moral realism, moral anti-realism, or error theory?",
            "Meta-ethics: moral realism or moral anti-realism?",
        ],
        "aliases": ["meta-ethics", "元伦理学"],
        "options": {
            "moral realism": {"transcendence": 1.0, "universalism": 0.5},
            "moral anti-realism": {"transcendence": -1.0, "universalism": -0.5},
            "error theory": {"transcendence": -1.0, "universalism": -1.0},
        },
    },
    "morality": {
        "questions": [
            "Morality: non-naturalism, naturalist realism, constructivism,"
            " expressivism, or error theory?"
        ],
        "aliases": ["morality", "道德"],
        "options": {
            "non-naturalism": {"transcendence": 1.5, "universalism": 0.5},
            "naturalist realism": {"universalism": 0.5},
            "constructivism": {"universalism": 0.5},
            "expressivism": {"universalism": -0.5, "transcendence": -0.5},
            "error theory": {"transcendence": -1.0, "universalism": -1.0},
        },
    },
    "mind": {
        "questions": ["Mind: physicalism or non-physicalism?"],
        "aliases": ["mind", "心灵"],
        "options": {
            "physicalism": {"materialism": 1.5},
            "non-physicalism": {"materialism": -1.5, "transcendence": 0.5},
        },
    },
    "consciousness": {
        "questions": [
            "Consciousness: dualism, eliminativism, functionalism, identity"
            " theory, or panpsychism?"
        ],
        "aliases": ["consciousness", "意识"],
        "options": {
            "dualism": {"materialism": -1.5, "transcendence": 0.5},
            "eliminativism": {"materialism": 1.5, "transcendence": -0.5},
            "functionalism": {"materialism": 1.0},
            "identity theory": {"materialism": 1.5},
            "panpsychism": {"materialism": -0.5, "transcendence": 1.0},
        },
    },
    "knowledge": {
        "questions": ["Knowledge: empiricism or rationalism?"],
        "aliases": ["knowledge", "知识"],
        "options": {
            "empiricism": {"rationalism": -1.5},
            "rationalism": {"rationalism": 1.5},
        },
    },
    "a_priori": {
        "questions": ["A priori knowledge: yes or no?"],
        "aliases": ["a priori knowledge", "a priori", "先验知识"],
        "options": {
            "yes": {"rationalism": 1.5},
            "no": {"rationalism": -1.5},
        },
    },
    "zombies": {
        "questions": [
            "Zombies: inconceivable, conceivable but not metaphysically"
            " possible, or metaphysically possible?"
        ],
        "aliases": ["zombies", "僵尸"],
        "options": {
            "inconceivable": {"materialism": 1.0},
            "conceivable but not metaphysically possible": {"materialism": 0.5},
            "metaphysically possible": {"materialism": -1.5, "transcendence": 0.5},
        },
    },
    "normative_ethics": {
        "questions": ["Normative ethics: deontology, consequentialism, or virtue ethics?"],
        "aliases": ["normative ethics", "规范伦理学"],
        "options": {
            "deontology": {"rationalism": 0.5, "universalism": 0.5},
            "consequentialism": {"universalism": 0.5, "individualism": -0.5},
            "virtue ethics": {"universalism": -0.5, "individualism": 0.5},
        },
    },
    "politics": {
        "questions": [
            "Politics: communitarianism, egalitarianism, or libertarianism?",
            "Political philosophy: communitarianism, egalitarianism, or"
            " libertarianism?",
        ],
        "aliases": ["politics", "political philosophy", "政治哲学"],
        "options": {
            "libertarianism": {"individualism": 2.0},
            "communitarianism": {"individualism": -1.5, "universalism": -0.5},
            "egalitarianism": {"individualism": -0.5, "universalism": 0.5},
        },
    },
    "politics_econ": {
        "questions": ["Politics: capitalism or socialism?"],
        "aliases": ["capitalism or socialism", "经济制度"],
        "options": {
            "capitalism": {"individualism": 1.0},
            "socialism": {"individualism": -1.0},
        },
    },
    "moral_judgment": {
        "questions": ["Moral judgment: cognitivism or non-cognitivism?"],
        "aliases": ["moral judgment", "道德判断"],
        "options": {
            "cognitivism": {"universalism": 0.5, "rationalism": 0.5},
            "non-cognitivism": {"universalism": -0.5, "transcendence": -0.5},
        },
    },
    "metaphilosophy": {
        "questions": ["Metaphilosophy: naturalism or non-naturalism?"],
        "aliases": ["metaphilosophy", "形而上学哲学观"],
        "options": {
            "naturalism": {"materialism": 1.0, "transcendence": -1.0},
            "non-naturalism": {"materialism": -1.0, "transcendence": 1.0},
        },
    },
    "science": {
        "questions": ["Science: scientific realism or scientific anti-realism?"],
        "aliases": ["science", "科学"],
        "options": {
            "scientific realism": {"materialism": 0.5},
            "scientific anti-realism": {"materialism": -0.5},
        },
    },
    "abstract_objects": {
        "questions": ["Abstract objects: Platonism or nominalism?"],
        "aliases": ["abstract objects", "抽象对象"],
        "options": {
            "Platonism": {"transcendence": 1.0, "materialism": -1.0, "rationalism": 0.5},
            "nominalism": {"materialism": 1.0, "transcendence": -0.5},
        },
    },
    "personal_identity": {
        "questions": [
            "Personal identity: psychological view, biological view, or"
            " further-fact view?",
            "Personal identity: biological view, psychological view, or"
            " further-fact view?",
        ],
        "aliases": ["personal identity", "人格同一性"],
        "options": {
            "biological view": {"materialism": 0.5},
            "further-fact view": {"transcendence": 1.5, "materialism": -1.0},
        },
    },
    "external_world": {
        "questions": [
            "External world: idealism, skepticism, or non-skeptical realism?"
        ],
        "aliases": ["external world", "外部世界"],
        "options": {
            "idealism": {"materialism": -2.0, "transcendence": 1.0},
        },
    },
    "meaning_of_life": {
        "questions": ["Meaning of life: subjective, objective, or nonexistent?"],
        "aliases": ["meaning of life", "人生意义"],
        "options": {
            "objective": {"transcendence": 1.0, "universalism": 0.5},
            "subjective": {"individualism": 1.0, "transcendence": -0.5},
            "nonexistent": {"transcendence": -1.0, "materialism": 0.5},
        },
    },
    "moral_principles": {
        "questions": ["Moral principles: moral generalism or moral particularism?"],
        "aliases": ["moral principles", "道德原则"],
        "options": {
            "moral generalism": {"universalism": 1.0, "rationalism": 0.5},
            "moral particularism": {"universalism": -1.0, "individualism": 0.5},
        },
    },
    "teletransporter": {
        "questions": ["Teletransporter (new matter): survival or death?"],
        "aliases": ["teletransporter", "传送机"],
        "options": {
            "survival": {"materialism": -0.5},
            "death": {"materialism": 1.0},
        },
    },
    "well_being": {
        "questions": ["Well-being: hedonism, desire satisfaction, or objective list?"],
        "aliases": ["well-being", "wellbeing", "福祉"],
        "options": {
            "hedonism": {"materialism": 0.5},
            "desire satisfaction": {"individualism": 1.0},
            "objective list": {"transcendence": 0.5, "universalism": 0.5},
        },
    },
    "aesthetic_value": {
        "questions": ["Aesthetic value: objective or subjective?"],
        "aliases": ["aesthetic value", "审美价值"],
        "options": {
            "objective": {"universalism": 0.5, "transcendence": 0.5},
            "subjective": {"universalism": -0.5, "individualism": 0.5},
        },
    },
    "chinese_room": {
        "questions": ["Chinese room: understands or doesn't understand?"],
        "aliases": ["chinese room", "中文房间"],
        "options": {
            "understands": {"materialism": 0.5},
            "doesn't understand": {"materialism": -0.5},
        },
    },
    "hard_problem": {
        "questions": ["Hard problem of consciousness (is there one?): yes or no?"],
        "aliases": ["hard problem of consciousness", "hard problem", "意识的难问题"],
        "options": {
            "yes": {"materialism": -1.0, "transcendence": 0.5},
            "no": {"materialism": 0.5},
        },
    },
    "psr": {
        "questions": ["Principle of sufficient reason: true or false?"],
        "aliases": ["principle of sufficient reason", "充足理由律"],
        "options": {
            "true": {"determinism": 1.0, "rationalism": 0.5},
            "false": {"determinism": -0.5},
        },
    },
}


@dataclass(frozen=True)
class ResolvedStance:
    """一张立场卡在轴空间中的落点。"""

    question_key: str
    position: str
    deltas: dict[str, float]


def _norm(s: str) -> str:
    """归一化：casefold + 压空白 + 去尾部问号（中英）。"""
    t = " ".join(s.casefold().split())
    while t.endswith(("?", "？")):
        t = t[:-1].rstrip()
    return t


# 预编译查找索引：归一化问题串/别名 → question_key
_QUESTION_INDEX: dict[str, str] = {}
for _key, _spec in AXIS_MAP.items():
    for _q in _spec["questions"] + _spec["aliases"]:
        _QUESTION_INDEX[_norm(_q)] = _key

_OPTION_INDEX: dict[tuple[str, str], str] = {}
for _key, _spec in AXIS_MAP.items():
    for _opt in _spec["options"]:
        _OPTION_INDEX[(_key, _norm(_opt))] = _opt


def question_keys() -> list[str]:
    return list(AXIS_MAP)


def resolve_question(question: str, question_ref: str | None = None) -> str | None:
    """问题串（或 survey question_ref 的 topic 部分）→ question_key；无则 None。

    只做确定性精确匹配（归一化后相等）；生活语言的模糊归一属问闭环（4.1）。
    """
    key = _QUESTION_INDEX.get(_norm(question or ""))
    if key:
        return key
    if question_ref:
        # question_ref 形如 "survey-2020:free will"——canonical 坐标优先于自由文本
        _, _, topic = question_ref.partition(":")
        return _QUESTION_INDEX.get(_norm(topic))
    return None


def resolve(question: str, position: str, question_ref: str | None = None) -> ResolvedStance | None:
    """立场卡 (question, position) → 轴增量；问题或选项任一映射不上则 None。"""
    key = resolve_question(question, question_ref)
    if not key:
        return None
    opt = _OPTION_INDEX.get((key, _norm(position or "")))
    if not opt:
        return None
    deltas = dict(AXIS_MAP[key]["options"][opt])
    for axis in deltas:
        assert axis in AXES, f"未知轴 {axis}（axis_map 笔误）"
    return ResolvedStance(question_key=key, position=opt, deltas=deltas)
