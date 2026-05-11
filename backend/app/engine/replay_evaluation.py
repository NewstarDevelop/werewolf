from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
import random

from app.domain.enums import Role
from app.domain.game_context import GameContext, NightActionSnapshot, PublicChatEvent, VoteSnapshot
from app.engine.check_win import check_win
from app.engine.game_engine import GameEngine
from app.engine.states.phase import GamePhase

DEFAULT_REPLAY_SEED_COUNT = 20
DEFAULT_REPLAY_MAX_ROUNDS = 20
CAPPED_GAME_SUMMARY = "夜尽未分胜负，本局暂止。"
PRIVATE_LEAK_MARKERS = (
    "private_log",
    "known_role",
    "private_memory",
    "suspicion_scores",
    "trust_scores",
    "inner_thought",
)


@dataclass(slots=True, kw_only=True)
class ReplayEvaluationIssue:
    code: str
    message: str
    day_count: int | None = None


@dataclass(slots=True, kw_only=True)
class ReplayEvaluationResult:
    seed: int
    issues: list[ReplayEvaluationIssue] = field(default_factory=list)
    outcome: str = "UNKNOWN"
    final_summary: str = ""
    day_count: int = 1
    rounds_recorded: int = 0
    context: GameContext | None = field(default=None, repr=False)

    @property
    def passed(self) -> bool:
        return not self.issues


@dataclass(slots=True, kw_only=True)
class ReplayEvaluationSummary:
    results: list[ReplayEvaluationResult]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def passed_count(self) -> int:
        return sum(result.passed for result in self.results)

    @property
    def failed_count(self) -> int:
        return len(self.results) - self.passed_count


def default_replay_seeds(
    *,
    count: int = DEFAULT_REPLAY_SEED_COUNT,
    start_seed: int = 1,
) -> list[int]:
    if count < 1:
        raise ValueError("seed count must be at least 1")
    return list(range(start_seed, start_seed + count))


async def evaluate_replay_seed(
    seed: int,
    *,
    max_rounds: int = DEFAULT_REPLAY_MAX_ROUNDS,
) -> ReplayEvaluationResult:
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")

    try:
        engine = GameEngine(rng=random.Random(seed), llm_client=None)
        context = await engine.run_loop(max_rounds=max_rounds)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        return ReplayEvaluationResult(
            seed=seed,
            issues=[
                ReplayEvaluationIssue(
                    code="ENGINE_EXCEPTION",
                    message=f"engine raised {type(exc).__name__}: {exc}",
                )
            ],
            outcome="INVALID",
        )

    issues = validate_replay_context(context)
    final_summary = _final_game_summary(context)
    return ReplayEvaluationResult(
        seed=seed,
        issues=issues,
        outcome=_classify_outcome(context, final_summary),
        final_summary=final_summary,
        day_count=context.day_count,
        rounds_recorded=len(context.night_actions),
        context=context,
    )


async def evaluate_replay_seeds(
    seeds: Iterable[int],
    *,
    max_rounds: int = DEFAULT_REPLAY_MAX_ROUNDS,
) -> ReplayEvaluationSummary:
    results = []
    for seed in seeds:
        results.append(await evaluate_replay_seed(seed, max_rounds=max_rounds))
    return ReplayEvaluationSummary(results=results)


def evaluate_replay_seeds_sync(
    seeds: Iterable[int],
    *,
    max_rounds: int = DEFAULT_REPLAY_MAX_ROUNDS,
) -> ReplayEvaluationSummary:
    return asyncio.run(evaluate_replay_seeds(seeds, max_rounds=max_rounds))


def validate_replay_context(context: GameContext) -> list[ReplayEvaluationIssue]:
    issues: list[ReplayEvaluationIssue] = []
    _validate_terminal_state(context, issues)
    _validate_reconstructed_timeline(context, issues)
    _validate_private_information(context, issues)
    return issues


