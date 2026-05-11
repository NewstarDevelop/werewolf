import asyncio
import random

from app.domain.game_context import GameContext
from app.engine.game_engine import GameEngine
from app.engine.replay_evaluation import (
    CAPPED_GAME_SUMMARY,
    ReplayEvaluationResult,
    ReplayEvaluationSummary,
    ReplayQualityMetrics,
    analyze_replay_quality,
    default_replay_seeds,
    evaluate_replay_seeds,
    validate_replay_context,
)
from app.llm.phrasebook import TABLE_TALK_TERMS, TACTIC_STYLE_HINTS


def test_default_replay_seeds_builds_consecutive_range() -> None:
    assert default_replay_seeds(count=4, start_seed=7) == [7, 8, 9, 10]


def test_evaluate_replay_seeds_passes_fixed_full_games() -> None:
    summary = asyncio.run(
        evaluate_replay_seeds(
            default_replay_seeds(count=5),
            max_rounds=20,
        )
    )

    assert summary.passed is True
    assert summary.passed_count == 5
    assert summary.failed_count == 0
    assert all(result.final_summary for result in summary.results)
    assert all(result.outcome in {"GOOD", "WOLF", "CAPPED"} for result in summary.results)
    assert summary.quality.total_games == 5
    assert sum(summary.quality.outcome_counts.values()) == 5
    assert summary.quality.speech_count > 0
    assert summary.quality.vote_rounds > 0
    assert summary.quality.wolf_kill_attempts > 0


def test_analyze_replay_quality_detects_repetition_and_table_terms() -> None:
    context = GameContext()
    term = TABLE_TALK_TERMS[0]
    tactic_label = next(iter(TACTIC_STYLE_HINTS))
    repeated_message = f"{term}{term}{tactic_label}"
    context.add_public_message(
        repeated_message,
        message_kind="speech",
        event_type="SPEECH",
        actor_seat=1,
    )
    context.add_public_message(
        repeated_message,
        message_kind="speech",
        event_type="SPEECH",
        actor_seat=2,
    )

    quality = analyze_replay_quality(context)

    assert quality.speech_count == 2
    assert quality.unique_speaker_count == 2
    assert quality.repeated_speech_count == 1
    assert quality.repetition_rate == 0.5
    assert quality.table_talk_term_hits == 4
    assert quality.tactic_label_hits == 2


def test_replay_summary_builds_notable_quality_insights() -> None:
    summary = ReplayEvaluationSummary(
        results=[
            ReplayEvaluationResult(
                seed=99,
                outcome="CAPPED",
                quality=ReplayQualityMetrics(
                    speech_count=4,
                    repeated_speech_count=2,
                    vote_rounds=1,
                    ballot_count=1,
                    abstention_count=3,
                    no_banishment_count=1,
                ),
            )
        ]
    )

    insight_codes = {insight.code for insight in summary.insights}

    assert summary.quality.abstention_rate == 0.75
    assert summary.quality.repetition_rate == 0.5
    assert insight_codes == {
        "CAPPED_GAME",
        "HIGH_ABSTENTION",
        "HIGH_REPETITION",
        "NO_BANISHMENT",
    }


def test_validate_replay_context_detects_invalid_vote_target() -> None:
    context = asyncio.run(GameEngine(rng=random.Random(5)).run_loop(max_rounds=2))
    assert context.vote_history
    vote = context.vote_history[0]
    voter = next(iter(vote.ballots))
    original_target = vote.ballots[voter]
    vote.ballots[voter] = voter

    issues = validate_replay_context(context)

    assert any(issue.code == "VOTE_SELF_TARGET" for issue in issues)
    vote.ballots[voter] = original_target


def test_validate_replay_context_detects_private_log_leak() -> None:
    context = asyncio.run(GameEngine(rng=random.Random(2)).run_loop(max_rounds=1))
    seat_id, private_entries = next(
        (seat, entries)
        for seat, entries in sorted(context.private_logs.items())
        if entries
    )
    context.add_public_message(private_entries[0])

    issues = validate_replay_context(context)

    assert seat_id in context.private_logs
    assert any(issue.code == "PRIVATE_LOG_LEAK" for issue in issues)


def test_capped_replay_is_reported_as_valid_cap() -> None:
    context = asyncio.run(GameEngine(rng=random.Random(5)).run_loop(max_rounds=1))

    assert context.public_chat_history[-1] == CAPPED_GAME_SUMMARY
    assert validate_replay_context(context) == []
