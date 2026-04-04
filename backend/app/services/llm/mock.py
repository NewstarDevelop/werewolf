"""Mock LLM client — returns predefined templates for testing and fallback."""

from __future__ import annotations

import json
import random

from app.models.game import Game, Player, Role
from app.services.llm.base import LLMClient


class MockClient(LLMClient):
    """Mock LLM client that returns rule-based responses.

    This preserves the original mock logic from ai_service.py,
    providing deterministic/random responses for all game actions
    without making any real API calls.
    """

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Return a mock text response based on the last user message."""
        last_msg = messages[-1]["content"] if messages else ""

        # Try to extract the action type from the system prompt
        for msg in messages:
            if msg.get("role") == "system":
                if "speech" in msg["content"].lower():
                    return self._mock_speech(messages)
                if "vote" in msg["content"].lower():
                    return self._mock_vote_text(messages)
                if "night action" in msg["content"].lower():
                    return self._mock_night_text(messages)

        return "I'm not sure what to say."

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict:
        """Return a mock JSON response based on the last user message."""
        for msg in messages:
            if msg.get("role") == "system":
                if "night action" in msg["content"].lower():
                    return self._mock_night_json(messages)
                if "vote" in msg["content"].lower():
                    return self._mock_vote_json(messages)
                if "hunter" in msg["content"].lower():
                    return self._mock_hunter_json(messages)
                if "wolf_king" in msg["content"].lower():
                    return self._mock_wolf_king_json(messages)

        return {"action": "skip"}

    # ------------------------------------------------------------------
    # Mock response generators (migrated from original ai_service.py)
    # ------------------------------------------------------------------

    def _mock_speech(self, messages: list[dict[str, str]]) -> str:
        templates = [
            "I think we should look carefully at everyone's behavior.",
            "I'm just a regular villager, let's find the wolves.",
            "Something feels off about a few people here.",
            "I didn't see anything suspicious last night.",
            "Let's focus on who's been too quiet.",
            "We need to be strategic about who we vote for.",
            "I think I know who the real threat is.",
            "Let's not be fooled by appearances.",
            "I have some information to share.",
            "I think I know who might be suspicious.",
            "We need to discuss before voting.",
            "I'm not sure who to trust.",
        ]
        return random.choice(templates)

    def _mock_vote_text(self, messages: list[dict[str, str]]) -> str:
        return "I vote based on the discussion."

    def _mock_night_text(self, messages: list[dict[str, str]]) -> str:
        return "I'll use my ability wisely."

    def _mock_night_json(self, messages: list[dict[str, str]]) -> dict:
        """Return a mock night action. The actual target selection
        is handled by the fallback logic in LLMService."""
        return {"action": "auto"}

    def _mock_vote_json(self, messages: list[dict[str, str]]) -> dict:
        return {"action": "auto"}

    def _mock_hunter_json(self, messages: list[dict[str, str]]) -> dict:
        if random.random() < 0.8:
            return {"action": "shoot"}
        return {"action": "skip"}

    def _mock_wolf_king_json(self, messages: list[dict[str, str]]) -> dict:
        if random.random() < 0.9:
            return {"action": "shoot"}
        return {"action": "skip"}

    # ------------------------------------------------------------------
    # Rule-based fallback helpers (kept from original ai_service.py)
    # These are used by LLMService when the LLM returns "auto" or fails.
    # ------------------------------------------------------------------

    @staticmethod
    def fallback_wolf_action(game: Game, player: Player) -> dict:
        """Wolves target a random alive non-wolf player."""
        targets = [p for p in game.alive_players() if not p.is_wolf]
        if not targets:
            return {}
        target = random.choice(targets)
        return {"wolf_target": target.seat}

    @staticmethod
    def fallback_seer_action(game: Game, player: Player) -> dict:
        """Seer checks a random alive player (not self)."""
        targets = [p for p in game.alive_players() if p.seat != player.seat]
        if not targets:
            return {}
        target = random.choice(targets)
        return {"seer_target": target.seat}

    @staticmethod
    def fallback_witch_action(game: Game, player: Player) -> dict:
        """Witch decides whether to save or poison."""
        action: dict = {}
        na = game.night_actions

        if na.wolf_target is not None and player.has_antidote:
            if random.random() < 0.7:
                action["witch_save"] = True
                return action

        if player.has_poison and random.random() < 0.3:
            targets = [p for p in game.alive_players() if p.seat != player.seat]
            if targets:
                target = random.choice(targets)
                action["witch_poison_target"] = target.seat

        return action

    @staticmethod
    def fallback_guard_action(game: Game, player: Player) -> dict:
        """Guard protects a random alive player (not same as last night)."""
        targets = [
            p for p in game.alive_players()
            if p.seat != player.last_guarded_seat
        ]
        if not targets:
            return {}
        target = random.choice(targets)
        return {"guard_target": target.seat}

    @staticmethod
    def fallback_vote(game: Game, player: Player) -> int | None:
        """Generate a random vote target."""
        alive = [p for p in game.alive_players() if p.seat != player.seat]
        if not alive:
            return None
        if player.is_wolf:
            non_wolves = [p for p in alive if not p.is_wolf]
            if non_wolves:
                return random.choice(non_wolves).seat
        return random.choice(alive).seat

    @staticmethod
    def fallback_hunter_shot(game: Game, player: Player) -> int | None:
        """Hunter AI decides who to shoot (or skip)."""
        if random.random() < 0.8:
            targets = [p for p in game.alive_players() if p.seat != player.seat]
            if targets:
                return random.choice(targets).seat
        return None

    @staticmethod
    def fallback_wolf_king_shot(game: Game, player: Player) -> int | None:
        """Wolf King AI decides who to shoot upon vote elimination."""
        if random.random() < 0.9:
            targets = [p for p in game.alive_players() if p.seat != player.seat]
            non_wolves = [p for p in targets if not p.is_wolf]
            if non_wolves:
                return random.choice(non_wolves).seat
            if targets:
                return random.choice(targets).seat
        return None

    @staticmethod
    def fallback_white_wolf_king_self_destruct(game: Game, player: Player) -> int | None:
        """White Wolf King AI decides whether to self-destruct during speech."""
        wolves = game.alive_wolves()
        total_alive = len(game.alive_players())
        if len(wolves) / max(total_alive, 1) < 0.4 and random.random() < 0.3:
            targets = [p for p in game.alive_players() if p.seat != player.seat and not p.is_wolf]
            if targets:
                priority = [p for p in targets if p.role in (Role.SEER, Role.WITCH, Role.HUNTER)]
                if priority:
                    return random.choice(priority).seat
                return random.choice(targets).seat
        return None