def _add_issue(
    issues: list[ReplayEvaluationIssue],
    code: str,
    message: str,
    *,
    day_count: int | None = None,
) -> None:
    issues.append(
        ReplayEvaluationIssue(
            code=code,
            message=message,
            day_count=day_count,
        )
    )


def _final_game_summary(context: GameContext) -> str:
    for event in reversed(context.public_chat_events):
        if event.event_type == "GAME_OVER_SUMMARY":
            return event.message
    return context.public_chat_history[-1] if context.public_chat_history else ""


def _classify_outcome(context: GameContext, final_summary: str) -> str:
    if final_summary == CAPPED_GAME_SUMMARY:
        return "CAPPED"
    winner = check_win(context)
    if winner is not None:
        return winner["winning_side"]
    return "UNKNOWN"


def _validate_terminal_state(
    context: GameContext,
    issues: list[ReplayEvaluationIssue],
) -> None:
    if context.phase != GamePhase.GAME_OVER.value:
        _add_issue(
            issues,
            "NOT_GAME_OVER",
            f"final phase is {context.phase}, expected GAME_OVER",
        )

    final_summary = _final_game_summary(context)
    if not final_summary:
        _add_issue(issues, "MISSING_GAME_OVER_SUMMARY", "no game-over summary was recorded")
        return

    winner = check_win(context)
    if final_summary == CAPPED_GAME_SUMMARY:
        if winner is not None:
            _add_issue(
                issues,
                "CAPPED_WITH_WINNER",
                "game was capped even though a side has already won",
            )
        return

    if winner is None:
        _add_issue(
            issues,
            "SUMMARY_WITHOUT_WINNER",
            f"final summary is not capped but no side has won: {final_summary}",
        )
        return

    if final_summary != winner["summary"]:
        _add_issue(
            issues,
            "WIN_SUMMARY_MISMATCH",
            f"final summary {final_summary!r} does not match {winner['summary']!r}",
        )


def _validate_reconstructed_timeline(
    context: GameContext,
    issues: list[ReplayEvaluationIssue],
) -> None:
    if not context.players:
        _add_issue(issues, "NO_PLAYERS", "context contains no players")
        return

    alive_seats = set(context.players)
    nights_by_day = _snapshots_by_day(context.night_actions, issues)
    votes_by_day = _snapshots_by_day(context.vote_history, issues)
    events_by_day = _events_by_day(context.public_chat_events)
    vote_days_seen: set[int] = set()

    for day_count in sorted(set(nights_by_day) | set(votes_by_day) | set(events_by_day)):
        night = nights_by_day.get(day_count)
        if night is not None:
            _validate_night_snapshot(context, night, alive_seats, issues)
            for dead_seat in night.dead_seats:
                if dead_seat in alive_seats:
                    alive_seats.remove(dead_seat)

        for event in events_by_day.get(day_count, []):
            if event.event_type in {"BANISHMENT", "VOTE_NO_BANISHMENT"}:
                vote = votes_by_day.get(day_count)
                if vote is None:
                    _add_issue(
                        issues,
                        "MISSING_VOTE_SNAPSHOT",
                        f"{event.event_type} event has no vote snapshot",
                        day_count=day_count,
                    )
                    continue
                vote_days_seen.add(day_count)
                _validate_vote_snapshot(context, vote, alive_seats, event, issues)
                if vote.banished_seat is not None and vote.banished_seat in alive_seats:
                    alive_seats.remove(vote.banished_seat)
                continue

            if event.event_type in {"HUNTER_SHOT", "HUNTER_POISONED", "HUNTER_NO_TARGET"}:
                _validate_hunter_event(context, event, alive_seats, issues)
                if event.event_type == "HUNTER_SHOT" and event.target_seats:
                    alive_seats.discard(event.target_seats[0])

    for day_count, vote in votes_by_day.items():
        if day_count not in vote_days_seen:
            _add_issue(
                issues,
                "ORPHAN_VOTE_SNAPSHOT",
                f"vote snapshot exists without a vote event: {vote.summary}",
                day_count=day_count,
            )

    final_alive = {seat_id for seat_id, player in context.players.items() if player.is_alive}
    if alive_seats != final_alive:
        _add_issue(
            issues,
            "FINAL_ALIVE_MISMATCH",
            f"reconstructed alive seats {sorted(alive_seats)} != final alive seats {sorted(final_alive)}",
        )


