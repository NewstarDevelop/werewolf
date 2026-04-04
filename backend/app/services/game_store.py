"""In-memory game store — V1 single-instance."""

from __future__ import annotations

from app.models.game import Game


class GameStore:
    """Singleton-like store for active games.

    V1: in-process dict, no distributed coordination.
    """

    _instance: GameStore | None = None

    def __init__(self) -> None:
        self._games: dict[int, Game] = {}

    @classmethod
    def get_instance(cls) -> GameStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add(self, game: Game) -> None:
        self._games[game.id] = game

    def get(self, game_id: int) -> Game | None:
        return self._games.get(game_id)

    def remove(self, game_id: int) -> Game | None:
        return self._games.pop(game_id, None)

    def list_active(self) -> list[Game]:
        return [g for g in self._games.values() if g.phase.value != "game_over"]

    def all_games(self) -> list[Game]:
        return list(self._games.values())
