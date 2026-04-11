from dataclasses import dataclass, field

from app.domain.player import AIPlayer, Player


@dataclass(slots=True, kw_only=True)
class GameContext:
    day_count: int = 1
    phase: str = "INIT"
    players: dict[int, Player] = field(default_factory=dict)
    public_chat_history: list[str] = field(default_factory=list)
    killed_tonight: list[int] = field(default_factory=list)
    night_death_causes: dict[int, set[str]] = field(default_factory=dict)
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

    def mark_killed_tonight(self, seat_id: int, *, cause: str) -> None:
        if seat_id not in self.killed_tonight:
            self.killed_tonight.append(seat_id)
        causes = self.night_death_causes.setdefault(seat_id, set())
        causes.add(cause)

    def clear_night_deaths(self) -> None:
        self.killed_tonight.clear()
        self.night_death_causes.clear()

    def death_causes_for(self, seat_id: int) -> set[str]:
        return set(self.night_death_causes.get(seat_id, set()))

    def get_private_log(self, seat_id: int) -> list[str]:
        return list(self.private_logs.get(seat_id, []))
