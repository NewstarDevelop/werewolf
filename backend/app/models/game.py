"""Game domain models — runtime aggregate (in-memory)."""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Role(str, enum.Enum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    GUARD = "guard"


class Faction(str, enum.Enum):
    WOLF = "wolf"
    VILLAGE = "village"


class Phase(str, enum.Enum):
    NIGHT = "night"
    DAWN = "dawn"            # announce night deaths
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"
    HUNTER_SHOT = "hunter_shot"
    GAME_OVER = "game_over"


ROLE_FACTION: dict[Role, Faction] = {
    Role.WEREWOLF: Faction.WOLF,
    Role.VILLAGER: Faction.VILLAGE,
    Role.SEER: Faction.VILLAGE,
    Role.WITCH: Faction.VILLAGE,
    Role.HUNTER: Faction.VILLAGE,
    Role.GUARD: Faction.VILLAGE,
}

# 9-player: 3 wolves, 3 villagers, seer, witch, hunter
ROLE_PRESETS: dict[str, list[Role]] = {
    "classic_9": [
        Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
        Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
        Role.SEER, Role.WITCH, Role.HUNTER,
    ],
    "classic_12": [
        Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
        Role.VILLAGER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
        Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD,
    ],
}

# Night action order: guard -> werewolf -> seer -> witch
NIGHT_ACTION_ORDER: list[Role] = [Role.GUARD, Role.WEREWOLF, Role.SEER, Role.WITCH]


# ---------------------------------------------------------------------------
# Player (runtime)
# ---------------------------------------------------------------------------

@dataclass
class Player:
    seat: int              # 0-indexed seat number
    user_id: int           # 0 for AI
    nickname: str
    role: Role | None = None
    is_ai: bool = False
    ai_provider: str | None = None
    alive: bool = True
    faction: Faction = Faction.VILLAGE

    # Per-game state
    has_antidote: bool = True   # witch
    has_poison: bool = True     # witch
    last_guarded_seat: int | None = None  # guard — cannot guard same person twice in a row

    @property
    def is_wolf(self) -> bool:
        return self.role == Role.WEREWOLF


# ---------------------------------------------------------------------------
# Night actions collected during a night phase
# ---------------------------------------------------------------------------

@dataclass
class NightActions:
    """Collected actions for a single night."""
    guard_target: int | None = None       # seat guarded by guard
    wolf_target: int | None = None        # seat targeted by wolves
    seer_target: int | None = None        # seat checked by seer
    seer_result: Faction | None = None    # result of seer check
    witch_save: bool = False              # witch uses antidote
    witch_poison_target: int | None = None  # witch uses poison on seat


# ---------------------------------------------------------------------------
# Game event log entry
# ---------------------------------------------------------------------------

@dataclass
class GameEvent:
    event_type: str       # "death", "speech", "vote", "hunter_shot", "phase_change", "role_reveal", "seer_result"
    phase: Phase
    round_num: int
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # visibility: None = public, set of seats = private
    visible_to: set[int] | None = None


# ---------------------------------------------------------------------------
# Game aggregate root
# ---------------------------------------------------------------------------

@dataclass
class Game:
    id: int
    room_id: int
    mode: str = "classic_9"
    players: list[Player] = field(default_factory=list)
    seat_map: dict[int, Player] = field(default_factory=dict)  # seat -> Player

    # Phase state
    phase: Phase = Phase.NIGHT
    round_num: int = 0
    winner: Faction | None = None

    # Night
    night_actions: NightActions = field(default_factory=NightActions)
    # Who still needs to act this night phase
    pending_night_actors: set[Role] = field(default_factory=set)

    # Day vote
    votes: dict[int, int] = field(default_factory=dict)  # voter_seat -> target_seat

    # Hunter
    hunter_pending: bool = False          # hunter needs to shoot

    # Event log
    events: list[GameEvent] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _rebuild_seat_map(self):
        self.seat_map = {p.seat: p for p in self.players}

    def assign_roles(self) -> None:
        """Shuffle and assign roles based on mode preset."""
        preset = ROLE_PRESETS.get(self.mode, ROLE_PRESETS["classic_9"])
        roles = list(preset)
        random.shuffle(roles)
        for player, role in zip(self.players, roles):
            player.role = role
            player.faction = ROLE_FACTION[role]
            # Reset witch / guard state
            if role == Role.WITCH:
                player.has_antidote = True
                player.has_poison = True
        self._rebuild_seat_map()

    @classmethod
    def from_room(cls, room_id: int, game_id: int, mode: str,
                  player_data: list[dict]) -> Game:
        """Create a Game from room player data.

        player_data: list of dicts with keys: seat, user_id, nickname, is_ai, ai_provider
        """
        players = []
        for pd in player_data:
            p = Player(
                seat=pd["seat"],
                user_id=pd["user_id"],
                nickname=pd.get("nickname", f"Player{pd['seat']}"),
                is_ai=pd.get("is_ai", False),
                ai_provider=pd.get("ai_provider"),
            )
            players.append(p)
        game = cls(id=game_id, room_id=room_id, mode=mode, players=players)
        game._rebuild_seat_map()
        return game

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the game: assign roles, enter first night."""
        self.assign_roles()
        self.round_num = 1
        self.phase = Phase.NIGHT
        self._begin_night()

    def _begin_night(self) -> None:
        """Set up a new night phase."""
        self.night_actions = NightActions()
        self.pending_night_actors = set()
        for role in NIGHT_ACTION_ORDER:
            # Only add if at least one alive player has this role
            if any(p.alive and p.role == role for p in self.players):
                self.pending_night_actors.add(role)
        self._add_event("phase_change", {"phase": "night", "round": self.round_num})

    # ------------------------------------------------------------------
    # Player queries
    # ------------------------------------------------------------------

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def alive_wolves(self) -> list[Player]:
        return [p for p in self.players if p.alive and p.is_wolf]

    def alive_villagers(self) -> list[Player]:
        return [p for p in self.players if p.alive and not p.is_wolf]

    def get_player_by_role(self, role: Role) -> Player | None:
        for p in self.players:
            if p.role == role:
                return p
        return None

    def get_player_by_seat(self, seat: int) -> Player | None:
        return self.seat_map.get(seat)

    def get_player_by_user(self, user_id: int) -> Player | None:
        for p in self.players:
            if p.user_id == user_id:
                return p
        return None

    # ------------------------------------------------------------------
    # Night actions
    # ------------------------------------------------------------------

    def submit_night_action(self, actor_role: Role, data: dict) -> None:
        """Submit a night action for a specific role.

        data keys vary by role:
          - guard: {"guard_target": int}
          - werewolf: {"wolf_target": int}
          - seer: {"seer_target": int}
          - witch: {"witch_save": bool, "witch_poison_target": int|None}
        """
        if actor_role not in self.pending_night_actors:
            raise ValueError(f"Role {actor_role.value} has no pending action or is not active")

        if actor_role == Role.GUARD:
            target = data["guard_target"]
            guard = self.get_player_by_role(Role.GUARD)
            assert guard is not None
            if target == guard.last_guarded_seat:
                raise ValueError("Cannot guard the same person two nights in a row")
            if not self.seat_map[target].alive:
                raise ValueError("Cannot guard a dead player")
            self.night_actions.guard_target = target

        elif actor_role == Role.WEREWOLF:
            target = data["wolf_target"]
            target_p = self.seat_map.get(target)
            if not target_p or not target_p.alive:
                raise ValueError("Invalid wolf target")
            if target_p.is_wolf:
                raise ValueError("Wolves cannot target another wolf")
            self.night_actions.wolf_target = target

        elif actor_role == Role.SEER:
            target = data["seer_target"]
            target_p = self.seat_map.get(target)
            if not target_p or not target_p.alive:
                raise ValueError("Invalid seer target")
            self.night_actions.seer_target = target
            self.night_actions.seer_result = target_p.faction

        elif actor_role == Role.WITCH:
            witch = self.get_player_by_role(Role.WITCH)
            assert witch is not None
            witch_save = data.get("witch_save", False)
            poison_target = data.get("witch_poison_target")

            if witch_save and not witch.has_antidote:
                raise ValueError("Antidote already used")
            if poison_target is not None and not witch.has_poison:
                raise ValueError("Poison already used")
            if witch_save and poison_target is not None:
                raise ValueError("Cannot use both antidote and poison in the same night")

            if witch_save:
                self.night_actions.witch_save = True
                witch.has_antidote = False
            if poison_target is not None:
                target_p = self.seat_map.get(poison_target)
                if not target_p or not target_p.alive:
                    raise ValueError("Invalid poison target")
                self.night_actions.witch_poison_target = poison_target
                witch.has_poison = False

        self.pending_night_actors.discard(actor_role)

    def night_complete(self) -> bool:
        """Check if all night actions have been submitted."""
        return len(self.pending_night_actors) == 0

    def resolve_night(self) -> list[GameEvent]:
        """Resolve all night actions, compute deaths, return events."""
        deaths: list[int] = []  # seats that die
        na = self.night_actions

        killed_by_wolf = na.wolf_target
        saved_by_guard = na.guard_target
        saved_by_witch = na.witch_save

        # Wolf kill
        if killed_by_wolf is not None:
            actually_killed = True
            if saved_by_guard == killed_by_wolf:
                actually_killed = False
            if saved_by_witch:
                actually_killed = False
            if actually_killed:
                deaths.append(killed_by_wolf)

        # Witch poison
        if na.witch_poison_target is not None:
            if na.witch_poison_target not in deaths:
                deaths.append(na.witch_poison_target)

        # Apply deaths
        events: list[GameEvent] = []
        for seat in deaths:
            p = self.seat_map[seat]
            p.alive = False
            events.append(GameEvent(
                event_type="death",
                phase=Phase.NIGHT,
                round_num=self.round_num,
                data={"seat": seat, "nickname": p.nickname, "cause": "night"},
            ))

        # Seer result (private)
        if na.seer_target is not None and na.seer_result is not None:
            seer = self.get_player_by_role(Role.SEER)
            if seer and seer.alive:
                events.append(GameEvent(
                    event_type="seer_result",
                    phase=Phase.NIGHT,
                    round_num=self.round_num,
                    data={"seat": na.seer_target, "result": na.seer_result.value},
                    visible_to={seer.seat},
                ))

        # Update guard last_guarded_seat
        guard = self.get_player_by_role(Role.GUARD)
        if guard:
            guard.last_guarded_seat = na.guard_target

        self.events.extend(events)
        self.phase = Phase.DAWN
        self._add_event("phase_change", {"phase": "dawn", "round": self.round_num})
        return events

    # ------------------------------------------------------------------
    # Day vote
    # ------------------------------------------------------------------

    def submit_vote(self, voter_seat: int, target_seat: int) -> None:
        """Submit a vote during day_vote phase."""
        if self.phase != Phase.DAY_VOTE:
            raise ValueError("Not in vote phase")
        voter = self.seat_map.get(voter_seat)
        if not voter or not voter.alive:
            raise ValueError("Voter is not alive")
        if voter_seat in self.votes:
            raise ValueError("Already voted")
        target = self.seat_map.get(target_seat)
        if not target or not target.alive:
            raise ValueError("Invalid vote target")

        self.votes[voter_seat] = target_seat
        self._add_event("vote", {"voter": voter_seat, "target": target_seat}, visible_to=set())

    def all_voted(self) -> bool:
        alive_seats = {p.seat for p in self.alive_players()}
        return alive_seats.issubset(self.votes.keys())

    def resolve_vote(self) -> list[GameEvent]:
        """Tally votes, eliminate the most-voted player, return events."""
        if not self.all_voted():
            raise ValueError("Not all players have voted")

        tally: dict[int, int] = {}
        for target_seat in self.votes.values():
            tally[target_seat] = tally.get(target_seat, 0) + 1

        max_votes = max(tally.values())
        top_seats = [s for s, v in tally.items() if v == max_votes]

        events: list[GameEvent] = []

        if len(top_seats) == 1:
            eliminated_seat = top_seats[0]
            p = self.seat_map[eliminated_seat]
            p.alive = False

            # Public vote result
            events.append(GameEvent(
                event_type="vote_result",
                phase=Phase.DAY_VOTE,
                round_num=self.round_num,
                data={"eliminated": eliminated_seat, "nickname": p.nickname, "tally": tally},
            ))
            events.append(GameEvent(
                event_type="death",
                phase=Phase.DAY_VOTE,
                round_num=self.round_num,
                data={"seat": eliminated_seat, "nickname": p.nickname, "cause": "vote"},
            ))

            # Hunter shoots on vote death
            if p.role == Role.HUNTER:
                self.hunter_pending = True
                events.append(GameEvent(
                    event_type="hunter_pending",
                    phase=Phase.DAY_VOTE,
                    round_num=self.round_num,
                    data={"seat": eliminated_seat},
                ))
        else:
            # Tie — no elimination
            events.append(GameEvent(
                event_type="vote_result",
                phase=Phase.DAY_VOTE,
                round_num=self.round_num,
                data={"tied": True, "tally": tally},
            ))

        self.events.extend(events)

        if self.hunter_pending:
            self.phase = Phase.HUNTER_SHOT
        else:
            self._advance_to_next_night_or_end()

        return events

    # ------------------------------------------------------------------
    # Hunter shot
    # ------------------------------------------------------------------

    def hunter_shoot(self, hunter_seat: int, target_seat: int) -> GameEvent:
        """Hunter shoots a player upon death."""
        hunter = self.seat_map.get(hunter_seat)
        if not hunter or hunter.role != Role.HUNTER:
            raise ValueError("Only hunter can shoot")
        if not self.hunter_pending:
            raise ValueError("Hunter is not pending a shot")
        target = self.seat_map.get(target_seat)
        if not target or not target.alive:
            raise ValueError("Invalid target")

        target.alive = False
        self.hunter_pending = False
        event = GameEvent(
            event_type="hunter_shot",
            phase=Phase.HUNTER_SHOT,
            round_num=self.round_num,
            data={"hunter": hunter_seat, "target": target_seat, "nickname": target.nickname},
        )
        self.events.append(event)
        self._advance_to_next_night_or_end()
        return event

    def skip_hunter_shot(self, hunter_seat: int) -> GameEvent:
        """Hunter chooses not to shoot."""
        hunter = self.seat_map.get(hunter_seat)
        if not hunter or hunter.role != Role.HUNTER:
            raise ValueError("Only hunter can skip")
        if not self.hunter_pending:
            raise ValueError("Hunter is not pending a shot")
        self.hunter_pending = False
        event = GameEvent(
            event_type="hunter_skip",
            phase=Phase.HUNTER_SHOT,
            round_num=self.round_num,
            data={"hunter": hunter_seat},
        )
        self.events.append(event)
        self._advance_to_next_night_or_end()
        return event

    # ------------------------------------------------------------------
    # Win condition check
    # ------------------------------------------------------------------

    def check_win(self) -> Faction | None:
        """Check if the game has a winner."""
        wolves = self.alive_wolves()
        villagers = self.alive_villagers()

        if len(wolves) == 0:
            return Faction.VILLAGE
        if len(villagers) <= len(wolves):
            return Faction.WOLF
        return None

    def _advance_to_next_night_or_end(self) -> None:
        """After day resolution, check win or start next night."""
        winner = self.check_win()
        if winner:
            self.winner = winner
            self.phase = Phase.GAME_OVER
            self.finished_at = datetime.now(timezone.utc).isoformat()
            self._add_event("game_over", {"winner": winner.value})
        else:
            self.round_num += 1
            self.phase = Phase.NIGHT
            self._begin_night()

    # ------------------------------------------------------------------
    # Day speech (simple — just record messages)
    # ------------------------------------------------------------------

    def add_speech(self, seat: int, content: str) -> GameEvent:
        """Record a player speech during day_speech phase."""
        if self.phase != Phase.DAY_SPEECH:
            raise ValueError("Not in speech phase")
        p = self.seat_map.get(seat)
        if not p or not p.alive:
            raise ValueError("Player not alive")
        event = GameEvent(
            event_type="speech",
            phase=Phase.DAY_SPEECH,
            round_num=self.round_num,
            data={"seat": seat, "nickname": p.nickname, "content": content},
        )
        self.events.append(event)
        return event

    # ------------------------------------------------------------------
    # Phase transitions (manual triggers for speech -> vote)
    # ------------------------------------------------------------------

    def start_vote(self) -> None:
        """Transition from day_speech to day_vote."""
        if self.phase != Phase.DAY_SPEECH:
            raise ValueError("Not in speech phase")
        self.phase = Phase.DAY_VOTE
        self.votes = {}
        self._add_event("phase_change", {"phase": "day_vote", "round": self.round_num})

    def start_speech(self) -> None:
        """Transition from dawn to day_speech."""
        if self.phase != Phase.DAWN:
            raise ValueError("Not in dawn phase")
        self.phase = Phase.DAY_SPEECH
        self._add_event("phase_change", {"phase": "day_speech", "round": self.round_num})

    # ------------------------------------------------------------------
    # Perspective — what each player can see
    # ------------------------------------------------------------------

    def get_player_perspective(self, viewer_seat: int) -> dict:
        """Generate a filtered view of the game for a specific player."""
        viewer = self.seat_map.get(viewer_seat)
        if not viewer:
            raise ValueError("Invalid seat")

        visible_events: list[dict] = []
        for e in self.events:
            if e.visible_to is None or viewer_seat in e.visible_to:
                visible_events.append({
                    "type": e.event_type,
                    "phase": e.phase.value,
                    "round": e.round_num,
                    "data": e.data,
                    "timestamp": e.timestamp,
                })

        players_view = []
        for p in self.players:
            info: dict[str, Any] = {
                "seat": p.seat,
                "nickname": p.nickname,
                "alive": p.alive,
                "is_ai": p.is_ai,
            }
            # Role visibility
            if p.seat == viewer_seat:
                info["role"] = p.role.value if p.role else None
            elif viewer.is_wolf and p.is_wolf:
                info["role"] = p.role.value  # wolves see each other
            players_view.append(info)

        return {
            "game_id": self.id,
            "room_id": self.room_id,
            "mode": self.mode,
            "phase": self.phase.value,
            "round": self.round_num,
            "winner": self.winner.value if self.winner else None,
            "my_seat": viewer_seat,
            "my_role": viewer.role.value if viewer.role else None,
            "players": players_view,
            "events": visible_events,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_event(self, event_type: str, data: dict[str, Any],
                   visible_to: set[int] | None = None) -> GameEvent:
        e = GameEvent(
            event_type=event_type,
            phase=self.phase,
            round_num=self.round_num,
            data=data,
            visible_to=visible_to,
        )
        self.events.append(e)
        return e

    # ------------------------------------------------------------------
    # Serialization (for snapshot / recovery)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize game state for snapshot storage."""
        return {
            "id": self.id,
            "room_id": self.room_id,
            "mode": self.mode,
            "phase": self.phase.value,
            "round_num": self.round_num,
            "winner": self.winner.value if self.winner else None,
            "hunter_pending": self.hunter_pending,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "players": [
                {
                    "seat": p.seat, "user_id": p.user_id, "nickname": p.nickname,
                    "role": p.role.value if p.role else None,
                    "is_ai": p.is_ai, "ai_provider": p.ai_provider,
                    "alive": p.alive, "faction": p.faction.value,
                    "has_antidote": p.has_antidote, "has_poison": p.has_poison,
                    "last_guarded_seat": p.last_guarded_seat,
                }
                for p in self.players
            ],
            "night_actions": {
                "guard_target": self.night_actions.guard_target,
                "wolf_target": self.night_actions.wolf_target,
                "seer_target": self.night_actions.seer_target,
                "seer_result": self.night_actions.seer_result.value if self.night_actions.seer_result else None,
                "witch_save": self.night_actions.witch_save,
                "witch_poison_target": self.night_actions.witch_poison_target,
            },
            "votes": dict(self.votes),
            "events": [
                {
                    "event_type": e.event_type, "phase": e.phase.value,
                    "round_num": e.round_num, "data": e.data,
                    "timestamp": e.timestamp,
                    "visible_to": list(e.visible_to) if e.visible_to else None,
                }
                for e in self.events
            ],
        }
