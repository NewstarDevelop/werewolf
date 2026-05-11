#!/usr/bin/env python3
"""Run deterministic full-game replay evaluations.

Example:
    python backend/evaluate_replays.py --count 20 --rounds 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.engine.replay_evaluation import (  # noqa: E402
    DEFAULT_REPLAY_MAX_ROUNDS,
    DEFAULT_REPLAY_SEED_COUNT,
    default_replay_seeds,
    evaluate_replay_seeds_sync,
)


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, TypeError, ValueError):
            continue


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic Werewolf full-game replay evaluation."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_REPLAY_SEED_COUNT,
        help=f"number of consecutive seeds to evaluate (default: {DEFAULT_REPLAY_SEED_COUNT})",
    )
    parser.add_argument(
        "--start-seed",
        type=int,
        default=1,
        help="first seed in the consecutive seed range (default: 1)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_REPLAY_MAX_ROUNDS,
        help=f"maximum day/night rounds per game (default: {DEFAULT_REPLAY_MAX_ROUNDS})",
    )
    args = parser.parse_args()

    try:
        seeds = default_replay_seeds(count=args.count, start_seed=args.start_seed)
        summary = evaluate_replay_seeds_sync(seeds, max_rounds=args.rounds)
    except ValueError as exc:
        parser.error(str(exc))

    print(
        f"Replay evaluation: {summary.passed_count}/{len(summary.results)} passed "
        f"({summary.failed_count} failed)"
    )
    print(f"Seeds: {seeds[0]}..{seeds[-1]} · max rounds: {args.rounds}")
    print()

    quality = summary.quality
    outcome_counts = ", ".join(
        f"{outcome}={count}"
        for outcome, count in sorted(quality.outcome_counts.items())
    ) or "none"
    print("AI quality summary:")
    print(f"  outcomes: {outcome_counts}")
    print(
        f"  averages: days={quality.average_day_count:.1f}, "
        f"night_rounds={quality.average_rounds_recorded:.1f}"
    )
    print(
        f"  speeches: total={quality.speech_count}, speakers={quality.unique_speaker_count}, "
        f"repeated={quality.repeated_speech_count} ({quality.repetition_rate:.0%}), "
        f"table_terms={quality.table_talk_term_hits}, tactic_labels={quality.tactic_label_hits}"
    )
    print(
        f"  votes: rounds={quality.vote_rounds}, ballots={quality.ballot_count}, "
        f"abstentions={quality.abstention_count} ({quality.abstention_rate:.0%}), "
        f"no_banishment={quality.no_banishment_count}"
    )
    print(
        f"  night actions: wolf_kills={quality.wolf_kill_attempts}, "
        f"seer_checks={quality.seer_checks}, witch_saves={quality.witch_saves}, "
        f"witch_poisons={quality.witch_poisons}"
    )
    if summary.insights:
        print("  notable seeds:")
        for insight in summary.insights:
            print(f"    - seed={insight.seed} {insight.code}: {insight.message}")
    print()

    for result in summary.results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"[{status}] seed={result.seed} outcome={result.outcome} "
            f"day={result.day_count} rounds={result.rounds_recorded} "
            f"speeches={result.quality.speech_count} "
            f"abstentions={result.quality.abstention_count} "
            f"summary={result.final_summary}"
        )
        for issue in result.issues:
            day = f" day={issue.day_count}" if issue.day_count is not None else ""
            print(f"       - {issue.code}{day}: {issue.message}")

    return 0 if summary.passed else 1


if __name__ == "__main__":
    configure_output_encoding()
    raise SystemExit(main())