def _snapshots_by_day(
    snapshots: Iterable[NightActionSnapshot | VoteSnapshot],
    issues: list[ReplayEvaluationIssue],
) -> dict[int, NightActionSnapshot | VoteSnapshot]:
    by_day: dict[int, NightActionSnapshot | VoteSnapshot] = {}
    for snapshot in snapshots:
        if snapshot.day_count in by_day:
            _add_issue(
                issues,
                "DUPLICATE_DAY_SNAPSHOT",
                f"duplicate snapshot for day {snapshot.day_count}",
                day_count=snapshot.day_count,
            )
        by_day[snapshot.day_count] = snapshot
    return by_day


def _events_by_day(events: Iterable[PublicChatEvent]) -> dict[int, list[PublicChatEvent]]:
    by_day: dict[int, list[PublicChatEvent]] = {}
    for event in events:
        by_day.setdefault(event.day_count, []).append(event)
    return by_day


def _validate_night_snapshot(
    context: GameContext,
    night: NightActionSnapshot,
    alive_seats: set[int],
    issues: list[ReplayEvaluationIssue],
) -> None:
    if night.wolf_target is None:
        _add_issue(issues, "MISSING_WOLF_TARGET", "night has no wolf target", day_count=night.day_count)
    elif night.wolf_target not in alive_seats:
        _add_issue(
            issues,
            "INVALID_WOLF_TARGET",
            f"wolf target {night.wolf_target} was not alive",
            day_count=night.day_count,
        )

    if night.seer_seat is not None:
        _validate_role_actor(
            context,
            night.seer_seat,
            Role.SEER,
            alive_seats,
            issues,
            code="INVALID_SEER_ACTOR",
            day_count=night.day_count,
        )
        if night.seer_target is None:
            _add_issue(issues, "MISSING_SEER_TARGET", "seer acted without target", day_count=night.day_count)
        elif night.seer_target not in alive_seats or night.seer_target == night.seer_seat:
            _add_issue(
                issues,
                "INVALID_SEER_TARGET",
                f"seer target {night.seer_target} was illegal for seer {night.seer_seat}",
                day_count=night.day_count,
            )

    if night.witch_seat is not None:
        _validate_role_actor(
            context,
            night.witch_seat,
            Role.WITCH,
            alive_seats,
            issues,
            code="INVALID_WITCH_ACTOR",
            day_count=night.day_count,
        )

    if night.witch_save_target is not None and night.witch_poison_target is not None:
        _add_issue(
            issues,
            "WITCH_DOUBLE_ACTION",
            "witch used antidote and poison in the same night",
            day_count=night.day_count,
        )

    if night.witch_save_target is not None:
        if night.witch_save_target != night.wolf_target:
            _add_issue(
                issues,
                "INVALID_WITCH_SAVE_TARGET",
                f"witch saved {night.witch_save_target}, expected wolf target {night.wolf_target}",
                day_count=night.day_count,
            )
        if night.witch_save_target == night.witch_seat:
            _add_issue(
                issues,
                "WITCH_SELF_SAVE",
                "witch saved self, which is disallowed by project rules",
                day_count=night.day_count,
            )

    if night.witch_poison_target is not None:
        if night.witch_poison_target not in alive_seats:
            _add_issue(
                issues,
                "INVALID_WITCH_POISON_TARGET",
                f"witch poison target {night.witch_poison_target} was not alive",
                day_count=night.day_count,
            )
        if night.witch_poison_target == night.witch_seat:
            _add_issue(
                issues,
                "WITCH_SELF_POISON",
                "witch poisoned self",
                day_count=night.day_count,
            )
        if night.witch_poison_target == night.wolf_target:
            _add_issue(
                issues,
                "WITCH_POISONED_WOLF_TARGET",
                "witch poisoned the same target already killed by wolves",
                day_count=night.day_count,
            )

    expected_dead = set[int]()
    if night.wolf_target is not None and night.wolf_target != night.witch_save_target:
        expected_dead.add(night.wolf_target)
    if night.witch_poison_target is not None:
        expected_dead.add(night.witch_poison_target)
    if set(night.dead_seats) != expected_dead:
        _add_issue(
            issues,
            "NIGHT_DEATH_MISMATCH",
            f"night deaths {sorted(night.dead_seats)} != expected {sorted(expected_dead)}",
            day_count=night.day_count,
        )

    for dead_seat in night.dead_seats:
        if dead_seat not in context.players:
            _add_issue(
                issues,
                "UNKNOWN_NIGHT_DEATH",
                f"night death references unknown seat {dead_seat}",
                day_count=night.day_count,
            )
        elif dead_seat not in alive_seats:
            _add_issue(
                issues,
                "REPEATED_NIGHT_DEATH",
                f"night death references already dead seat {dead_seat}",
                day_count=night.day_count,
            )


