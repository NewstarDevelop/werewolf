"""AI action service — generates actions for AI players using mock/simple logic."""

from __future__ import annotations

import random

from app.models.game import Game, Player, Role, Faction, Phase


class AIActionService:
    """Generates deterministic/simple actions for AI players.

    V1 uses rule-based mock logic. Will be replaced by LLM provider later.
    """

    def generate_night_action(self, game: Game, player: Player) -> dict:
        """Generate a night action for an AI player based on their role."""
        role = player.role
        if role is None:
            return {}

        if role == Role.WEREWOLF:
            return self._wolf_action(game, player)
        elif role == Role.SEER:
            return self._seer_action(game, player)
        elif role == Role.WITCH:
            return self._witch_action(game, player)
        elif role == Role.GUARD:
            return self._guard_action(game, player)
        return {}

    def _wolf_action(self, game: Game, player: Player) -> dict:
        """Wolves target a random alive non-wolf player."""
        targets = [p for p in game.alive_players() if not p.is_wolf]
        if not targets:
            return {}
        target = random.choice(targets)
        return {"wolf_target": target.seat}

    def _seer_action(self, game: Game, player: Player) -> dict:
        """Seer checks a random alive player (not self)."""
        targets = [p for p in game.alive_players() if p.seat != player.seat]
        if not targets:
            return {}
        target = random.choice(targets)
        return {"seer_target": target.seat}

    def _witch_action(self, game: Game, player: Player) -> dict:
        """Witch decides whether to save or poison."""
        action: dict = {}
        na = game.night_actions

        # Save: if someone was killed by wolf and witch has antidote
        if na.wolf_target is not None and player.has_antidote:
            # 70% chance to save
            if random.random() < 0.7:
                action["witch_save"] = True
                return action

        # Poison: random chance to poison someone (if have poison)
        if player.has_poison and random.random() < 0.3:
            targets = [p for p in game.alive_players() if p.seat != player.seat]
            if targets:
                target = random.choice(targets)
                action["witch_poison_target"] = target.seat

        return action

    def _guard_action(self, game: Game, player: Player) -> dict:
        """Guard protects a random alive player (not same as last night)."""
        targets = [
            p for p in game.alive_players()
            if p.seat != player.last_guarded_seat
        ]
        if not targets:
            return {}
        target = random.choice(targets)
        return {"guard_target": target.seat}

    def generate_speech(self, game: Game, player: Player) -> str:
        """Generate a speech message for an AI player."""
        role = player.role
        templates = {
            Role.WEREWOLF: [
                "I think we should look carefully at everyone's behavior.",
                "I'm just a regular villager, let's find the wolves.",
                "Something feels off about a few people here.",
                "I didn't see anything suspicious last night.",
                "Let's focus on who's been too quiet.",
            ],
            Role.SEER: [
                "I have some information to share.",
                "I think I know who might be suspicious.",
                "Based on what I've seen, we need to be careful.",
                "I've been paying close attention to everyone.",
            ],
            Role.WITCH: [
                "We need to think about who to protect.",
                "I've been watching the events carefully.",
                "Let's not rush to judgment.",
                "I think there's a pattern here.",
            ],
            Role.HUNTER: [
                "If anything happens to me, I'll take someone with me.",
                "I'm watching everyone closely.",
                "Let's be methodical about this.",
            ],
            Role.GUARD: [
                "I think we can trust a few people here.",
                "Let's work together to find the wolves.",
                "I've been protecting who I can.",
            ],
            Role.VILLAGER: [
                "I'm not sure who to trust.",
                "We need to discuss before voting.",
                "Let's hear from everyone first.",
                "I don't have much information to go on.",
                "Something about the voting pattern seems off.",
            ],
        }
        pool = templates.get(role, templates[Role.VILLAGER])
        return random.choice(pool)

    def generate_vote(self, game: Game, player: Player) -> int | None:
        """Generate a vote target for an AI player."""
        alive = [p for p in game.alive_players() if p.seat != player.seat]
        if not alive:
            return None

        if player.is_wolf:
            # Wolves vote for non-wolves
            non_wolves = [p for p in alive if not p.is_wolf]
            if non_wolves:
                return random.choice(non_wolves).seat

        # Non-wolves vote randomly
        return random.choice(alive).seat

    def generate_hunter_shot(self, game: Game, player: Player) -> int | None:
        """Hunter AI decides who to shoot (or skip)."""
        if player.role != Role.HUNTER:
            return None

        # 80% chance to shoot someone
        if random.random() < 0.8:
            targets = [p for p in game.alive_players() if p.seat != player.seat]
            if targets:
                return random.choice(targets).seat
        return None  # skip


# Singleton
ai_service = AIActionService()
