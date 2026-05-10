import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.domain.enums import Role

TARGETED_INPUT_ACTION_TYPES = {
    "VOTE",
    "WOLF_KILL",
    "SEER_CHECK",
    "HUNTER_SHOOT",
    "WITCH_POISON",
}


@dataclass(slots=True, kw_only=True)
class Player:
    seat_id: int
    role: Role
    is_alive: bool = True

    def mark_dead(self) -> None:
        self.is_alive = False


@dataclass(slots=True, kw_only=True)
class HumanPlayer(Player):
    ws_connection: WebSocket | None = None
    pending_input: asyncio.Future[dict[str, Any]] | None = None
    pending_action_types: set[str] | None = None
    pending_allowed_targets: set[int] | None = None
    pending_request_id: str | None = None

    def begin_input(
        self,
        *,
        allowed_action_types: set[str] | None = None,
        allowed_targets: set[int] | None = None,
        request_id: str | None = None,
    ) -> asyncio.Future[dict[str, Any]]:
        if self.pending_input is not None and not self.pending_input.done():
            self.pending_input.cancel()
        loop = asyncio.get_running_loop()
        self.pending_input = loop.create_future()
        self.pending_action_types = allowed_action_types
        self.pending_allowed_targets = (
            set(allowed_targets) if allowed_targets is not None else None
        )
        self.pending_request_id = request_id
        return self.pending_input

    def resolve_input(self, payload: dict[str, Any]) -> bool:
        if self.pending_input is None or self.pending_input.done():
            return False
        if (
            self.pending_request_id is not None
            and payload.get("request_id") != self.pending_request_id
        ):
            return False
        action_type = payload.get("action_type")
        if (
            self.pending_action_types is not None
            and action_type not in self.pending_action_types
        ):
            return False
        if self.pending_allowed_targets is not None:
            target = payload.get("target")
            if action_type in TARGETED_INPUT_ACTION_TYPES:
                if not isinstance(target, int) or target not in self.pending_allowed_targets:
                    return False
            elif target is not None:
                return False
        self.pending_input.set_result(payload)
        return True

    def clear_input(self) -> None:
        self.pending_input = None
        self.pending_action_types = None
        self.pending_allowed_targets = None
        self.pending_request_id = None

    @property
    def is_human(self) -> bool:
        return True


@dataclass(slots=True, kw_only=True)
class AIPlayer(Player):
    personality: str
    private_memory: list[str] = field(default_factory=list)
    suspicion_scores: dict[int, int] = field(default_factory=dict)
    trust_scores: dict[int, int] = field(default_factory=dict)

    @property
    def is_human(self) -> bool:
        return False

    def remember(self, memory: str) -> None:
        self.private_memory.append(memory)

    def adjust_suspicion(self, seat_id: int, delta: int) -> None:
        if seat_id == self.seat_id:
            return
        self.suspicion_scores[seat_id] = max(
            0,
            self.suspicion_scores.get(seat_id, 0) + delta,
        )
        if self.suspicion_scores[seat_id] == 0:
            self.suspicion_scores.pop(seat_id, None)

    def adjust_trust(self, seat_id: int, delta: int) -> None:
        if seat_id == self.seat_id:
            return
        self.trust_scores[seat_id] = max(
            0,
            self.trust_scores.get(seat_id, 0) + delta,
        )
        if self.trust_scores[seat_id] == 0:
            self.trust_scores.pop(seat_id, None)

    def top_suspicions(self, *, limit: int = 3) -> list[tuple[int, int]]:
        return sorted(
            self.suspicion_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]

    def top_trusts(self, *, limit: int = 3) -> list[tuple[int, int]]:
        return sorted(
            self.trust_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
