"""Storage backend protocol for game state.

Defines the abstract interface that all storage backends must implement.
This enables swapping between in-memory, Redis, or other backends
without changing the GameStore facade.
"""

from typing import Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.game import Game


class GameStoreBackend(Protocol):
    """Protocol defining the storage backend interface for game state.

    Implementations:
    - InMemoryBackend: Dict-based storage (default, current behavior)
    - RedisBackend: Redis-backed storage (future, for multi-instance)
    """

    def get(self, game_id: str) -> Optional["Game"]:
        """Retrieve a game by ID. Returns None if not found."""
        ...

    def put(self, game_id: str, game: "Game") -> None:
        """Store or update a game."""
        ...

    def delete(self, game_id: str) -> bool:
        """Delete a game. Returns True if the game existed."""
        ...

    def exists(self, game_id: str) -> bool:
        """Check if a game exists."""
        ...

    def count(self) -> int:
        """Return the number of stored games."""
        ...

    def all_ids(self) -> list[str]:
        """Return all stored game IDs."""
        ...
