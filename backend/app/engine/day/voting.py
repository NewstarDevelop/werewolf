from dataclasses import dataclass

from app.domain.game_context import GameContext
from app.domain.player import AIPlayer


@dataclass(slots=True, kw_only=True)
class VotingResult:
    votes: dict[int, int]
    ballots: dict[int, int]
    abstentions: list[int]
    banished_seat: int | None
    summary: str


def _remember_vote_choices(
    context: GameContext,
    *,
    ballots: dict[int, int],
    abstentions: list[int],
    summary: str,
) -> None:
    for voter_seat, target_seat in sorted(ballots.items()):
        voter = context.players[voter_seat]
        if isinstance(voter, AIPlayer):
            voter.remember(f"我上一轮投票给 {target_seat}号。票型结果：{summary}")

        target = context.players[target_seat]
        if isinstance(target, AIPlayer) and target_seat != voter_seat:
            target.remember(f"{voter_seat}号上一轮投票打了你。票型结果：{summary}")

    for voter_seat in sorted(abstentions):
        voter = context.players[voter_seat]
        if isinstance(voter, AIPlayer):
            voter.remember(f"我上一轮选择弃票。票型结果：{summary}")


def resolve_voting(
    context: GameContext,
    *,
    votes_by_voter: dict[int, int | None],
) -> VotingResult:
    alive_seats = set(context.alive_seat_ids())
    if set(votes_by_voter) != alive_seats:
        raise ValueError("all alive players must vote or abstain")

    tally: dict[int, int] = {}
    ballots: dict[int, int] = {}
    abstentions: list[int] = []

    for voter_seat, target_seat in sorted(votes_by_voter.items()):
        if target_seat is None:
            abstentions.append(voter_seat)
            continue
        if target_seat not in alive_seats:
            raise ValueError("vote target must be alive")
        ballots[voter_seat] = target_seat
        tally[target_seat] = tally.get(target_seat, 0) + 1

    if not tally:
        summary = "所有玩家弃票，本轮无人出局。"
        _remember_vote_choices(
            context,
            ballots=ballots,
            abstentions=abstentions,
            summary=summary,
        )
        return VotingResult(
            votes={},
            ballots=ballots,
            abstentions=abstentions,
            banished_seat=None,
            summary=summary,
        )

    highest_votes = max(tally.values())
    winners = [seat_id for seat_id, count in sorted(tally.items()) if count == highest_votes]
    if len(winners) > 1:
        summary = "出现平票，本轮无人出局。"
        _remember_vote_choices(
            context,
            ballots=ballots,
            abstentions=abstentions,
            summary=summary,
        )
        return VotingResult(
            votes=tally,
            ballots=ballots,
            abstentions=abstentions,
            banished_seat=None,
            summary=summary,
        )

    banished_seat = winners[0]
    summary = f"{banished_seat}号玩家被放逐出局。"
    _remember_vote_choices(
        context,
        ballots=ballots,
        abstentions=abstentions,
        summary=summary,
    )
    context.players[banished_seat].mark_dead()
    return VotingResult(
        votes=tally,
        ballots=ballots,
        abstentions=abstentions,
        banished_seat=banished_seat,
        summary=summary,
    )
