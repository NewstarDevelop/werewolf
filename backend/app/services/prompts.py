"""Prompt templates for AI players in Werewolf game."""

from typing import TYPE_CHECKING
from app.i18n import t, normalize_language
from app.services.prompts_templates import SYSTEM_PROMPT_ZH, SYSTEM_PROMPT_EN

if TYPE_CHECKING:
    from app.models.game import Game, Player
    from app.schemas.enums import GamePhase, MessageType

# Wolf roles for checking (includes wolf_king and white_wolf_king)
WOLF_ROLE_VALUES = {"werewolf", "wolf_king", "white_wolf_king"}


def _is_garbled_or_meaningless(content: str) -> bool:
    """检测发言是否为乱码或无意义内容。

    用于预言家查验黑名单和好人噪音过滤。
    """
    import re

    if not content or len(content.strip()) < 3:
        return True

    # 检测乱码特征
    # 1. 过多特殊字符（允许常见标点和符号）
    # 允许：中文、英文、数字、空格、中英文标点、常见符号(~-._…)
    special_char_ratio = len(re.findall(r'[^\u4e00-\u9fa5a-zA-Z0-9\s，。！？、：；""''（）~\-._…·,.:;!?\'"()\[\]]', content)) / max(len(content), 1)
    if special_char_ratio > 0.5:
        return True

    # 2. 重复字符过多 (如 "啊啊啊啊啊啊")
    if re.search(r'(.)\1{5,}', content):
        return True

    # 3. 纯数字或纯符号
    if re.match(r'^[\d\s\W]+$', content):
        return True

    # 4. 过短且无实质内容
    meaningful_words = ["我", "你", "他", "狼", "好人", "预言家", "女巫", "猎人", "投", "查", "验", "杀"]
    if len(content) < 10 and not any(word in content for word in meaningful_words):
        return True

    return False


def _analyze_player_speech_quality(game: "Game", seat_id: int) -> dict:
    """分析玩家发言质量，用于预言家查验优先级和好人噪音过滤。

    Returns:
        dict: {
            "speech_count": int,  # 发言次数
            "garbled_count": int,  # 乱码发言次数
            "quality_score": float,  # 质量分数 0-1
            "is_low_priority": bool,  # 是否低优先级查验目标
            "reason": str  # 原因
        }
    """
    from app.schemas.enums import MessageType

    speeches = [msg for msg in game.messages
                if msg.seat_id == seat_id and msg.msg_type == MessageType.SPEECH]

    if not speeches:
        return {
            "speech_count": 0,
            "garbled_count": 0,
            "quality_score": 0.3,  # 沉默玩家给低分
            "is_low_priority": True,
            "reason": "silent"
        }

    garbled_count = sum(1 for msg in speeches if _is_garbled_or_meaningless(msg.content))
    garbled_ratio = garbled_count / len(speeches)

    # 计算质量分数
    quality_score = 1.0 - garbled_ratio

    # 判断是否低优先级
    is_low_priority = garbled_ratio > 0.5 or (len(speeches) == 1 and garbled_count == 1)
    reason = "garbled" if garbled_ratio > 0.5 else ("single_garbled" if is_low_priority else "normal")

    return {
        "speech_count": len(speeches),
        "garbled_count": garbled_count,
        "quality_score": quality_score,
        "is_low_priority": is_low_priority,
        "reason": reason
    }


def _build_voting_pattern_analysis(game: "Game", player: "Player", language: str = "zh") -> str:
    """构建投票模式分析摘要，用于好人阵营的注意力聚焦。

    预处理投票数据，让AI关注"硬事实"而非"噪音"。
    """
    from app.schemas.enums import ActionType
    from collections import defaultdict

    if game.day < 2:
        return ""

    # 收集投票数据
    vote_history = defaultdict(list)  # seat_id -> [(day, target)]
    for action in game.actions:
        if action.action_type == ActionType.VOTE and action.target_id:
            vote_history[action.player_id].append((action.day, action.target_id))

    if not vote_history:
        return ""

    analysis_points = []

    # 分析投票模式
    # 1. 找出总是一起投票的玩家对
    vote_pairs = defaultdict(int)
    for day in range(1, game.day + 1):
        day_votes = {seat: target for seat, votes in vote_history.items()
                     for d, target in votes if d == day}
        seats = list(day_votes.keys())
        for i, s1 in enumerate(seats):
            for s2 in seats[i+1:]:
                if day_votes[s1] == day_votes[s2]:
                    pair = tuple(sorted([s1, s2]))
                    vote_pairs[pair] += 1

    # 找出高度一致的投票对
    total_days = game.day
    for (s1, s2), count in vote_pairs.items():
        if count >= 2 and count / total_days >= 0.8:
            if language == "zh":
                analysis_points.append(f"- {s1}号和{s2}号投票高度一致（{count}/{total_days}天相同）")
            else:
                analysis_points.append(f"- #{s1} and #{s2} vote together frequently ({count}/{total_days} days)")

    # 2. 找出投票给已确认好人的玩家
    # (这需要预言家验人信息，暂时跳过)

    # 3. 找出发言与投票不一致的玩家
    # (需要更复杂的NLP分析，暂时跳过)

    if not analysis_points:
        return ""

    if language == "zh":
        header = "\n# 【系统分析】投票模式异常\n"
    else:
        header = "\n# [System Analysis] Voting Pattern Anomalies\n"

    return header + "\n".join(analysis_points)


