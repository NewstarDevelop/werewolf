"""Unified LLM service — prompt construction, calling, retry, and fallback.

This is the single entry point for all AI decisions in the game.
It builds role-aware prompts, delegates to LLMClient, handles failures
with mock fallback, and parses structured outputs.
"""

from __future__ import annotations

import json
import logging

from app.models.game import Game, Player, Role, Phase
from app.services.llm.base import LLMClient
from app.services.llm.config import ProviderConfig, ProviderManager, provider_manager
from app.services.llm.mock import MockClient

logger = logging.getLogger(__name__)

# Maximum retries for LLM calls
_MAX_RETRIES = 2


class LLMService:
    """Unified service for all LLM-backed AI decisions.

    Usage:
        service = LLMService(provider_manager)
        config = provider_manager.resolve_config(player.ai_provider, player.ai_model, player.ai_config)
        speech = await service.generate_speech(game, player, config)
    """

    def __init__(self, manager: ProviderManager | None = None):
        self._manager = manager or provider_manager

    def _get_client(self, config: ProviderConfig) -> LLMClient:
        """Get or create an LLM client for the given config."""
        return self._manager.create_client(config)

    async def _call_with_fallback(
        self,
        messages: list[dict[str, str]],
        config: ProviderConfig,
        *,
        json_mode: bool = False,
    ) -> str | dict:
        """Call LLM with retry and mock fallback.

        Retries up to _MAX_RETRIES times on transient failures.
        Falls back to MockClient on persistent failures.
        """
        client = self._get_client(config)

        for attempt in range(_MAX_RETRIES + 1):
            try:
                if json_mode:
                    return await client.complete_json(messages)
                return await client.complete(messages)
            except Exception as e:
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    str(e),
                )
                if attempt == _MAX_RETRIES:
                    break

        # Fallback to mock
        logger.info("Falling back to mock client for provider=%s", config.provider)
        mock = MockClient()
        if json_mode:
            return await mock.complete_json(messages)
        return await mock.complete(messages)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_system_prompt(self, game: Game, player: Player) -> str:
        """Build a system prompt describing the game state from the player's perspective."""
        role_desc = {
            Role.WEREWOLF: "You are a Werewolf. You hunt villagers at night with your wolf teammates.",
            Role.WOLF_KING: "You are the Wolf King. You hunt with wolves at night. If you are voted out, you can take one player down.",
            Role.WHITE_WOLF_KING: "You are the White Wolf King. You hunt with wolves. You can self-destruct during day speech to take someone down.",
            Role.SEER: "You are the Seer. You can check one player each night to learn if they are a wolf.",
            Role.WITCH: "You are the Witch. You have one antidote (save) and one poison. Use them wisely.",
            Role.HUNTER: "You are the Hunter. If you die, you can shoot one player.",
            Role.GUARD: "You are the Guard. You protect one player each night from wolf attacks.",
            Role.VILLAGER: "You are a Villager. Find and vote out the wolves.",
        }
        role_text = role_desc.get(player.role, "You are a Villager.")

        # Player perspective
        perspective = game.get_player_perspective(player.seat)
        alive_count = len(game.alive_players())
        round_num = game.round_num
        phase = game.phase.value

        lines = [
            f"You are playing a Werewolf game. Round {round_num}, Phase: {phase}.",
            f"There are {alive_count} players alive.",
            role_text,
            f"Your seat number is {player.seat}, your nickname is {player.nickname}.",
        ]

        # Add perspective info
        if perspective.get("my_role"):
            lines.append(f"Your role: {perspective['my_role']}")

        # Wolf teammates
        if player.is_wolf:
            wolf_mates = [
                f"#{p['seat']} {p['nickname']}"
                for p in perspective.get("players", [])
                if p.get("role") in ("werewolf", "wolf_king", "white_wolf_king") and p["seat"] != player.seat
            ]
            if wolf_mates:
                lines.append(f"Your wolf teammates: {', '.join(wolf_mates)}")

        return "\n".join(lines)

    def _build_alive_players_text(self, game: Game, player: Player) -> str:
        """Build a text list of alive players (for target selection)."""
        players = []
        for p in game.alive_players():
            if p.seat == player.seat:
                continue
            tag = f"#{p.seat} {p.nickname}"
            if player.is_wolf and p.is_wolf:
                tag += " (teammate)"
            players.append(tag)
        return "Alive players: " + ", ".join(players) if players else "No other players alive."

    # ------------------------------------------------------------------
    # Public API: Game actions
    # ------------------------------------------------------------------

    async def generate_speech(self, game: Game, player: Player, config: ProviderConfig) -> str:
        """Generate a day speech for an AI player.

        Returns free-form text (the speech content).
        """
        system = self._build_system_prompt(game, player)
        alive_text = self._build_alive_players_text(game, player)

        messages = [
            {"role": "system", "content": f"{system}\n\n{alive_text}"},
            {"role": "user", "content": (
                "It's your turn to speak during the day discussion phase. "
                "Make a short, in-character speech (1-3 sentences). "
                "Stay in character — do not reveal your strategy directly. "
                "Do NOT use markdown or special formatting. "
                "Respond with ONLY your speech text, nothing else."
            )},
        ]

        result = await self._call_with_fallback(messages, config)
        if isinstance(result, dict):
            return result.get("speech", "I have nothing to say.")
        return str(result).strip()

    async def generate_night_action(self, game: Game, player: Player, config: ProviderConfig) -> dict:
        """Generate a night action for an AI player.

        Returns a dict matching the expected night action format:
        - Wolves: {"wolf_target": <seat>}
        - Seer: {"seer_target": <seat>}
        - Witch: {"witch_save": true} or {"witch_poison_target": <seat>} or {}
        - Guard: {"guard_target": <seat>}
        """
        system = self._build_system_prompt(game, player)
        alive_text = self._build_alive_players_text(game, player)

        role = player.role

        # Build role-specific instructions
        if role in (Role.WEREWOLF, Role.WOLF_KING, Role.WHITE_WOLF_KING):
            action_desc = (
                "It's night. Choose a non-wolf player to kill. "
                'Respond with JSON: {"wolf_target": <seat_number>}'
            )
        elif role == Role.SEER:
            action_desc = (
                "It's night. Choose a player to investigate. "
                'Respond with JSON: {"seer_target": <seat_number>}'
            )
        elif role == Role.WITCH:
            na = game.night_actions
            extra = ""
            if na.wolf_target is not None and player.has_antidote:
                extra = f" Player #{na.wolf_target} was attacked by wolves tonight."
            action_desc = (
                f"It's night. You are the Witch.{extra}\n"
                "You can save the attacked player, or poison another player, or do nothing.\n"
                'Respond with JSON: {"witch_save": true} or {"witch_poison_target": <seat_number>} or {}'
            )
        elif role == Role.GUARD:
            action_desc = (
                "It's night. Choose a player to protect from wolf attack.\n"
                "You cannot guard the same player two nights in a row.\n"
                'Respond with JSON: {"guard_target": <seat_number>}'
            )
        else:
            return {}

        messages = [
            {"role": "system", "content": f"{system}\n\n{alive_text}"},
            {"role": "user", "content": action_desc},
        ]

        result = await self._call_with_fallback(messages, config, json_mode=True)

        if not isinstance(result, dict) or "action" in result and result["action"] == "auto":
            # LLM returned "auto" — use rule-based fallback
            return self._fallback_night_action(game, player)

        return result

    async def generate_vote(self, game: Game, player: Player, config: ProviderConfig) -> int | None:
        """Generate a vote target for an AI player.

        Returns the seat number to vote for, or None.
        """
        system = self._build_system_prompt(game, player)
        alive_text = self._build_alive_players_text(game, player)

        messages = [
            {"role": "system", "content": f"{system}\n\n{alive_text}"},
            {"role": "user", "content": (
                "It's voting time. Choose one player to vote out. "
                'Respond with JSON: {"vote_target": <seat_number>}'
            )},
        ]

        result = await self._call_with_fallback(messages, config, json_mode=True)

        if isinstance(result, dict):
            target = result.get("vote_target") or result.get("target")
            if isinstance(target, int):
                # Validate target is alive and not self
                p = game.seat_map.get(target)
                if p and p.alive and p.seat != player.seat:
                    return target

        # Fallback
        return MockClient.fallback_vote(game, player)

    async def generate_hunter_shot(self, game: Game, player: Player, config: ProviderConfig) -> int | None:
        """Hunter AI decides who to shoot (or skip)."""
        system = self._build_system_prompt(game, player)
        alive_text = self._build_alive_players_text(game, player)

        messages = [
            {"role": "system", "content": f"{system}\n\n{alive_text}"},
            {"role": "user", "content": (
                "You just died as the Hunter. You can choose to shoot one player, or skip. "
                'Respond with JSON: {"action": "shoot", "target": <seat_number>} or {"action": "skip"}'
            )},
        ]

        result = await self._call_with_fallback(messages, config, json_mode=True)

        if isinstance(result, dict):
            if result.get("action") == "shoot":
                target = result.get("target")
                if isinstance(target, int):
                    p = game.seat_map.get(target)
                    if p and p.alive and p.seat != player.seat:
                        return target

        return MockClient.fallback_hunter_shot(game, player)

    async def generate_wolf_king_shot(self, game: Game, player: Player, config: ProviderConfig) -> int | None:
        """Wolf King AI decides who to shoot upon vote elimination."""
        system = self._build_system_prompt(game, player)
        alive_text = self._build_alive_players_text(game, player)

        messages = [
            {"role": "system", "content": f"{system}\n\n{alive_text}"},
            {"role": "user", "content": (
                "You are the Wolf King and you were just voted out. "
                "You can choose to shoot one player to take them down with you, or skip. "
                'Respond with JSON: {"action": "shoot", "target": <seat_number>} or {"action": "skip"}'
            )},
        ]

        result = await self._call_with_fallback(messages, config, json_mode=True)

        if isinstance(result, dict):
            if result.get("action") == "shoot":
                target = result.get("target")
                if isinstance(target, int):
                    p = game.seat_map.get(target)
                    if p and p.alive and p.seat != player.seat:
                        return target

        return MockClient.fallback_wolf_king_shot(game, player)

    async def should_white_wolf_king_self_destruct(
        self, game: Game, player: Player, config: ProviderConfig
    ) -> int | None:
        """White Wolf King AI decides whether to self-destruct during speech."""
        system = self._build_system_prompt(game, player)
        alive_text = self._build_alive_players_text(game, player)

        wolves = game.alive_wolves()
        total_alive = len(game.alive_players())
        wolf_ratio = len(wolves) / max(total_alive, 1)

        messages = [
            {"role": "system", "content": (
                f"{system}\n\n{alive_text}\n\n"
                f"Wolf team status: {len(wolves)} wolves out of {total_alive} alive players "
                f"({wolf_ratio:.0%})."
            )},
            {"role": "user", "content": (
                "You are the White Wolf King. It's the speech phase. "
                "You can self-destruct to take one player down (ending discussion). "
                "This is powerful but you also die. "
                "Should you self-destruct? If yes, choose a target.\n"
                'Respond with JSON: {"action": "self_destruct", "target": <seat_number>} or {"action": "wait"}'
            )},
        ]

        result = await self._call_with_fallback(messages, config, json_mode=True)

        if isinstance(result, dict):
            if result.get("action") == "self_destruct":
                target = result.get("target")
                if isinstance(target, int):
                    p = game.seat_map.get(target)
                    if p and p.alive and p.seat != player.seat and not p.is_wolf:
                        return target

        return MockClient.fallback_white_wolf_king_self_destruct(game, player)

    # ------------------------------------------------------------------
    # Fallback helpers
    # ------------------------------------------------------------------

    def _fallback_night_action(self, game: Game, player: Player) -> dict:
        """Rule-based fallback for night actions when LLM fails or returns auto."""
        role = player.role
        if role in (Role.WEREWOLF, Role.WOLF_KING, Role.WHITE_WOLF_KING):
            return MockClient.fallback_wolf_action(game, player)
        elif role == Role.SEER:
            return MockClient.fallback_seer_action(game, player)
        elif role == Role.WITCH:
            return MockClient.fallback_witch_action(game, player)
        elif role == Role.GUARD:
            return MockClient.fallback_guard_action(game, player)
        return {}


# Singleton
llm_service = LLMService()
