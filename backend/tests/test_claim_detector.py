"""Tests for claim_detector service.

Validates role claim detection from speech content (NEW-7).
"""
import pytest
from app.services.claim_detector import detect_role_claim, has_seer_claim


class TestDetectRoleClaim:
    """Tests for detect_role_claim()."""

    # --- Seer claims (Chinese) ---
    @pytest.mark.parametrize("text", [
        "我是预言家，我昨晚验了3号",
        "本预言家查验了5号，是金水",
        "作为预言家我给了6号查杀",
        "我验了4号是好人",
        "我昨晚查了2号，验到金水",
        "我给了1号金水",
        "验出狼了，3号是狼",
    ])
    def test_seer_claim_zh(self, text):
        assert detect_role_claim(text) == "seer"

    # --- Seer claims (English) ---
    @pytest.mark.parametrize("text", [
        "I am the seer, I checked player 3",
        "I'm the seer and I verified player 5",
        "As the seer, last night I checked player 2",
        "I found werewolf on seat 3",
        "I gave gold to player 4",
    ])
    def test_seer_claim_en(self, text):
        assert detect_role_claim(text) == "seer"

    # --- Seer negative patterns (denial/accusation, not a claim) ---
    @pytest.mark.parametrize("text", [
        "3号不是预言家，他是假的",
        "他是假预言家",
        "狼人悍跳预言家了",
        "Player 3 is not the seer",
        "That's a fake seer claim",
        "The werewolf claiming seer should be voted out",
    ])
    def test_seer_negative_not_detected(self, text):
        assert detect_role_claim(text) != "seer"

    # --- Hunter claims ---
    @pytest.mark.parametrize("text", [
        "我是猎人，别投我",
        "本猎人有枪",
        "I am the hunter, don't vote me",
        "I'm the hunter",
    ])
    def test_hunter_claim(self, text):
        assert detect_role_claim(text) == "hunter"

    # --- Guard claims ---
    @pytest.mark.parametrize("text", [
        "我是守卫，昨晚守了1号",
        "I am the guard",
        "I'm the guard, I protected player 1",
    ])
    def test_guard_claim(self, text):
        assert detect_role_claim(text) == "guard"

    # --- Witch claims ---
    @pytest.mark.parametrize("text", [
        "我是女巫，昨晚用了解药",
        "I am the witch, I used the antidote",
    ])
    def test_witch_claim(self, text):
        assert detect_role_claim(text) == "witch"

    # --- Villager claims ---
    @pytest.mark.parametrize("text", [
        "我是平民，没有技能",
        "我是村民",
        "I am a villager, I have no abilities",
    ])
    def test_villager_claim(self, text):
        assert detect_role_claim(text) == "villager"

    # --- No claim ---
    @pytest.mark.parametrize("text", [
        "我觉得3号很可疑",
        "投票给5号",
        "I think player 3 is suspicious",
        "Let's vote for player 5",
        "",
        "今天天气不错",
    ])
    def test_no_claim(self, text):
        assert detect_role_claim(text) is None

    # --- Case insensitivity ---
    def test_case_insensitive(self):
        assert detect_role_claim("I AM THE SEER") == "seer"
        assert detect_role_claim("i am the hunter") == "hunter"

    # --- Seer has priority over other roles ---
    def test_seer_priority(self):
        # If somehow both seer and hunter patterns match, seer should win
        # (seer is checked first in _ROLE_PATTERNS)
        text = "我是预言家也是猎人"  # nonsensical but tests priority
        assert detect_role_claim(text) == "seer"


class TestHasSeerClaim:
    """Tests for has_seer_claim()."""

    def test_empty_dict(self):
        assert has_seer_claim({}) is False

    def test_no_seer(self):
        claims = {1: "hunter", 2: "villager", 3: "guard"}
        assert has_seer_claim(claims) is False

    def test_seer_present(self):
        claims = {1: "hunter", 2: "seer", 3: "villager"}
        assert has_seer_claim(claims) is True

    def test_exclude_seat(self):
        claims = {2: "seer"}
        # Excluding the only seer should return False
        assert has_seer_claim(claims, exclude_seat=2) is False

    def test_exclude_seat_another_seer_exists(self):
        claims = {2: "seer", 5: "seer"}
        # Excluding seat 2, seat 5 still has seer claim
        assert has_seer_claim(claims, exclude_seat=2) is True

    def test_exclude_non_seer(self):
        claims = {1: "hunter", 3: "seer"}
        # Excluding a non-seer seat, seer still found
        assert has_seer_claim(claims, exclude_seat=1) is True

    def test_exclude_none(self):
        claims = {3: "seer"}
        assert has_seer_claim(claims, exclude_seat=None) is True
