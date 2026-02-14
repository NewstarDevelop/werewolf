"""In-memory storage backend for game state.

This is the default backend that preserves the current behavior:
games are stored in a Python dict with O(1) access.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.game import Game


class InMemoryBackend:
    """Dict-based in-memory game storage.

    This backend stores Game objects by reference, so mutations
    to the returned Game object are immediately visible without
    an explicit put() call. This matches the current GameStore behavior.

    For Redis or other serialized backends, callers must explicitly
    call put() after modifying a Game object.
    """

    def __init__(self) -> None:
        self._games: dict[str, "Game"] = {}

    def get(self, game_id: str) -> Optional["Game"]:
        return self._games.get(game_id)

    def put(self, game_id: str, game: "Game") -> None:
        self._games[game_id] = game

    def delete(self, game_id: str) -> bool:
        return self._games.pop(game_id, None) is not None

    def exists(self, game_id: str) -> bool:
        return game_id in self._games

    def count(self) -> int:
        return len(self._games)

    def all_ids(self) -> list[str]:
        return list(self._games.keys())
