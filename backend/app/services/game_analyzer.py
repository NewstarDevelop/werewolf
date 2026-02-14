"""Game Analysis Service - AI-powered performance and quality evaluation."""
import asyncio
import logging
from typing import Dict, Any, List

from openai import AsyncOpenAI

from app.models.game import Game, Player
from app.schemas.enums import Role, MessageType, ActionType, Winner
from app.core.config import settings
from app.services.analysis_cache import AnalysisCache
from app.services.llm import CUSTOM_USER_AGENT

logger = logging.getLogger(__name__)

# T-PERF-001: Rate limiting for analysis requests
# Limit concurrent analysis to prevent overwhelming the AI service
_analysis_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent analyses


async def analyze_game(game: Game) -> Dict[str, Any]:
    """
    Analyze finished game with configurable mode and language.

    T-PERF-001: Now async with rate limiting to prevent blocking and overload.

    Evaluates:
    - Individual player performance (strategy, logic, social influence)
    - Match quality (balance, drama, technical stability)
    - MVP/LVP moments

    Supports multiple analysis modes:
    - comprehensive: Detailed analysis (default)
    - quick: Brief summary
    - custom: Custom template (future extension)
    """

    # Determine analysis language
    analysis_language = settings.ANALYSIS_LANGUAGE
    if analysis_language == "auto":
        analysis_language = game.language

    analysis_mode = settings.ANALYSIS_MODE

    # Try cache first (offload sync file I/O to thread pool)
    if settings.ANALYSIS_CACHE_ENABLED:
        cached = await asyncio.to_thread(AnalysisCache.get, game.id, analysis_mode, analysis_language)
        if cached:
            logger.info(f"Returning cached analysis for game {game.id}")
            return cached["result"]

    # T-PERF-001: Rate limiting - wait for semaphore
    async with _analysis_semaphore:
        logger.info(f"Generating new analysis for game {game.id}")

        # Collect game data
        game_data = _collect_game_data(game)

        # Build prompt based on mode
        prompt = _get_analysis_prompt_by_mode(game_data, analysis_language, analysis_mode)

        # Call AI with quality detection (now async)
        analysis_text = await _call_ai_analyzer(prompt, analysis_language, analysis_mode)

    # Structure the response
    result = {
        "game_id": game.id,
        "winner": game.winner,
        "total_days": game.day,
        "analysis": analysis_text,
        "game_summary": _build_game_summary(game_data),
        "analysis_mode": analysis_mode,
        "analysis_language": analysis_language,
    }

    # Save to cache (offload sync file I/O to thread pool)
    if settings.ANALYSIS_CACHE_ENABLED:
        await asyncio.to_thread(AnalysisCache.set, game.id, analysis_mode, analysis_language, result)

    return result


def _collect_game_data(game: Game) -> Dict[str, Any]:
    """Collect comprehensive game data for analysis."""

    players_data = []
    for player in game.players.values():
        player_data = {
            "seat_id": player.seat_id,
            "name": player.personality.name if player.personality else f"Player {player.seat_id}",
            "role": player.role.value,
            "is_human": player.is_human,
            "is_alive": player.is_alive,
            "survival_days": _calculate_survival_days(game, player.seat_id),
        }

        # Add role-specific data
        if player.role == Role.SEER:
            player_data["verifications"] = len(player.verified_players)
            player_data["verified_wolves"] = sum(
                1 for is_wolf in player.verified_players.values() if is_wolf
            )
        elif player.role == Role.WITCH:
            player_data["used_save"] = not player.has_save_potion
            player_data["used_poison"] = not player.has_poison_potion
        elif player.role == Role.HUNTER:
            player_data["used_shot"] = not player.can_shoot

        players_data.append(player_data)

    # Collect speech data
    speeches = []
    for msg in game.messages:
        if msg.msg_type == MessageType.SPEECH:
            player = game.players.get(msg.seat_id)
            speeches.append({
                "day": msg.day,
                "seat_id": msg.seat_id,
                "speaker": player.personality.name if player and player.personality else f"Player {msg.seat_id}",
                "content": msg.content
            })

    # Collect voting data
    votes_by_day = {}
    for action in game.actions:
        if action.action_type == ActionType.VOTE and action.target_id:
            day_key = f"day_{action.day}"
            if day_key not in votes_by_day:
                votes_by_day[day_key] = []
            votes_by_day[day_key].append({
                "voter": action.player_id,
                "target": action.target_id
            })

    # Collect kill/action history
    night_kills = []
    for action in game.actions:
        if action.action_type == ActionType.KILL and action.target_id:
            night_kills.append({
                "day": action.day,
                "killer": action.player_id,
                "victim": action.target_id
            })

    return {
        "players": players_data,
        "speeches": speeches,
        "votes_by_day": votes_by_day,
        "night_kills": night_kills,
        "total_days": game.day,
        "winner": game.winner.value if game.winner else "none"
    }