def _validate_role_actor(
    context: GameContext,
    seat_id: int,
    role: Role,
    alive_seats: set[int],
    issues: list[ReplayEvaluationIssue],
    *,
    code: str,
    day_count: int,
) -> None:
    player = context.players.get(seat_id)
    if player is None:
        _add_issue(issues, code, f"actor {seat_id} does not exist", day_count=day_count)
        return
    if player.role is not role:
        _add_issue(
            issues,
            code,
            f"actor {seat_id} has role {player.role.value}, expected {role.value}",
            day_count=day_count,
        )
    if seat_id not in alive_seats:
        _add_issue(issues, code, f"actor {seat_id} was not alive", day_count=day_count)


def _validate_vote_snapshot(
    context: GameContext,
    vote: VoteSnapshot,
    alive_seats: set[int],
    event: PublicChatEvent,
    issues: list[ReplayEvaluationIssue],
) -> None:
    voters = set(vote.ballots) | set(vote.abstentions)
    if voters != alive_seats:
        _add_issue(
            issues,
            "VOTE_VOTER_SET_MISMATCH",
            f"voters {sorted(voters)} != alive seats {sorted(alive_seats)}",
            day_count=vote.day_count,
        )

    for voter, target in sorted(vote.ballots.items()):
        if voter not in alive_seats:
            _add_issue(
                issues,
                "VOTE_FROM_DEAD_PLAYER",
                f"dead or missing voter {voter} cast a ballot",
                day_count=vote.day_count,
            )
        if target not in alive_seats:
            _add_issue(
                issues,
                "VOTE_TARGET_NOT_ALIVE",
                f"voter {voter} targeted non-alive seat {target}",
                day_count=vote.day_count,
            )
        if target == voter:
            _add_issue(
                issues,
                "VOTE_SELF_TARGET",
                f"voter {voter} targeted self",
                day_count=vote.day_count,
            )

    invalid_abstainers = sorted(set(vote.abstentions) - alive_seats)
    if invalid_abstainers:
        _add_issue(
            issues,
            "INVALID_ABSTAINERS",
            f"abstainers were not alive: {invalid_abstainers}",
            day_count=vote.day_count,
        )

    tally: dict[int, int] = {}
    for target in vote.ballots.values():
        tally[target] = tally.get(target, 0) + 1
    if tally != vote.votes:
        _add_issue(
            issues,
            "VOTE_TALLY_MISMATCH",
            f"stored tally {vote.votes} != recomputed {tally}",
            day_count=vote.day_count,
        )

    expected_banishment = _expected_banishment(tally)
    if vote.banished_seat != expected_banishment:
        _add_issue(
            issues,
            "BANISHMENT_MISMATCH",
            f"banished {vote.banished_seat} != expected {expected_banishment}",
            day_count=vote.day_count,
        )

    event_target = event.target_seats[0] if event.target_seats else None
    if event.event_type == "BANISHMENT" and event_target != vote.banished_seat:
        _add_issue(
            issues,
            "BANISHMENT_EVENT_MISMATCH",
            f"event target {event_target} != vote banished {vote.banished_seat}",
            day_count=vote.day_count,
        )
    if event.event_type == "VOTE_NO_BANISHMENT" and vote.banished_seat is not None:
        _add_issue(
            issues,
            "NO_BANISHMENT_EVENT_MISMATCH",
            f"no-banishment event had banished seat {vote.banished_seat}",
            day_count=vote.day_count,
        )

    if vote.banished_seat is not None:
        player = context.players.get(vote.banished_seat)
        if player is None:
            _add_issue(
                issues,
                "BANISHED_UNKNOWN_SEAT",
                f"banished unknown seat {vote.banished_seat}",
                day_count=vote.day_count,
            )


