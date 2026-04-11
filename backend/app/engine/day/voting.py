from dataclasses import dataclass

from app.domain.game_context import GameContext


@dataclass(slots=True, kw_only=True)
class VotingResult:
    votes: dict[int, int]
    abstentions: list[int]
    banished_seat: int | None
    summary: str


def resolve_voting(
    context: GameContext,
    *,
    votes_by_voter: dict[int, int | None],
) -> VotingResult:
    alive_seats = set(context.alive_seat_ids())
    if set(votes_by_voter) != alive_seats:
        raise ValueError("all alive players must vote or abstain")

    tally: dict[int, int] = {}
    abstentions: list[int] = []

    for voter_seat, target_seat in sorted(votes_by_voter.items()):
        if target_seat is None:
            abstentions.append(voter_seat)
            continue
        if target_seat not in alive_seats:
            raise ValueError("vote target must be alive")
        tally[target_seat] = tally.get(target_seat, 0) + 1

    if not tally:
        return VotingResult(
            votes={},
            abstentions=abstentions,
            banished_seat=None,
            summary="所有玩家弃票，本轮无人出局。",
        )

    highest_votes = max(tally.values())
    winners = [seat_id for seat_id, count in sorted(tally.items()) if count == highest_votes]
    if len(winners) > 1:
        return VotingResult(
            votes=tally,
            abstentions=abstentions,
            banished_seat=None,
            summary="出现平票，本轮无人出局。",
        )

    banished_seat = winners[0]
    context.players[banished_seat].mark_dead()
    return VotingResult(
        votes=tally,
        abstentions=abstentions,
        banished_seat=banished_seat,
        summary=f"{banished_seat}号玩家被放逐出局。",
    )