def _get_wolf_persona_strategy(wolf_persona: str, language: str = "zh") -> str:
    """根据狼人战术角色返回差异化策略指令。

    P2优化：确保狼队战术配置多样化，避免全员冲锋。
    """
    if language == "zh":
        strategies = {
            "aggressive": """
# 🔥 你的战术角色：冲锋狼
你是狼队的矛——制造混乱、吸引火力、为深水狼打掩护。
- 主动质疑、带节奏、引导投票。需要时敢悍跳预言家发假查杀
- 投票激进，不划水。暴露后也要拖延、搅混水
- ⚠️ 不要和队友同时攻击同一人，不要关键时刻突然沉默
""",
            "hook": """
# 🎣 你的战术角色：倒钩狼
你是狼队的间谍——假装好人，积累信任，关键时刻反水。
- 第一天跟好人投票，甚至可以投狼队友做身份
- 队友被质疑时补刀攻击他，表现"被骗的愤怒"
- 信任建立后，在关键投票时带偏节奏
- ⚠️ 不要过早保护队友，表演要自然不刻意
""",
            "deep": """
# 🌊 你的战术角色：深水狼
你是狼队的王牌——必须活到最后。
- 发言简短跟随主流，表现"理性客观"。别人说服你后再跟随
- 绝不直接保护队友，即使他们被投出局
- 场上人少时才主动出击
- ⚠️ 不要带节奏（那是冲锋狼的活），不要和队友票型一致
"""
        }
    else:  # English
        strategies = {
            "aggressive": """
# 🔥 Your Tactical Role: AGGRESSIVE WOLF
You are the team's spear — create chaos, draw fire, cover for deep wolves.
- Actively question, lead votes, guide discussion. Dare to fake-claim Seer if needed
- Vote aggressively, never lurk. Even if exposed, stall and create confusion
- ⚠️ Don't attack the same person as teammates. Don't go silent at key moments
""",
            "hook": """
# 🎣 Your Tactical Role: HOOK WOLF
You are the team's spy — infiltrate village, build trust, turn at the right moment.
- Day 1: vote with villagers, even bus wolf teammates to gain credibility
- When teammates are questioned, attack them too — show "betrayed" anger
- After earning trust, mislead at critical votes
- ⚠️ Don't protect teammates early. Act natural, not forced
""",
            "deep": """
# 🌊 Your Tactical Role: DEEP WOLF
You are the team's ace — must survive until endgame.
- Keep speeches brief, follow mainstream, appear "rational and objective"
- Never directly protect teammates, even if they get voted out
- Only attack actively when few players remain
- ⚠️ Don't lead discussions (that's aggressive wolf's job). Don't mirror teammates' votes
"""
        }

    return strategies.get(wolf_persona, "")