def _expected_banishment(tally: dict[int, int]) -> int | None:
    if not tally:
        return None
    highest_votes = max(tally.values())
    winners = [seat_id for seat_id, count in sorted(tally.items()) if count == highest_votes]
    return winners[0] if len(winners) == 1 else None


def _validate_hunter_event(
    context: GameContext,
    event: PublicChatEvent,
    alive_seats: set[int],
    issues: list[ReplayEvaluationIssue],
) -> None:
    hunter_seat = event.actor_seat
    if hunter_seat is None or hunter_seat not in context.players:
        _add_issue(
            issues,
            "HUNTER_EVENT_WITHOUT_ACTOR",
            "hunter event is missing a valid actor",
            day_count=event.day_count,
        )
        return

    hunter = context.players[hunter_seat]
    if hunter.role is not Role.HUNTER:
        _add_issue(
            issues,
            "HUNTER_EVENT_NON_HUNTER",
            f"actor {hunter_seat} is {hunter.role.value}, expected HUNTER",
            day_count=event.day_count,
        )
    if hunter_seat in alive_seats:
        _add_issue(
            issues,
            "HUNTER_EVENT_ALIVE_HUNTER",
            f"hunter {hunter_seat} was still alive during {event.event_type}",
            day_count=event.day_count,
        )

    if event.event_type != "HUNTER_SHOT":
        if event.target_seats:
            _add_issue(
                issues,
                "HUNTER_NON_SHOT_HAS_TARGET",
                f"{event.event_type} should not include targets {event.target_seats}",
                day_count=event.day_count,
            )
        return

    if len(event.target_seats) != 1:
        _add_issue(
            issues,
            "HUNTER_SHOT_TARGET_COUNT",
            f"hunter shot target count is {len(event.target_seats)}",
            day_count=event.day_count,
        )
        return

    target = event.target_seats[0]
    if target == hunter_seat:
        _add_issue(
            issues,
            "HUNTER_SHOT_SELF",
            "hunter shot self",
            day_count=event.day_count,
        )
    if target not in alive_seats:
        _add_issue(
            issues,
            "HUNTER_SHOT_TARGET_NOT_ALIVE",
            f"hunter shot target {target} was not alive",
            day_count=event.day_count,
        )


def _validate_private_information(
    context: GameContext,
    issues: list[ReplayEvaluationIssue],
) -> None:
    public_text = "\n".join(context.public_chat_history)
    normalized_public = public_text.lower()
    for marker in PRIVATE_LEAK_MARKERS:
        if marker in normalized_public:
            _add_issue(
                issues,
                "PRIVATE_MARKER_LEAK",
                f"public log contains private marker {marker!r}",
            )

    for seat_id, private_entries in sorted(context.private_logs.items()):
        for private_entry in private_entries:
            if private_entry and private_entry in public_text:
                _add_issue(
                    issues,
                    "PRIVATE_LOG_LEAK",
                    f"private log for {seat_id} leaked into public history",
                )
                break
