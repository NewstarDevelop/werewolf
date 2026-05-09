#!/usr/bin/env python3
"""
狼人杀 CLI 回放模拟器
直接使用 GameEngine 模拟完整一局（无 LLM，纯规则 AI），输出格式化回放日志

用法:
    python wolf_cli_replay.py [--seed 42] [--rounds 3]
"""

import argparse
import asyncio
import random
import sys
from datetime import datetime

sys.path.insert(0, __file__.rstrip("wolf_cli_replay.py"))

from app.engine.init import initialize_game
from app.engine.game_engine import GameEngine
from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.engine.states.phase import GamePhase

FULL_GAME_MAX_ROUNDS = 20


def configure_output_encoding() -> None:
    """Use UTF-8 output so replay markers do not crash on Windows code pages."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, TypeError, ValueError):
            continue


def resolve_max_rounds(rounds: int) -> int:
    if rounds < 0:
        raise ValueError("--rounds must be greater than or equal to 0")
    return FULL_GAME_MAX_ROUNDS if rounds == 0 else rounds


class ReplayEngine(GameEngine):
    """扩展 GameEngine，输出完整回放日志"""

    def __init__(self, seed: int = 42):
        super().__init__(rng=random.Random(seed), llm_client=None)

    def _phase_emoji(self, phase_val: str) -> str:
        emojis = {
            "NIGHT_START": "🌙", "WOLF_ACTION": "🐺", "SEER_ACTION": "🔮",
            "WITCH_ACTION": "🧪", "NIGHT_END": "🌅", "DAY_START": "☀️",
            "HUNTER_SHOOTING": "🏹", "DEAD_LAST_WORDS": "💀", "DAY_SPEAKING": "💬",
            "VOTING": "🗳️", "VOTE_RESULT": "📊", "BANISH_LAST_WORDS": "💀",
            "GAME_OVER": "🏁",
        }
        return emojis.get(phase_val, "🔄")

    async def _notify_phase_changed(self, context: GameContext) -> None:
        phase_val = context.phase
        emoji = self._phase_emoji(phase_val)
        print(f"\n{'─'*60}")
        print(f"  [{emoji}] 第 {context.day_count} 天 - {phase_val}")
        print(f"{'─'*60}")

    async def _notify_player_state(self, context: GameContext, dead_seats: list[int]) -> None:
        for seat in dead_seats:
            player = context.players.get(seat)
            if player:
                role_emoji = {
                    Role.WOLF: "🐺", Role.SEER: "🔮", Role.WITCH: "🧪",
                    Role.HUNTER: "🏹", Role.VILLAGER: "👤",
                }.get(player.role, "❓")
                print(f"  💀 玩家 {seat} 号({role_emoji}{player.role.value}) 已死亡")

    async def _notify_death_revealed(
        self, context: GameContext, dead_seats: list[int], eligible_last_words: list[int]
    ) -> None:
        if dead_seats:
            print(f"\n  📢 昨夜死亡: {', '.join(f'{s}号' for s in dead_seats)}")
        if eligible_last_words:
            print(f"  📝 可留遗言: {', '.join(f'{s}号' for s in eligible_last_words)}")

    async def _notify_vote_resolved(
        self,
        *,
        votes: dict[int, int],
        ballots: dict[int, int] | None = None,
        abstentions: list[int],
        banished_seat: int | None,
        summary: str,
    ) -> None:
        if ballots:
            print(f"\n  🗳️ 投票详情:")
            for voter, target in sorted(ballots.items()):
                print(f"     {voter}号 → {target}号")
        elif votes:
            print(f"\n  🗳️ 投票统计:")
            for target, count in sorted(votes.items()):
                print(f"     {target}号 <= {count}票")
        if abstentions:
            print(f"  ⏭️ 弃权: {', '.join(f'{s}号' for s in abstentions)}")
        if banished_seat:
            player_name = banished_seat
            print(f"  ⚖️ 放逐: {player_name}号")
        else:
            print(f"  ⚖️ 无人被放逐")
        print(f"  📋 {summary}")

    async def _notify_thinking(self, seat_id: int, _: bool) -> None:
        pass  # suppress thinking


def print_role_info(context: GameContext):
    """打印玩家身份"""
    print(f"\n{'─'*50}")
    print("  📋 玩家身份")
    print(f"{'─'*50}")
    for seat_id, player in sorted(context.players.items()):
        role_emoji = {
            Role.WOLF: "🐺", Role.SEER: "🔮", Role.WITCH: "🧪",
            Role.HUNTER: "🏹", Role.VILLAGER: "👤",
        }.get(player.role, "❓")
        status = "✅ 存活" if player.is_alive else "💀 死亡"
        print(f"   座位 {seat_id:2d}: {role_emoji} {player.role.value:10s} {status}")


def print_game_summary(context: GameContext):
    """打印完整游戏总结"""
    print(f"\n{'★'*30}")
    print("  游戏总结")
    print(f"{'★'*30}")

    print_role_info(context)

    total_days = context.day_count
    print(f"\n📊 共进行了 {total_days} 天")

    if context.vote_history:
        print(f"\n📋 投票记录：")
        for vs in context.vote_history:
            day = vs.day_count
            if vs.banished_seat:
                player = context.players.get(vs.banished_seat)
                role_str = f"({player.role.value})" if player else ""
                print(f"  第{day}天: {vs.banished_seat}号{role_str} 被放逐")
            else:
                print(f"  第{day}天: 无人被放逐")
            print(f"           {vs.summary}")

    if context.night_actions:
        print(f"\n🌙 夜间行动记录：")
        for na in context.night_actions:
            day = na.day_count
            parts = []
            if na.wolf_target is not None:
                parts.append(f"🐺狼人刀 {na.wolf_target}号")
            if na.seer_target is not None:
                result_str = "🟢好人" if na.seer_result == "GOOD" else "🔴狼人"
                parts.append(f"🔮预言家查{na.seer_target}号={result_str}")
            if na.witch_save_target is not None:
                parts.append(f"🧪女巫救{na.witch_save_target}号")
            if na.witch_poison_target is not None:
                parts.append(f"🧪女巫毒{na.witch_poison_target}号")
            if na.dead_seats:
                parts.append(f"💀阵亡={na.dead_seats}")
            print(f"  第{day}天: {'; '.join(parts)}")


def print_event_log(context: GameContext, max_events: int = 200):
    """按时间顺序打印公共事件"""
    events = context.public_chat_events
    if not events:
        return

    print(f"\n{'█'*60}")
    print("  完整事件日志")
    print(f"{'█'*60}")

    shown = 0
    for event in events:
        if shown >= max_events:
            print(f"  ... (剩余 {len(events) - shown} 条未显示)")
            break

        emoji_map = {
            "NIGHT_KILL": "💀", "NIGHT_DEATH": "💀", "DEATH_REVEAL": "💀",
            "BANISHMENT": "⚖️", "VOTE_NO_BANISHMENT": "⏭️",
            "SPEECH": "💬", "SYSTEM": "ℹ️", "GAME_OVER_SUMMARY": "🏁",
            "HUNTER_SHOT": "🏹", "NIGHT_START": "🌙", "DAY_START": "☀️",
            "PHASE_CHANGE": "🔄", "IDENTITY": "🎭",
        }
        emoji = emoji_map.get(event.event_type, "📌")

        msg = event.message
        if len(msg) > 300:
            msg = msg[:300] + "..."

        # Simpler: just print type prefix
        print(f"  {emoji}[{event.event_type}] {msg}")
        shown += 1


async def main():
    parser = argparse.ArgumentParser(description="狼人杀 CLI 回放模拟器")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认: 42)")
    parser.add_argument("--rounds", type=int, default=0, help="最大轮次 (0=完整一局，最多20轮)")
    args = parser.parse_args()

    seed = args.seed
    try:
        max_rounds = resolve_max_rounds(args.rounds)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"{'★'*30}")
    print("  狼人杀 CLI 回放模拟器")
    print(f"  随机种子: {seed}")
    print(f"{'★'*30}")

    # 初始化 9 人局
    rng = random.Random(seed)
    init_result = initialize_game(rng=rng)
    context = init_result.context

    print(f"\n👤 人类玩家: {init_result.human_seat_id} 号 → 🎭 {init_result.human_role}")
    print_role_info(context)

    # 创建引擎并运行
    print(f"\n{'#'*60}")
    print("  游戏开始")
    print(f"{'#'*60}")
    engine = ReplayEngine(seed=seed)
    final_context = await engine.run_loop(context=context, max_rounds=max_rounds)

    # 输出完整事件日志
    print_event_log(final_context)

    # 输出总结
    print_game_summary(final_context)

    print(f"\n{'★'*30}")
    print("  回放完毕")
    print(f"{'★'*30}")


if __name__ == "__main__":
    configure_output_encoding()
    asyncio.run(main())