def _calculate_survival_days(game: Game, seat_id: int) -> int:
    """Calculate how many days a player survived.

    Scans action history for lethal events (KILL, POISON, SHOOT, SELF_DESTRUCT)
    targeting this player to determine the day of death.
    """
    player = game.players.get(seat_id)
    if not player:
        return 0

    if player.is_alive:
        return game.day

    # Lethal action types that indicate a player was killed
    lethal_actions = {ActionType.KILL, ActionType.POISON, ActionType.SHOOT, ActionType.SELF_DESTRUCT}

    # Find the earliest lethal action targeting this player
    death_day = None
    for action in game.actions:
        if action.target_id == seat_id and action.action_type in lethal_actions:
            if death_day is None or action.day < death_day:
                death_day = action.day

    # Also check vote eliminations: if player was the most-voted target
    # Vote eliminations are not directly recorded as a single action,
    # so fall back to system messages announcing death
    if death_day is None:
        for msg in game.messages:
            if (msg.msg_type == MessageType.SYSTEM
                    and msg.seat_id == seat_id
                    and msg.day is not None):
                # System messages about a specific player likely indicate their death
                death_day = msg.day
                break

    return death_day if death_day is not None else max(1, game.day - 1)


def _get_analysis_prompt_by_mode(game_data: Dict[str, Any], language: str, mode: str) -> str:
    """Generate analysis prompt based on mode."""

    if mode == "quick":
        return _build_quick_analysis_prompt(game_data, language)
    elif mode == "custom":
        return _build_custom_analysis_prompt(game_data, language)
    else:  # comprehensive (default)
        return _build_analysis_prompt(game_data, language)


def _build_quick_analysis_prompt(game_data: Dict[str, Any], language: str) -> str:
    """Build quick analysis prompt (shorter, faster)."""

    if language == "en":
        return f"""# Quick Game Analysis

Winner: {game_data['winner'].title()}
Days: {game_data['total_days']}

Provide a brief 3-section analysis:
1. Winner's key advantage (1 paragraph)
2. Critical turning point (1 paragraph)
3. MVP player (1 sentence)

Keep it under 200 words."""
    else:
        return f"""# 快速对局分析

获胜方：{'好人' if game_data['winner'] == 'villager' else '狼人' if game_data['winner'] == 'werewolf' else '平局'}
天数：{game_data['total_days']}

请提供简短的3段分析：
1. 获胜方关键优势（1段）
2. 关键转折点（1段）
3. MVP玩家（1句话）

控制在200字以内。"""


def _build_custom_analysis_prompt(game_data: Dict[str, Any], language: str) -> str:
    """Build custom analysis prompt (can be extended by user)."""
    # For now, use comprehensive mode
    # Future: allow custom prompt template from env var or config file
    return _build_analysis_prompt(game_data, language)


def _build_analysis_prompt(game_data: Dict[str, Any], language: str) -> str:
    """Build comprehensive analysis prompt based on evaluation framework."""

    if language == "en":
        return _build_analysis_prompt_en(game_data)
    else:
        return _build_analysis_prompt_zh(game_data)