def build_system_prompt(player: "Player", game: "Game", language: str = "zh") -> str:
    """Build the system prompt for an AI player."""
    # Normalize language to ensure consistency
    language = normalize_language(language)

    role_desc = t(f"roles.descriptions.{player.role.value}", language=language)

    # Personality description
    personality_desc = ""
    if player.personality:
        # Try to get wolf-specific trait if player is a wolf
        trait_key = f"personality.traits.{player.personality.trait}"
        if player.role.value in WOLF_ROLE_VALUES:
            wolf_trait_key = f"{trait_key}_狼人"
            trait_desc = t(wolf_trait_key, language=language, default=None)
            if not trait_desc:  # Fallback to general trait if wolf version doesn't exist
                trait_desc = t(trait_key, language=language)
        else:
            trait_desc = t(trait_key, language=language)

        style_desc = t(f"personality.styles.{player.personality.speaking_style}", language=language)
        personality_desc = f"""
{t('prompts.your_name', language=language, name=player.personality.name)}
{t('prompts.personality_trait', language=language, trait=trait_desc)}
{t('prompts.speaking_style', language=language, style=style_desc)}
"""

        # Add emotional constraint for aggressive wolves
        if player.role.value in WOLF_ROLE_VALUES and player.personality.trait == "激进":
            if language == "zh":
                personality_desc += '\n⚠️ 你是狼人，攻击前必须有逻辑依据。用理性包装攻击性——让好人觉得你是\u201c正义的愤怒\u201d，而非无脑喷。\n'
            else:
                personality_desc += "\n⚠️ You're a wolf — back up every attack with logic. Wrap aggression in rationality so villagers see 'righteous anger', not blind rage.\n"

    # Wolf teammates info (only for werewolves, wolf_king, white_wolf_king)
    wolf_info = ""
    if player.role.value in WOLF_ROLE_VALUES and player.teammates:
        teammates_str = "、".join([f"{t}号" for t in player.teammates]) if language == "zh" else ", ".join([f"#{t}" for t in player.teammates])
        wolf_info = f"\n{t('prompts.wolf_teammates', language=language, teammates=teammates_str)}\n{t('prompts.wolf_info_note', language=language)}"

        # P2优化：添加狼人差异化战术角色策略
        if player.wolf_persona:
            wolf_persona_strategy = _get_wolf_persona_strategy(player.wolf_persona, language)
            wolf_info += wolf_persona_strategy

    # Seer verification info
    seer_info = ""
    if player.role.value == "seer" and player.verified_players:
        verifications = []
        seat_suffix = "号" if language == "zh" else ""
        separator = "，" if language == "zh" else ", "
        is_word = "是" if language == "zh" else " is "
        for seat_id, is_wolf in player.verified_players.items():
            result = t("prompts.seer_result_wolf", language=language) if is_wolf else t("prompts.seer_result_villager", language=language)
            verifications.append(f"{seat_id}{seat_suffix}{is_word}{result}")
        seer_info = t("prompts.seer_verified_header", language=language) + separator.join(verifications)

    # Witch potion info
    witch_info = ""
    if player.role.value == "witch":
        potions = []
        separator = "、" if language == "zh" else ", "
        if player.has_save_potion:
            potions.append(t("prompts.witch_antidote", language=language))
        if player.has_poison_potion:
            potions.append(t("prompts.witch_poison", language=language))
        if potions:
            witch_info = t("prompts.witch_potions_header", language=language) + separator.join(potions)
        else:
            witch_info = t("prompts.witch_no_potions", language=language)

    # Language instruction (for English mode)
    language_instruction = ""
    if language == "en":
        language_instruction = f"\n\n{t('prompts.language_instruction', language=language)}"

    # Board configuration (dynamic based on player count)
    board_config = ""
    player_count = 9  # Default fallback

    # Valid configurations
    VALID_WOLF_KING_VARIANTS = {"wolf_king", "white_wolf_king"}
    SUPPORTED_PLAYER_COUNTS = {9, 12}

    if hasattr(game, 'config') and game.config:
        player_count = game.config.player_count

        # Validate player count
        if player_count not in SUPPORTED_PLAYER_COUNTS:
            # Unsupported player count, fallback to 9-player mode
            player_count = 9
            board_config = t("prompts.board_config_9", language=language)
        elif player_count == 9:
            board_config = t("prompts.board_config_9", language=language)
        elif player_count == 12:
            # Validate wolf king variant
            wolf_king_variant = game.config.wolf_king_variant or "wolf_king"
            if wolf_king_variant not in VALID_WOLF_KING_VARIANTS:
                wolf_king_variant = "wolf_king"  # Fallback to default
            board_config = t(f"prompts.board_config_12_{wolf_king_variant}", language=language)
    else:
        # Fallback to 9-player config if game.config is not available
        board_config = t("prompts.board_config_9", language=language)

    # Select template based on language
    template = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ZH

    system_prompt = f"""{t('prompts.game_intro', language=language, player_count=player_count)}
{t('prompts.your_role', language=language, role=role_desc)}
{t('prompts.your_seat', language=language, seat_id=player.seat_id)}
{personality_desc}
{template.format(wolf_info=wolf_info, seer_info=seer_info, witch_info=witch_info, language_instruction=language_instruction, board_config=board_config)}
"""
    return system_prompt


