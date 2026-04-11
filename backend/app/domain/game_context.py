from dataclasses import dataclass, field

from app.domain.player import AIPlayer, Player


@dataclass(slots=True, kw_only=True)
class GameContext:
    day_count: int = 1
    phase: str = "INIT"
    players: dict[int, Player] = field(default_factory=dict)
    public_chat_history: list[str] = field(default_factory=list)
    killed_tonight: list[int] = field(default_factory=list)
    private_logs: dict[int, list[str]] = field(default_factory=dict)

    def add_player(self, player: Player) -> None:
        self.players[player.seat_id] = player
        self.private_logs.setdefault(player.seat_id, [])

    def add_public_message(self, message: str) -> None:
        self.public_chat_history.append(message)

    def add_private_message(self, seat_id: int, message: str) -> None:
        private_log = self.private_logs.setdefault(seat_id, [])
        private_log.append(message)

        player = self.players.get(seat_id)
        if isinstance(player, AIPlayer):
            player.remember(message)

    def alive_seat_ids(self) -> list[int]:
        return [
            seat_id
            for seat_id, player in sorted(self.players.items())
            if player.is_alive
        ]

    def mark_killed_tonight(self, seat_id: int) -> None:
        if seat_id not in self.killed_tonight:
            self.killed_tonight.append(seat_id)

    def get_private_log(self, seat_id: int) -> list[str]:
        return list(self.private_logs.get(seat_id, []))