def _build_analysis_prompt_zh(game_data: Dict[str, Any]) -> str:
    """Build Chinese analysis prompt."""

    prompt = f"""# 狼人杀对局分析任务

## 游戏基本信息
- 总天数：{game_data['total_days']}
- 获胜方：{'好人' if game_data['winner'] == 'villager' else '狼人' if game_data['winner'] == 'werewolf' else '平局'}

## 玩家信息
"""

    for p in game_data['players']:
        role_name = {'werewolf': '狼人', 'villager': '村民', 'seer': '预言家', 'witch': '女巫', 'hunter': '猎人'}.get(p['role'], p['role'])
        status = '存活' if p['is_alive'] else '死亡'
        prompt += f"- {p['seat_id']}号 {p['name']} - {role_name} - {status} - 存活{p['survival_days']}天\n"

    prompt += "\n## 发言记录\n"
    for speech in game_data['speeches'][-20:]:  # Last 20 speeches
        prompt += f"第{speech['day']}天 - {speech['speaker']}：{speech['content'][:100]}...\n"

    prompt += f"\n## 投票记录\n"
    for day_key, votes in game_data['votes_by_day'].items():
        prompt += f"{day_key}: {len(votes)}次投票\n"

    prompt += """

## 分析要求

请根据以下评估体系对本局游戏进行全面分析：

### 第一部分：玩家表现分析

为每位玩家评估以下维度：

**1. 硬性胜负与博弈价值**
- 有效生存价值：存活轮次、挡刀贡献、无效死亡率
- 投票转化率：投票准确率、摇摆票捕获
- 技能释放收益率：技能对轮次的贡献

**2. 逻辑构建与推理能力**
- 多重世界观构建：是否能推演多条平行逻辑线
- 信息提取与记忆：细节捕捉、长程记忆
- 逻辑自洽性：前后一致性、是否有矛盾

**3. 社交影响力与拟人化**
- 舆论引导力：跟随票数、归票成功率
- 伪装与欺骗（狼人）：潜伏深度、倒钩指数
- 拟人化程度（AI）：角色扮演一致性、情绪适应、语言多样性

### 第二部分：对局质量分析

**1. 动态平衡性**
- 胜率波动：是否有多次优劣势转换
- 信息熵：身份未知程度的变化
- 轮次差：获胜方领先的轮次

**2. 精彩程度**
- 反转节点：站边倒戈、悍跳成功等关键时刻
- 投票悬念：票型差距
- 战术复杂度：高阶博弈的出现

**3. 技术稳定性**（针对AI局）
- 指令遵从：是否严格遵守游戏规则
- 响应流畅度：发言生成速度

### 第三部分：复盘要点

**1. MVP时刻**：决定胜负的关键发言或操作
**2. LVP时刻**：致命失误
**3. 六维能力雷达图数据**：为每位玩家生成六维评分（生存、逻辑、输出、配置、心态、欺诈），满分10分

## 输出格式要求

请以清晰的markdown格式输出，包含：

1. **总体评价**（2-3句话概括本局质量）
2. **玩家表现分析**（每位玩家的详细评价，包含六维评分）
3. **对局质量分析**（平衡性、精彩程度、技术稳定性）
4. **MVP与LVP**（具体时刻和理由）
5. **改进建议**（针对人类玩家和AI策略）

开始分析：
"""

    return prompt


def _build_analysis_prompt_en(game_data: Dict[str, Any]) -> str:
    """Build English analysis prompt."""

    prompt = f"""# Werewolf Game Analysis Task

## Basic Game Information
- Total Days: {game_data['total_days']}
- Winner: {game_data['winner'].title()}

## Player Information
"""

    for p in game_data['players']:
        status = 'Alive' if p['is_alive'] else 'Dead'
        prompt += f"- Seat {p['seat_id']} {p['name']} - {p['role'].title()} - {status} - Survived {p['survival_days']} days\n"

    prompt += "\n## Speech Records\n"
    for speech in game_data['speeches'][-20:]:
        prompt += f"Day {speech['day']} - {speech['speaker']}: {speech['content'][:100]}...\n"

    prompt += f"\n## Voting Records\n"
    for day_key, votes in game_data['votes_by_day'].items():
        prompt += f"{day_key}: {len(votes)} votes\n"

    prompt += """

## Analysis Requirements

Please analyze this game comprehensively based on the following evaluation framework:

### Part 1: Player Performance Analysis

Evaluate each player on:

**1. Hard Metrics & Game Theory Value**
- Effective Survival Value: survival rounds, tanking contribution, ineffective death rate
- Voting Conversion Rate: voting accuracy, swing vote capture
- Skill ROI: contribution to game progression

**2. Logic & Reasoning**
- Multi-World Building: ability to reason through multiple scenarios
- Information Retrieval & Memory: detail capture, long-term memory
- Logical Consistency: coherence, contradictions

**3. Social Influence & Human-likeness**
- Opinion Leadership: follower votes, vote consolidation success
- Deception & Camouflage (Werewolf): camouflage depth, reverse psychology
- Human-likeness (AI): role consistency, emotional adaptation, language diversity

### Part 2: Match Quality Analysis

**1. Dynamic Balance**
- Win Probability Swing: advantage reversals
- Information Entropy: uncertainty levels
- Round Margin: winner's lead

**2. Engagement & Drama**
- Twist Moments: key turning points
- Voting Tension: vote margins
- Tactical Complexity: advanced strategies

**3. Technical Stability** (for AI games)
- Instruction Following: rule adherence
- Response Fluency: generation speed

### Part 3: Key Highlights

**1. MVP Moments**: Game-deciding plays
**2. LVP Moments**: Critical mistakes
**3. Hexagon Stats**: Six-dimensional scores for each player (Survival, Logic, Output, Utility, Mentality, Deception) out of 10

## Output Format

Please provide in clear markdown format:

1. **Overall Assessment** (2-3 sentences)
2. **Player Performance Analysis** (detailed evaluation with hexagon scores)
3. **Match Quality Analysis** (balance, drama, technical stability)
4. **MVP & LVP** (specific moments and reasons)
5. **Improvement Suggestions** (for human players and AI strategies)

Begin analysis:
"""

    return prompt