def build_context_prompt(player: "Player", game: "Game", action_type: str = "speech", language: str = "zh") -> str:
    """Build the context prompt with current game state."""
    # Normalize language to ensure consistency
    language = normalize_language(language)

    # Alive players info
    alive_players = []
    seat_suffix = "号" if language == "zh" else ""
    you_label = "（你）" if language == "zh" else " (you)"
    separator = "、" if language == "zh" else ", "
    for p in game.get_alive_players():
        status = you_label if p.seat_id == player.seat_id else ""
        alive_players.append(f"{p.seat_id}{seat_suffix}{status}")
    alive_str = separator.join(alive_players)

    # Dead players info
    dead_players = [p for p in game.players.values() if not p.is_alive]
    none_label = "无" if language == "zh" else "None"
    dead_str = separator.join([f"{p.seat_id}{seat_suffix}" for p in dead_players]) if dead_players else none_label

    # Recent messages (last 20)
    recent_messages = game.messages[-20:] if len(game.messages) > 20 else game.messages
    chat_history = []
    system_label = "【系统】" if language == "zh" else "[System]"
    wolf_chat_label = "【狼人私聊】" if language == "zh" else "[Werewolf Chat]"
    teammate_label = "（队友）" if language == "zh" else " (teammate)"
    colon = "：" if language == "zh" else ": "
    no_messages_label = "（暂无发言）" if language == "zh" else "(No messages yet)"

    for msg in recent_messages:
        # 跳过投票思考消息（不让AI看到其他玩家的投票推理）
        if msg.msg_type.value == "vote_thought":
            continue

        if msg.msg_type.value == "system":
            chat_history.append(f"{system_label} {msg.content}")
        else:
            sender = f"{msg.seat_id}{seat_suffix}"
            if msg.seat_id == player.seat_id:
                sender = f"{msg.seat_id}{seat_suffix}{you_label}"
            elif player.role.value in WOLF_ROLE_VALUES and msg.seat_id in player.teammates:
                sender = f"{msg.seat_id}{seat_suffix}{teammate_label}"

            # 区分消息类型
            if msg.msg_type.value == "wolf_chat":
                # 只有狼人才能看到狼人私聊
                if player.role.value in WOLF_ROLE_VALUES:
                    chat_history.append(f"{wolf_chat_label} {sender}{colon}{msg.content}")
            else:
                chat_history.append(f"{sender}{colon}{msg.content}")

    chat_str = "\n".join(chat_history) if chat_history else no_messages_label

    # Wolf night plan context (inject for wolves during day)
    wolf_plan_context = ""
    if player.role.value in WOLF_ROLE_VALUES and game.wolf_night_plan and game.phase.value.startswith("day"):
        if language == "zh":
            wolf_plan_context = f"\n\n💡 **昨晚团队计划**: {game.wolf_night_plan}\n记住团队战术,白天行动要配合夜间计划\n"
        else:
            wolf_plan_context = f"\n\n💡 **Last Night's Team Plan**: {game.wolf_night_plan}\nRemember the team tactics, coordinate day actions with night plan\n"

    # Phase-specific instructions
    phase_instruction = ""
    if action_type == "speech":
        # 检查是否是狼人夜间讨论阶段 (包括狼王和白狼王)
        if game.phase.value == "night_werewolf_chat" and player.role.value in WOLF_ROLE_VALUES:
            # 狼人夜间讨论专用 prompt
            separator = "、" if language == "zh" else ", "
            seat_suffix = "号" if language == "zh" else ""
            teammates_str = separator.join([f"{t}{seat_suffix}" for t in (player.teammates or [])])

            if language == "zh":
                phase_instruction = f"""
# 夜晚狼人私密讨论
你和队友（{teammates_str}）正在私下讨论，好人看不到。

**核心任务**：确定今晚刀谁。优先级：预言家 > 女巫 > 猎人 > 强势村民。
也可以考虑自刀队友（骗解药/做身份）等高级战术。

简要讨论明天白天配合：被质疑时保持中立或倒钩做身份，避免强保。是否需要悍跳预言家？

**要求**：1-2句话直奔主题，重点是刀人目标。
"""
            else:  # English
                phase_instruction = f"""
# Werewolf Private Night Discussion
You and teammates ({teammates_str}) are discussing privately. Village can't see this.

**Core task**: Decide tonight's kill target. Priority: Seer > Witch > Hunter > Strong villagers.
Consider advanced tactics: self-knife a teammate (bait antidote/gain trust).

Brief daytime planning: if questioned, stay neutral or bus for credibility. Need to fake-claim Seer?

**Requirements**: 1-2 sentences, get to the point. Focus on kill target.
"""
        else:
            # 普通白天发言 - 根据发言位置提供不同策略
            speech_position = (game.current_speech_index or 0) + 1  # 第几个发言（1-based）
            total_speakers = len(game.speech_order or [])
            player_count = len(game.players)

            # P1优化：预言家白天发言时的强制起跳提醒
            seer_reveal_reminder = ""
            if player.role.value == "seer":
                has_wolf_check = any(is_wolf for is_wolf in (player.verified_players or {}).values())
                if has_wolf_check:
                    wolf_seats = [str(s) for s, is_wolf in player.verified_players.items() if is_wolf]
                    if language == "zh":
                        seer_reveal_reminder = f"""
🚨 **你手握查杀（{', '.join(wolf_seats)}号是狼人）！必须本轮跳预言家身份报出查杀！不跳=好人全黑=输。**
"""
                    else:
                        seer_reveal_reminder = f"""
🚨 **You have wolf check (#{', #'.join(wolf_seats)} is wolf)! MUST claim Seer and report this speech! Not claiming = village blind = lose.**
"""
                elif player_count >= 12:
                    if language == "zh":
                        seer_reveal_reminder = """
📢 12人局建议首日起跳预言家，建立信任、避免被刀后好人全黑。报金水也能引导阵营。
"""
                    else:
                        seer_reveal_reminder = """
📢 In 12-player games, Day 1 Seer claim recommended. Build trust and prevent info blackout if killed.
"""

            # 位置策略指导
            if language == "zh":
                if speech_position == 1:
                    position_strategy = f"""你是第 1/{total_speakers} 个发言（首发位）。
你没有前人发言可参考，但你可以设定讨论基调：分析昨晚死亡情况、抛出疑点、提出后续关注方向。首发位是引导讨论的机会，不是劣势。"""
                elif speech_position >= total_speakers - 1:
                    position_strategy = f"""你是第 {speech_position}/{total_speakers} 个发言（后置位）。
你听了几乎所有人的发言，拥有全局视角。你的任务是：找出发言矛盾的人、整合局面信息（谁跳了预言家、金水/查杀是谁）、给出明确判断和站队意见。后置位必须有态度。"""
                else:
                    position_strategy = f"""你是第 {speech_position}/{total_speakers} 个发言（中间位）。
回应前面玩家的观点（认同或质疑），补充他们没注意到的疑点，如果有人跳预言家要表明站边。不要重复别人说过的，要提供新信息。"""

                phase_instruction = f"""
# 当前任务：发言
{seer_reveal_reminder}
{position_strategy}

**要求**：50-150字，像聊天一样说话（不要列点），每句有信息量。可以分析局势、质疑他人、为自己辩护、表明立场。
"""
            else:  # English
                if speech_position == 1:
                    position_strategy = f"""You are speaker 1/{total_speakers} (first position).
No previous speeches to reference, but you set the tone: analyze last night's deaths, raise suspicions, suggest what to watch for. First position is an opportunity, not a disadvantage."""
                elif speech_position >= total_speakers - 1:
                    position_strategy = f"""You are speaker {speech_position}/{total_speakers} (late position).
You've heard almost everyone — use your global perspective. Find contradictions, integrate info (who claimed Seer, gold/kill checks), and give clear judgments. Late speakers must take a stance."""
                else:
                    position_strategy = f"""You are speaker {speech_position}/{total_speakers} (middle position).
Respond to previous speakers (agree or challenge), add suspicions they missed, take a stance if someone claimed Seer. Don't repeat what's been said — provide new information."""

                phase_instruction = f"""
# Current Task: Speech
{seer_reveal_reminder}
{position_strategy}

**Requirements**: 50-150 words, speak conversationally (no bullet points), every sentence must carry information. Analyze, question, defend, or take a stance.
"""
    elif action_type == "vote":
        # 计算场上局势
        alive_count = len(game.get_alive_players())

        # 身份特定策略 (根据语言选择)
        if language == "zh":
            if player.role.value in WOLF_ROLE_VALUES:
                role_specific_strategy = """
**狼人投票**：保命>保队友。队友必死时果断投他做身份（跟好人一起投，表现失望）。投票目标优先级：真预言家>神职>强势村民。不要和队友票型一致。"""
            elif player.role.value == "seer":
                role_specific_strategy = """
**预言家投票**：坚定带队投出查杀。遇悍跳用事实拆解对方逻辑，让金水帮你站队。"""
            elif player.role.value == "witch":
                role_specific_strategy = """
**女巫投票**：隐藏身份，理性站队，不因救人而盲目信任。"""
            elif player.role.value == "hunter":
                role_specific_strategy = """
**猎人投票**：隐藏身份，记录可疑玩家为死后开枪准备。被怀疑可暗示"投我需谨慎"。"""
            else:
                role_specific_strategy = """
**村民投票**：积极推理找狼，保护神职。主流≠正确，跟逻辑不跟情绪。"""

            phase_instruction = f"""
# 当前任务：投票放逐
场上剩余 {alive_count} 人。有查杀优先投查杀，≤5人必须归票。
{role_specific_strategy}
可选目标：{alive_str}（不能投自己，弃票填0）

在 thought 中分析（证据→推断→反证→决策），speak 用 30-80字说理由，action_target 填座位号。
"""
        else:  # English
            if player.role.value in WOLF_ROLE_VALUES:
                role_specific_strategy = """
**Werewolf vote**: Survival > teammates. If teammate is doomed, vote them out (show "disappointment"). Priority: real Seer > power roles > strong villagers. Don't mirror teammates' votes."""
            elif player.role.value == "seer":
                role_specific_strategy = """
**Seer vote**: Lead team to vote out your checked wolves. Counter fake-claims with facts. Rally gold-checked players."""
            elif player.role.value == "witch":
                role_specific_strategy = """
**Witch vote**: Hide identity, vote rationally. Don't blindly trust saved players."""
            elif player.role.value == "hunter":
                role_specific_strategy = """
**Hunter vote**: Hide identity, track suspects for your final shot. If suspected, hint: "Be careful voting me."."""
            else:
                role_specific_strategy = """
**Villager vote**: Actively deduce, protect power roles. Mainstream ≠ correct — follow logic, not emotions."""

            phase_instruction = f"""
# Current Task: Vote for Exile
{alive_count} players alive. Prioritize Seer-checked targets. ≤5 players = must consolidate votes.
{role_specific_strategy}
Available targets: {alive_str} (can't vote yourself; 0 to abstain)

In thought: analyze (evidence → inference → counter-test → decision). In speak: 30-80 words explaining vote. action_target: seat number.
"""
    elif action_type == "kill":
        # 狼人可以击杀任何存活玩家（包括队友，实现自刀策略）
        kill_targets = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in kill_targets])

            # 显示队友的投票情况
            votes_info = ""
            if game.wolf_votes:
                teammate_votes = []
                for seat, target in game.wolf_votes.items():
                    if seat in player.teammates:
                        teammate_votes.append(f"- {seat}号队友投给了 {target}号")
                if teammate_votes:
                    votes_info = "\n\n**队友投票情况**：\n" + "\n".join(teammate_votes) + "\n\n**建议**：和队友保持一致，统一击杀目标。"

            phase_instruction = f"""
# 当前任务：狼人击杀
可选目标：{targets_str}（含狼队友，可自刀骗药/做身份）{votes_info}
建议与队友统一目标。action_target 填座位号。
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in kill_targets])

            # Display teammate votes
            votes_info = ""
            if game.wolf_votes:
                teammate_votes = []
                for seat, target in game.wolf_votes.items():
                    if seat in player.teammates:
                        teammate_votes.append(f"- Teammate #{seat} voted for #{target}")
                if teammate_votes:
                    votes_info = "\n\n**Teammate Votes**:\n" + "\n".join(teammate_votes) + "\n\n**Suggestion**: Coordinate with teammates for unified kill target."

            phase_instruction = f"""
