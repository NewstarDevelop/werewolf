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
