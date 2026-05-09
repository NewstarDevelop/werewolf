from collections.abc import Callable
from dataclasses import dataclass, field
import re
from typing import Literal

from app.domain.player import AIPlayer, Player

PublicMessageListener = Callable[[str], None]
PrivateMessageListener = Callable[[int, str], None]
ChatMessageKind = Literal["system", "speech"]
ATTACK_WORDS = (
    "质疑",
    "踩",
    "打",
    "怀疑",
    "查杀",
    "定狼",
    "归票",
    "抗推",
    "像狼",
    "狼面",
    "狼坑",
    "要出",
    "出",
)
SUPPORT_WORDS = ("保", "认好", "金水", "好人", "站边", "相信", "信你", "捞")
MENTION_BOUNDARIES = "，。；！？,.!?;：:"


def _classify_mention(message: str, seat_id: int) -> str:
    marker = f"{seat_id}号"
    marker_index = message.find(marker)
    if marker_index == -1:
        return "提及"

    boundary_start = max(
        message.rfind(boundary, 0, marker_index)
        for boundary in MENTION_BOUNDARIES
    )
    window_start = boundary_start + 1 if boundary_start >= 0 else 0
    boundary_ends = [
        boundary_index
        for boundary in MENTION_BOUNDARIES
        if (boundary_index := message.find(boundary, marker_index + len(marker))) != -1
    ]
    window_end = min(boundary_ends) if boundary_ends else len(message)
    mention_window = message[window_start:window_end]
    if len(mention_window) > 30:
        local_marker_index = marker_index - window_start
        mention_window = mention_window[
            max(0, local_marker_index - 12) : local_marker_index + len(marker) + 12
        ]
    attack_score = sum(word in mention_window for word in ATTACK_WORDS)
    support_score = sum(word in mention_window for word in SUPPORT_WORDS)
    if "不保" in mention_window:
        attack_score += 1
        support_score = max(0, support_score - 1)

    if attack_score > support_score:
        return "攻击/质疑"
    if support_score > 0:
        return "保护/认可"
    return "提及"


def _snippet(message: str, *, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", message).strip()
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


@dataclass(slots=True, kw_only=True)
class PublicChatEvent:
    message: str
    message_kind: ChatMessageKind = "system"
    event_type: str | None = None
    actor_seat: int | None = None
    target_seats: list[int] = field(default_factory=list)
    day_count: int = 1
    phase: str = "INIT"


@dataclass(slots=True, kw_only=True)
class PrivateChatEvent:
    seat_id: int
    message: str
    event_type: str | None = None
    target_seats: list[int] = field(default_factory=list)


PublicChatEventListener = Callable[[PublicChatEvent], None]
PrivateChatEventListener = Callable[[PrivateChatEvent], None]


@dataclass(slots=True, kw_only=True)
class VoteSnapshot:
    day_count: int = 1
    votes: dict[int, int] = field(default_factory=dict)
    ballots: dict[int, int] = field(default_factory=dict)
    abstentions: list[int] = field(default_factory=list)
    banished_seat: int | None = None
    summary: str = ""


@dataclass(slots=True, kw_only=True)
class NightActionSnapshot:
    day_count: int = 1
    wolf_target: int | None = None
    seer_seat: int | None = None
    seer_target: int | None = None
    seer_result: Literal["GOOD", "WOLF"] | None = None
    witch_seat: int | None = None
    witch_save_target: int | None = None
    witch_poison_target: int | None = None
    dead_seats: list[int] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class GameContext:
    day_count: int = 1
    phase: str = "INIT"
    players: dict[int, Player] = field(default_factory=dict)
    public_chat_history: list[str] = field(default_factory=list)
    killed_tonight: list[int] = field(default_factory=list)
    night_death_causes: dict[int, set[str]] = field(default_factory=dict)
    private_logs: dict[int, list[str]] = field(default_factory=dict)
    public_chat_events: list[PublicChatEvent] = field(default_factory=list)
    last_vote_result: VoteSnapshot | None = None
    vote_history: list[VoteSnapshot] = field(default_factory=list)
    night_actions: list[NightActionSnapshot] = field(default_factory=list)
    public_message_listeners: list[PublicMessageListener] = field(default_factory=list)
    public_chat_event_listeners: list[PublicChatEventListener] = field(default_factory=list)
    private_message_listeners: list[PrivateMessageListener] = field(default_factory=list)
    private_chat_event_listeners: list[PrivateChatEventListener] = field(default_factory=list)

    def add_player(self, player: Player) -> None:
        self.players[player.seat_id] = player
        self.private_logs.setdefault(player.seat_id, [])

    def add_public_message(
        self,
        message: str,
        *,
        message_kind: ChatMessageKind = "system",
        event_type: str | None = None,
        actor_seat: int | None = None,
        target_seats: list[int] | None = None,
    ) -> None:
        self.public_chat_history.append(message)
        for listener in self.public_message_listeners:
            listener(message)
        event = PublicChatEvent(
            message=message,
            message_kind=message_kind,
            event_type=event_type,
            actor_seat=actor_seat,
            target_seats=list(target_seats or []),
            day_count=self.day_count,
            phase=self.phase,
        )
        self.public_chat_events.append(event)
        for listener in self.public_chat_event_listeners:
            listener(event)
        if message_kind == "speech" and actor_seat is not None:
            self._remember_public_speech_interactions(event)

    def add_private_message(
        self,
        seat_id: int,
        message: str,
        *,
        event_type: str | None = None,
        target_seats: list[int] | None = None,
    ) -> None:
        private_log = self.private_logs.setdefault(seat_id, [])
        private_log.append(message)
        for listener in self.private_message_listeners:
            listener(seat_id, message)
        event = PrivateChatEvent(
            seat_id=seat_id,
            message=message,
            event_type=event_type,
            target_seats=list(target_seats or []),
        )
        for listener in self.private_chat_event_listeners:
            listener(event)

        player = self.players.get(seat_id)
        if isinstance(player, AIPlayer):
            player.remember(message)

    def _remember_public_speech_interactions(self, event: PublicChatEvent) -> None:
        for seat_id, player in sorted(self.players.items()):
            if not isinstance(player, AIPlayer):
                continue
            if seat_id == event.actor_seat:
                continue
            if f"{seat_id}号" not in event.message:
                continue
            relation = _classify_mention(event.message, seat_id)
            player.remember(
                f"{event.actor_seat}号在公开发言中{relation}你：{_snippet(event.message)}"
            )

    def on_public_message(self, listener: PublicMessageListener) -> None:
        self.public_message_listeners.append(listener)

    def on_public_chat_event(self, listener: PublicChatEventListener) -> None:
        self.public_chat_event_listeners.append(listener)

    def on_private_message(self, listener: PrivateMessageListener) -> None:
        self.private_message_listeners.append(listener)

    def on_private_chat_event(self, listener: PrivateChatEventListener) -> None:
        self.private_chat_event_listeners.append(listener)

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