# Current Task: Werewolf Kill
Available targets: {targets_str} (includes wolf teammates for self-knife/bait antidote){votes_info}
Coordinate with teammates. action_target: seat number.
"""
    elif action_type == "verify":
        unverified = [p.seat_id for p in game.get_alive_players()
                     if p.seat_id != player.seat_id and p.seat_id not in (player.verified_players or {})]
        is_first_night = game.day == 1
        player_count = len(game.players)

        # P1优化：构建查验黑名单（低优先级目标）
        blacklist_info = ""
        low_priority_targets = []
        high_priority_targets = []

        for seat_id in unverified:
            quality = _analyze_player_speech_quality(game, seat_id)
            if quality["is_low_priority"]:
                low_priority_targets.append((seat_id, quality["reason"]))
            else:
                high_priority_targets.append(seat_id)

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in unverified])

            # 生成查验历史
            verification_table = ""
            if player.verified_players:
                verification_table = "\n**查验历史**："
                night_counter = 1
                for seat_id, is_wolf in player.verified_players.items():
                    result = "狼人" if is_wolf else "好人"
                    alive_status = "存活" if game.players[seat_id].is_alive else "出局"
                    verification_table += f" 第{night_counter}晚查{seat_id}号={result}({alive_status});"
                    night_counter += 1
                verification_table += "\n"

            # 生成黑名单提示
            if low_priority_targets:
                blacklist_reasons = {
                    "silent": "沉默",
                    "garbled": "乱码",
                    "single_garbled": "仅一次乱码"
                }
                blacklist_items = [f"{s}号({blacklist_reasons.get(r, r)})" for s, r in low_priority_targets]
                blacklist_info = f"\n⚠️ 低价值目标（别查）：{', '.join(blacklist_items)}\n"

            # 检测查杀，提示起跳
            has_wolf_check = any(is_wolf for is_wolf in (player.verified_players or {}).values())
            reveal_reminder = ""
            if has_wolf_check:
                wolf_seats = [str(s) for s, is_wolf in player.verified_players.items() if is_wolf]
                reveal_reminder = f"\n🚨 你已查出狼人（{', '.join(wolf_seats)}号）！明天必须跳预言家报查杀！\n"
            elif player_count >= 12 and game.day == 1:
                reveal_reminder = "\n📢 12人局建议明天首日起跳预言家，建立信任避免被刀后全黑。\n"

            phase_instruction = f"""
