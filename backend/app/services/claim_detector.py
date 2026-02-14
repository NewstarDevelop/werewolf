"""Centralized role claim detection from speech content.

NEW-7: Replaces duplicated hardcoded text matching in llm.py and prompts.py
with a single source of truth. Results are stored in Game.claimed_roles.
"""
from typing import Optional

# Seer claim patterns (positive)
_SEER_PATTERNS_ZH = [
    "我是预言家", "本预言家", "作为预言家",
    "我验了", "我查验", "我昨晚验", "我昨晚查",
    "给了金水", "给了查杀", "验到金水", "验到查杀", "验出狼", "验到",
    "金水", "查杀"
]
_SEER_PATTERNS_EN = [
    "i am the seer", "i'm the seer", "as the seer",
    "i checked", "i verified", "last night i checked",
    "found werewolf", "found good", "gave gold", "gave kill"
]

# Negative patterns (deny / accuse)
_SEER_NEGATIVE_ZH = ["不是预言家", "假预言家", "狼人悍跳预言家"]
_SEER_NEGATIVE_EN = ["not the seer", "fake seer", "werewolf claiming seer"]

# Hunter claim patterns
_HUNTER_PATTERNS_ZH = ["我是猎人", "本猎人", "作为猎人"]
_HUNTER_PATTERNS_EN = ["i am the hunter", "i'm the hunter", "as the hunter"]

# Guard claim patterns
_GUARD_PATTERNS_ZH = ["我是守卫", "本守卫", "作为守卫"]
_GUARD_PATTERNS_EN = ["i am the guard", "i'm the guard", "as the guard"]

# Witch claim patterns
_WITCH_PATTERNS_ZH = ["我是女巫", "本女巫", "作为女巫"]
_WITCH_PATTERNS_EN = ["i am the witch", "i'm the witch", "as the witch"]

# Villager claim patterns
_VILLAGER_PATTERNS_ZH = ["我是平民", "我是民", "我是村民"]
_VILLAGER_PATTERNS_EN = ["i am a villager", "i'm a villager", "i am villager"]

# All role patterns: (role_key, positive_patterns, negative_patterns)
_ROLE_PATTERNS = [
    ("seer",
     _SEER_PATTERNS_ZH + _SEER_PATTERNS_EN,
     _SEER_NEGATIVE_ZH + _SEER_NEGATIVE_EN),
    ("hunter",
     _HUNTER_PATTERNS_ZH + _HUNTER_PATTERNS_EN,
     []),
    ("guard",
     _GUARD_PATTERNS_ZH + _GUARD_PATTERNS_EN,
     []),
    ("witch",
     _WITCH_PATTERNS_ZH + _WITCH_PATTERNS_EN,
     []),
    ("villager",
     _VILLAGER_PATTERNS_ZH + _VILLAGER_PATTERNS_EN,
     []),
]


def detect_role_claim(content: str) -> Optional[str]:
    """Detect if speech content contains a role claim.

    Returns the claimed role string (e.g. "seer", "hunter") or None.
    Seer claims are checked first as they have the highest strategic impact.
    """
    lower = content.lower()

    for role_key, positive, negative in _ROLE_PATTERNS:
        if any(p.lower() in lower for p in positive):
            if negative and any(n.lower() in lower for n in negative):
                continue  # Negative match — this is denial, not a claim
            return role_key

    return None


def has_seer_claim(claimed_roles: dict[int, str], exclude_seat: Optional[int] = None) -> bool:
    """Check if any player (optionally excluding a seat) has claimed seer."""
    for seat, role in claimed_roles.items():
        if role == "seer" and seat != exclude_seat:
            return True
    return False
