import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.domain.enums import Role


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

    def begin_input(self) -> asyncio.Future[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        self.pending_input = loop.create_future()
        return self.pending_input

    def resolve_input(self, payload: dict[str, Any]) -> bool:
        if self.pending_input is None or self.pending_input.done():
            return False
        self.pending_input.set_result(payload)
        return True

    def clear_input(self) -> None:
        self.pending_input = None

    @property
    def is_human(self) -> bool:
        return True


@dataclass(slots=True, kw_only=True)
class AIPlayer(Player):
    personality: str
    private_memory: list[str] = field(default_factory=list)

    @property
    def is_human(self) -> bool:
        return False

    def remember(self, memory: str) -> None:
        self.private_memory.append(memory)