# 当前任务：预言家查验
选择一名玩家查验身份。
{verification_table}{blacklist_info}{reveal_reminder}
可选目标：{targets_str}

**查验策略**：禁止查沉默/乱码玩家。优先查：发言激进带节奏者、逻辑矛盾者、投票异常者、被质疑但辩解无力者。

action_target 填座位号。
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in unverified])

            # Generate verification history
            verification_table = ""
            if player.verified_players:
                verification_table = "\n**Check history**:"
                night_counter = 1
                for seat_id, is_wolf in player.verified_players.items():
                    result = "Wolf" if is_wolf else "Villager"
                    alive_status = "alive" if game.players[seat_id].is_alive else "dead"
                    verification_table += f" Night {night_counter}: #{seat_id}={result}({alive_status});"
                    night_counter += 1
                verification_table += "\n"

            # Generate blacklist info
            if low_priority_targets:
                blacklist_reasons = {
                    "silent": "silent",
                    "garbled": "garbled",
                    "single_garbled": "one garbled speech"
                }
                blacklist_items = [f"#{s}({blacklist_reasons.get(r, r)})" for s, r in low_priority_targets]
                blacklist_info = f"\n⚠️ Low-value targets (don't check): {', '.join(blacklist_items)}\n"

            # Check for wolf findings
            has_wolf_check = any(is_wolf for is_wolf in (player.verified_players or {}).values())
            reveal_reminder = ""
            if has_wolf_check:
                wolf_seats = [str(s) for s, is_wolf in player.verified_players.items() if is_wolf]
                reveal_reminder = f"\n🚨 You found wolf(s) (#{', #'.join(wolf_seats)})! Tomorrow MUST claim Seer and report!\n"
            elif player_count >= 12 and game.day == 1:
                reveal_reminder = "\n📢 12-player game: recommend claiming Seer Day 1 to build trust and prevent info blackout.\n"

            phase_instruction = f"""
# Current Task: Seer Verification
Choose a player to verify.
{verification_table}{blacklist_info}{reveal_reminder}
Available targets: {targets_str}

**Strategy**: Never check silent/garbled players. Prioritize: aggressive speakers, contradictory logic, abnormal voters, weakly defended suspects.

action_target: seat number.
"""
    elif action_type == "witch_save":
        is_first_night = game.day == 1
        alive_count = len(game.get_alive_players())
        target_id = game.night_kill_target or ("未知" if language == "zh" else "Unknown")

        if language == "zh":
            phase_instruction = f"""
# 当前任务：女巫救人
今晚 {target_id}号 被狼人杀害。解药全场只能用一次。
首夜默认保留（警惕自刀骗药），除非被刀者明确是关键神职。

救人填 {game.night_kill_target}，不救填 0。
"""
        else:  # English
            phase_instruction = f"""
# Current Task: Witch Save
Player #{target_id} was killed. Antidote is one-time use.
First night: default keep (beware self-knife bait), unless target is clearly a key power role.

Save: fill {game.night_kill_target}. Don't save: fill 0.
"""
    elif action_type == "witch_poison":
        alive_others = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in alive_others])
            phase_instruction = f"""
# 当前任务：女巫毒人
毒药全场只能用一次。宁可不用也不要误毒好人。首夜信息太少不建议使用。
可选目标：{targets_str}

毒人填座位号，不用填 0。
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in alive_others])
            phase_instruction = f"""