async def _call_ai_analyzer(prompt: str, language: str, mode: str) -> str:
    """
    Call AI to generate analysis with quality detection and retry.

    T-PERF-001: Now async to prevent blocking main event loop.
    FIX: Now uses LLMService rate limiting to respect global quotas.
    """

    max_attempts = 2
    min_length = 50 if mode == "quick" else 100

    provider = settings.get_analysis_provider()
    if not provider:
        logger.error(
            "AI analysis unavailable: No valid provider configured. "
            "To enable analysis: 1) Set OPENAI_API_KEY in .env, "
            "OR 2) Configure another provider (e.g., DEEPSEEK_API_KEY) and set ANALYSIS_PROVIDER=deepseek"
        )
        return _generate_fallback_analysis(language)

    # FIX: Import and use LLMService for rate limiting
    from app.services.llm import llm_service

    # FIX: Get rate limiter for this provider
    limiter = await llm_service._get_limiter(provider)

    # T-PERF-001: Use async client to prevent blocking
    # Use default_headers for User-Agent (consistent with llm.py game requests)
    client = AsyncOpenAI(
        api_key=provider.api_key,
        base_url=provider.base_url if provider.base_url else None,
        default_headers={"User-Agent": CUSTOM_USER_AGENT},
        timeout=120.0,
    )

    for attempt in range(max_attempts):
        try:
            logger.info(f"Analysis attempt {attempt + 1}/{max_attempts} using {provider.name}")

            # FIX: Apply rate limiting before API call
            async with limiter.limit(max_wait_seconds=30.0):
                response = await client.chat.completions.create(
                    model=provider.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional Werewolf game analyst. Provide detailed, insightful analysis."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=provider.temperature,
                    max_tokens=provider.max_tokens
                )

            analysis_text = response.choices[0].message.content or ""

            # Quality check
            if len(analysis_text) < min_length:
                logger.warning(f"Analysis too short ({len(analysis_text)} chars), expected >{min_length}")
                if attempt < max_attempts - 1:
                    logger.info("Retrying with adjusted prompt...")
                    continue

            logger.info(f"Analysis generated successfully ({len(analysis_text)} chars)")

            # FIX: Close client after use to prevent connection leak
            await client.close()
            return analysis_text

        except Exception as e:
            logger.error(
                "Analysis attempt %s failed: %s (base_url=%s, model=%s, mode=%s)",
                attempt + 1,
                e,
                provider.base_url,
                provider.model,
                mode,
            )
            if attempt < max_attempts - 1:
                logger.info("Retrying...")
                continue

    # All attempts failed - close client before returning
    try:
        await client.close()
    except Exception:
        pass

    logger.error("All analysis attempts failed, returning fallback")
    return _generate_fallback_analysis(language)


def _generate_fallback_analysis(language: str) -> str:
    """Generate fallback analysis when AI is unavailable."""

    if language == "en":
        return """# Game Analysis (Fallback Mode)

## Note
AI analysis is temporarily unavailable. Please try again later.

This is an automated summary with limited insights.

## Summary
- The game has concluded
- Detailed performance analysis requires AI service

Please configure AI provider settings to enable full analysis features.
"""
    else:
        return """# 对局分析（备用模式）

## 说明
AI分析服务暂时不可用，请稍后重试。

这是自动生成的简要总结，分析深度有限。

## 总结
- 游戏已结束
- 详细的表现分析需要AI服务支持

请配置AI服务以启用完整的分析功能。
"""


def _build_game_summary(game_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build basic game summary stats."""

    total_players = len(game_data['players'])
    alive_players = sum(1 for p in game_data['players'] if p['is_alive'])
    total_speeches = len(game_data['speeches'])
    total_votes = sum(len(votes) for votes in game_data['votes_by_day'].values())

    return {
        "total_players": total_players,
        "alive_players": alive_players,
        "total_days": game_data['total_days'],
        "total_speeches": total_speeches,
        "total_votes": total_votes,
        "winner": game_data['winner']
    }