# Current Task: Witch Poison
Poison is one-time use. Rather not use than mis-poison a villager. First night: too little info, not recommended.
Available targets: {targets_str}

Poison: fill seat number. Don't use: fill 0.
"""
    elif action_type == "protect":
        alive_all = [p.seat_id for p in game.get_alive_players()]
        # Filter out last night's target (consecutive guard rule)
        protect_choices = [s for s in alive_all if s != game.guard_last_target]

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in protect_choices])
            last_target_hint = f"\n⚠️ 昨晚守护了{game.guard_last_target}号，今晚不能连续守护。" if game.guard_last_target else ""
            phase_instruction = f"""
# 当前任务：守卫守护
选择一名玩家今晚守护，使其免受狼人刀杀（不防毒药）。{last_target_hint}
可选目标：{targets_str}

**守护策略**：优先守护已跳预言家/疑似关键神职 > 发言有价值的活跃玩家 > 自己。
首夜可守自己或跳预言家的人。不确定时可空守（填0）。

action_target 填座位号（空守填 0）。
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in protect_choices])
            last_target_hint = f"\n⚠️ Protected #{game.guard_last_target} last night, cannot protect consecutively." if game.guard_last_target else ""
            phase_instruction = f"""
# Current Task: Guard Protection
Choose a player to protect tonight from werewolf kill (does not block poison).{last_target_hint}
Available targets: {targets_str}

**Strategy**: Prioritize claimed Seer/suspected key power roles > active valuable speakers > yourself.
Night 1: protect yourself or the Seer claimant. If uncertain, skip (fill 0).

action_target: seat number (0 to skip).
"""
    elif action_type == "shoot":
        alive_others = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]
        alive_count = len(game.get_alive_players())

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in alive_others])
            phase_instruction = f"""
# 当前任务：猎人开枪
你已出局，这是你最后的贡献机会！可选目标：{targets_str}
优先带走：确认狼人（查杀/假预言家）> 最大嫌疑 > 站队异常者。避免带走金水/确认好人。

强烈建议开枪！action_target 填座位号（放弃填 0）。
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in alive_others])
            phase_instruction = f"""
# Current Task: Hunter Shoot
You're eliminated — last chance to contribute! Available: {targets_str}
Priority: confirmed wolves (seer-checked/fake seer) > most suspicious > abnormal stance. Avoid gold-checked/confirmed villagers.

Strongly recommend shooting! action_target: seat number (0 to skip).
"""

    # Assemble context with language-specific headers
    # P2优化：为好人阵营添加投票模式分析
    voting_analysis = ""
    if player.role.value not in WOLF_ROLE_VALUES:
        voting_analysis = _build_voting_pattern_analysis(game, player, language)

    if language == "zh":
        context_prompt = f"""# 当前游戏状态
第 {game.day} 天 | 存活：{alive_str} | 出局：{dead_str}
{wolf_plan_context}{voting_analysis}
# 历史发言记录
{chat_str}
{phase_instruction}
❗ 输出纯 JSON，禁止 markdown 标记：{{"thought": "...", "speak": "...", "action_target": ...}}
"""
    else:
        context_prompt = f"""# Current Game State
Day {game.day} | Alive: {alive_str} | Eliminated: {dead_str}
{wolf_plan_context}{voting_analysis}
# Chat History
{chat_str}
{phase_instruction}
❗ Output pure JSON only, no markdown: {{"thought": "...", "speak": "...", "action_target": ...}}
"""

    return context_prompt


def build_wolf_strategy_prompt(player: "Player", game: "Game", language: str = "zh") -> str:
    """Build additional strategy prompt for werewolves."""
    # Normalize language
    language = normalize_language(language)

    # Check if conditions are right for advanced wolf tactics
    strategy_hints = []

    # Check if real seer has claimed (using language-specific patterns)
    seer_claimed = False
    if language == "zh":
        seer_patterns = [
            "我是预言家", "本预言家", "作为预言家",
            "我验了", "我查验", "我昨晚验", "我昨晚查",
            "给了金水", "给了查杀", "验到金水", "验到查杀", "验出狼"
        ]
        negative_patterns = ["不是预言家", "假预言家", "狼人悍跳预言家"]
    else:
        seer_patterns = [
            "I am the seer", "I'm the seer", "as the seer",
            "I checked", "I verified", "last night I checked",
            "gave gold", "gave kill", "found werewolf", "found good"
        ]
        negative_patterns = ["not the seer", "fake seer", "werewolf claiming seer"]

    for msg in game.messages:
        if msg.seat_id != player.seat_id:
            content = msg.content.lower()
            if any(pattern.lower() in content for pattern in seer_patterns):
                if not any(neg.lower() in content for neg in negative_patterns):
                    seer_claimed = True
                    break

    # Scenario 1: Seer has claimed, consider counter-claiming
    if seer_claimed and game.day >= 2:
        if player.seat_id == min((player.teammates or []) + [player.seat_id]):
            strategy_hints.append(t("prompts.wolf_strategy_counter_claim", language=language))

    # Scenario 2: Day 1 and no seer claimed (seer might be dead)
    elif game.day == 1 and not seer_claimed:
        dead_players = [p for p in game.players.values() if not p.is_alive]
        if dead_players:
            # Check if a wolf teammate died on night 1 (self-knife strategy)
            dead_wolves = [p for p in dead_players if p.role.value in WOLF_ROLE_VALUES]
            if dead_wolves:
                # Assign the smallest seat number alive wolf to claim seer
                alive_wolves = [p.seat_id for p in game.players.values()
                               if p.is_alive and p.role.value in WOLF_ROLE_VALUES]
                if alive_wolves and player.seat_id == min(alive_wolves):
                    if language == "zh":
                        strategy_hints.append("""
🚨 队友首夜死亡（疑似自刀）——你必须立即悍跳预言家！给死亡队友发金水或给好人发查杀，利用银水身份做高自己。不跳=白牺牲队友。
""")
                    else:
                        strategy_hints.append("""
🚨 Teammate died Night 1 (suspected self-knife) — MUST fake-claim Seer now! Give gold to dead teammate or kill-check a villager. Leverage silver water status. Not claiming = wasted sacrifice.
""")
            else:
                strategy_hints.append(t("prompts.wolf_strategy_first_claim", language=language))

    # Scenario 3: Mid-game, consider using emotional players
    if game.day >= 2:
        strategy_hints.append(t("prompts.wolf_strategy_emotional", language=language))

    return "\n".join(strategy_hints) if strategy_hints else ""
