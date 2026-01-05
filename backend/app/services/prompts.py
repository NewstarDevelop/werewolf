"""Prompt templates for AI players in Werewolf game."""

from typing import TYPE_CHECKING
from app.i18n import t, normalize_language
from app.services.prompts_templates import SYSTEM_PROMPT_ZH, SYSTEM_PROMPT_EN

if TYPE_CHECKING:
    from app.models.game import Game, Player
    from app.schemas.enums import GamePhase, MessageType


def build_system_prompt(player: "Player", game: "Game", language: str = "zh") -> str:
    """Build the system prompt for an AI player."""
    # Normalize language to ensure consistency
    language = normalize_language(language)

    role_desc = t(f"roles.descriptions.{player.role.value}", language=language)

    # Personality description
    personality_desc = ""
    if player.personality:
        trait_desc = t(f"personality.traits.{player.personality.trait}", language=language)
        style_desc = t(f"personality.styles.{player.personality.speaking_style}", language=language)
        personality_desc = f"""
{t('prompts.your_name', language=language, name=player.personality.name)}
{t('prompts.personality_trait', language=language, trait=trait_desc)}
{t('prompts.speaking_style', language=language, style=style_desc)}
"""

    # Wolf teammates info (only for werewolves)
    wolf_info = ""
    if player.role.value == "werewolf" and player.teammates:
        teammates_str = "、".join([f"{t}号" for t in player.teammates]) if language == "zh" else ", ".join([f"#{t}" for t in player.teammates])
        wolf_info = f"\n{t('prompts.wolf_teammates', language=language, teammates=teammates_str)}\n{t('prompts.wolf_info_note', language=language)}"

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
            elif player.role.value == "werewolf" and msg.seat_id in player.teammates:
                sender = f"{msg.seat_id}{seat_suffix}{teammate_label}"

            # 区分消息类型
            if msg.msg_type.value == "wolf_chat":
                # 只有狼人才能看到狼人私聊
                if player.role.value == "werewolf":
                    chat_history.append(f"{wolf_chat_label} {sender}{colon}{msg.content}")
            else:
                chat_history.append(f"{sender}{colon}{msg.content}")

    chat_str = "\n".join(chat_history) if chat_history else no_messages_label

    # Phase-specific instructions
    phase_instruction = ""
    if action_type == "speech":
        # 检查是否是狼人夜间讨论阶段 (包括狼王和白狼王)
        wolf_roles = {"werewolf", "wolf_king", "white_wolf_king"}
        if game.phase.value == "night_werewolf_chat" and player.role.value in wolf_roles:
            # 狼人夜间讨论专用 prompt
            separator = "、" if language == "zh" else ", "
            seat_suffix = "号" if language == "zh" else ""
            teammates_str = separator.join([f"{t}{seat_suffix}" for t in (player.teammates or [])])

            if language == "zh":
                phase_instruction = f"""
# 当前阶段：夜晚狼人队内讨论
**核心任务**：分析局势并确定今晚的击杀目标

你和狼队友（{teammates_str}）正在夜间私密讨论。这是**夜晚行动阶段**，你们需要：

## 【最高优先级】今晚击杀目标
- [ ] **今晚刀谁？**
  * 优先级：预言家 > 女巫 > 猎人 > 强势村民
  * 理由：这个玩家对我们的威胁是什么？
- [ ] **是否需要自刀策略？**
  * 击杀队友做身份或骗解药（高级战术）

## 【次要优先级】明天白天策略（简要讨论）
- [ ] **如果队友明天被质疑，其他队友应该？**
  * 保持中立 ✅ 或 适度倒钩做身份 ✅
  * 避免强行保护（容易暴露关系）
- [ ] **是否需要悍跳预言家对抗？**
- [ ] **带节奏目标是谁？** 避免多狼同时攻击同一人

**讨论要求**：
- 重要信息：你的队友是 {teammates_str}，你们彼此知道身份
- 发言1-2句话，直奔主题
- **本轮重点是确定今晚刀人目标，其次才是明天演戏策略**
- 这是私密讨论，好人阵营看不到
"""
            else:  # English
                phase_instruction = f"""
# Current Phase: Werewolf Night Discussion
**Core Task**: Analyze the situation and determine tonight's kill target

You and your werewolf teammates ({teammates_str}) are in a private night discussion. This is the **night action phase**, and you need to:

## [Highest Priority] Tonight's Kill Target
- [ ] **Who should we kill tonight?**
  * Priority: Seer > Witch > Hunter > Strong Villagers
  * Reason: What threat does this player pose to us?
- [ ] **Do we need a self-kill strategy?**
  * Kill a teammate to gain trust or bait the witch's antidote (advanced tactic)

## [Secondary Priority] Tomorrow's Daytime Strategy (Brief Discussion)
- [ ] **If a teammate is questioned tomorrow, what should others do?**
  * Stay neutral ✅ or Moderately distance yourself ✅
  * Avoid strong defense (easy to expose relationship)
- [ ] **Do we need to counter-claim as seer?**
- [ ] **Who to lead the vote against?** Avoid multiple wolves attacking the same person

**Discussion Requirements**:
- Important info: Your teammates are {teammates_str}, you all know each other's identities
- Keep it brief (1-2 sentences), get to the point
- **This round's focus is determining tonight's kill target, then tomorrow's strategy**
- This is a private discussion, the village team cannot see it
"""
        else:
            # 普通白天发言 - 根据发言位置提供不同策略
            speech_position = (game.current_speech_index or 0) + 1  # 第几个发言（1-based）
            total_speakers = len(game.speech_order or [])

            # 位置策略指导
            if language == "zh":
                if speech_position == 1:
                    position_strategy = """
**首发位策略（你是第一个发言）**：
- **信息量有限**：你之前没有任何人的发言可以参考
- **设定基调**：你的发言会影响后续玩家的思路和节奏
- **谨慎表态**：
  - 如果你是预言家，可以选择跳或不跳（视局势而定）
  - 如果你是狼人，不要过早暴露队友，先观察
  - 如果你是村民，可以抛出一些疑点引导讨论
- **建议内容**：
  - 总结夜晚结果（谁死了、怎么死的）
  - 提出1-2个疑点或观察
  - 不要过早站队或下死结论
"""
                elif speech_position >= total_speakers - 1:
                    position_strategy = f"""
**后置位策略（你是第 {speech_position}/{total_speakers} 个发言）**：
- **总结能力**：你听到了几乎所有人的发言，拥有全局视角
- **找矛盾**：
  - 谁的发言前后矛盾？
  - 谁在刻意避开某些话题？
  - 谁的逻辑站不住脚？
- **整合信息**：
  - 梳理当前局面：谁跳预言家了、金水是谁、查杀是谁
  - 归纳不同阵营的发言特点
  - 指出最可疑的1-2个人
- **明确立场**：
  - 后置位有责任给出清晰判断
  - 如果你是预言家还没跳，现在应该考虑是否跳出来
  - 如果你是狼人，要做好身份、跟随主流或带节奏
- **优势**：你可以回应之前所有人的发言，说服力更强
"""
                else:
                    position_strategy = f"""
**中间位策略（你是第 {speech_position}/{total_speakers} 个发言）**：
- **平衡信息**：你既有部分发言可参考，又不用总结全局
- **回应前者**：
  - 认同或质疑前面玩家的观点
  - 指出前面发言的逻辑漏洞或可疑之处
  - 如果有人跳预言家，表明你的站边倾向
- **补充视角**：
  - 提出前面玩家没注意到的疑点
  - 从不同角度分析局势
  - 如果你有关键信息（如预言家验人结果），考虑是否公开
- **避免重复**：不要重复前面玩家已经说过的内容，要有新信息
- **保持灵活**：后面还有玩家发言，不要把话说死
"""

                phase_instruction = f"""
# 当前任务：发言
现在轮到你发言了。请根据当前局势和你的发言位置发表看法。

{position_strategy}

**基本要求**：
- 发言长度：50-150字（3-6句话），确保逻辑完整有说服力
- 要符合你的身份和性格
- 可以分析局势、质疑他人、为自己辩护、表明立场等
- 每句话都要有信息量，避免废话
"""
            else:  # English
                if speech_position == 1:
                    position_strategy = """
**First Speaker Strategy (You speak first)**:
- **Limited information**: You have no previous speeches to reference
- **Set the tone**: Your speech will influence subsequent players' thinking
- **Cautious stance**:
  - If you're the seer, decide whether to claim (depends on situation)
  - If you're a werewolf, don't expose teammates early, observe first
  - If you're a villager, raise some suspicions to guide discussion
- **Suggested content**:
  - Summarize night results (who died, how)
  - Raise 1-2 suspicions or observations
  - Don't take early sides or make absolute conclusions
"""
                elif speech_position >= total_speakers - 1:
                    position_strategy = f"""
**Late Speaker Strategy (You are speaker {speech_position}/{total_speakers})**:
- **Summary ability**: You've heard almost everyone, you have a global perspective
- **Find contradictions**:
  - Who contradicted themselves?
  - Who is deliberately avoiding certain topics?
  - Whose logic doesn't hold up?
- **Integrate information**:
  - Sort out the current situation: who claimed seer, who got gold/kill checks
  - Summarize different camps' speech patterns
  - Point out the 1-2 most suspicious players
- **Clear stance**:
  - Late speakers should provide clear judgments
  - If you're seer and haven't claimed, consider whether to reveal now
  - If you're werewolf, blend in, follow mainstream, or lead voting
- **Advantage**: You can respond to everyone's speech, more persuasive
"""
                else:
                    position_strategy = f"""
**Middle Speaker Strategy (You are speaker {speech_position}/{total_speakers})**:
- **Balanced information**: You have some speeches to reference, but don't need to summarize everything
- **Respond to previous speakers**:
  - Agree or question previous players' views
  - Point out logical flaws or suspicious points
  - If someone claimed seer, express your stance
- **Add perspective**:
  - Raise suspicions previous players missed
  - Analyze from different angles
  - If you have key info (seer results), consider whether to reveal
- **Avoid repetition**: Don't repeat what others already said, provide new information
- **Stay flexible**: More players will speak after you, don't be absolute
"""

                phase_instruction = f"""
# Current Task: Speech
It's your turn to speak. Analyze the situation and share your thoughts based on your speaking position.

{position_strategy}

**Basic requirements**:
- Speech length: 50-150 words (3-6 sentences), ensure complete and persuasive logic
- Match your role and personality
- Can analyze situation, question others, defend yourself, express stance, etc.
- Every sentence should have substance, avoid filler
"""
    elif action_type == "vote":
        # 计算场上局势
        alive_count = len(game.get_alive_players())

        # 身份特定策略 (根据语言选择)
        if language == "zh":
            if player.role.value == "werewolf":
                role_specific_strategy = """
**狼人投票策略（极其重要）**：

**核心原则**：保命优先，队友其次。绝不能为了保护队友而暴露自己！

**队友保护决策树**：
1. **判断队友生存几率**：被查杀+多人质疑=必死 → 果断投他（倒钩做身份）
2. **评估保护风险**：为队友辩护会暴露关系吗？风险高=放弃队友
3. **倒钩技巧**：跟随2-3个好人后再投，表现出"失望""被骗"等情绪
4. **间接保护**：转移话题、提出其他疑点，不要直接辩护
5. **带节奏**：等好人先质疑，你再跟随；寻找替罪羊而非保护队友
6. **票型伪装**：偶尔投狼队友，制造你们不是一伙的假象
7. **目标优先级**：真预言家 > 女巫/猎人 > 强势村民 > 避免金水玩家

**最终提醒**：深水狼价值远大于冲锋狼，活到最后才能赢
"""
            elif player.role.value == "seer":
                role_specific_strategy = """
**预言家投票策略**：
- 坚定带队投出查杀
- 通过逻辑证明自己是真预
- 利用金水玩家帮你站队
"""
            elif player.role.value == "witch":
                role_specific_strategy = """
**女巫投票策略**：
- 隐藏身份，避免被狼针对
- 理性站队，不因救人而盲目信任
"""
            elif player.role.value == "hunter":
                role_specific_strategy = """
**猎人投票策略**：
- 绝对隐藏身份
- 记录可疑玩家，为死后开枪准备
"""
            else:  # villager
                role_specific_strategy = """
**村民投票策略**：
- 积极推理找狼
- 保护神职，相信真预言家
- 主流≠正确：判断你跟的是逻辑还是情绪
"""

            phase_instruction = f"""
# 当前任务：投票放逐
现在是投票阶段，你需要选择一名玩家投票放逐。

**局势分析**：
- 场上剩余 {alive_count} 人
- 投票至关重要：投错人可能导致局势逆转

**通用策略**：
1. 优先投出发言最可疑、逻辑最混乱的玩家
2. 如果有预言家查杀，优先投查杀对象
3. 关键回合（≤5人）必须归票
{role_specific_strategy}

**决策要求**：
- 在 thought 中完成结构化分析（目标、证据、推断、反证、决策）
- 在 speak 中用 30-80字说明投票理由
- 在 action_target 中填写座位号（不能投自己；弃票填0）

可选目标：{alive_str}（不能投自己）
"""
        else:  # English
            if player.role.value == "werewolf":
                role_specific_strategy = """
**Werewolf Voting Strategy**:

**Core Principle**: Survival first, teammates second. Never expose yourself to protect teammates!

**Key Tactics**:
1. **Assess teammate's survival chance**: If checked by seer + multiple accusations = doomed → Vote them (gain trust)
2. **Risk assessment**: Will defending expose your relationship? High risk = abandon teammate
3. **Distancing tactics**: Follow 2-3 villagers before voting, show "disappointment" emotions
4. **Indirect protection**: Redirect attention, don't directly defend
5. **Lead votes**: Wait for villagers to question first, then follow; find scapegoats
6. **Vote pattern disguise**: Occasionally vote wolf teammates to hide relationship
7. **Priority targets**: Real seer > Witch/Hunter > Strong villagers > Avoid gold checks

**Remember**: Deep wolves are more valuable than charging wolves, survive to win
"""
            elif player.role.value == "seer":
                role_specific_strategy = """
**Seer Voting Strategy**:
- Lead team to vote out your checked wolves
- Prove you're real seer through logic
- Use your gold checks to support you
"""
            elif player.role.value == "witch":
                role_specific_strategy = """
**Witch Voting Strategy**:
- Hide your identity to avoid wolf targeting
- Rational stance, don't blindly trust saved players
"""
            elif player.role.value == "hunter":
                role_specific_strategy = """
**Hunter Voting Strategy**:
- Absolutely hide your identity
- Remember suspicious players for your final shot
"""
            else:  # villager
                role_specific_strategy = """
**Villager Voting Strategy**:
- Actively deduce to find wolves
- Protect key roles, trust real seer
- Mainstream ≠ Correct: Judge if you're following logic or emotions
"""

            phase_instruction = f"""
# Current Task: Vote for Exile
You need to vote for a player to exile.

**Situation Analysis**:
- {alive_count} players alive
- This vote is crucial: wrong vote may reverse the situation

**General Strategy**:
1. Prioritize most suspicious, illogical players
2. If seer has checked someone, prioritize that target
3. Critical rounds (≤5 players) must consolidate votes
{role_specific_strategy}

**Requirements**:
- In thought: Complete structured analysis (target, evidence, deduction, verification, decision)
- In speak: Explain your vote in 30-80 words
- In action_target: Fill seat number (can't vote yourself; 0 to abstain)

Available targets: {alive_str} (can't vote yourself)
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
# 当前任务：狼人杀人
现在是夜晚，你和狼队友需要选择今晚要击杀的目标。
可选目标：{targets_str}（包括狼队友，可实现自刀策略）{votes_info}

**注意**：
- 你可以击杀任何存活玩家，包括你的狼队友
- 自刀（击杀队友）可以用来做身份、骗解药等高级策略
- 建议与队友讨论后统一目标

在 action_target 中填写你要击杀的座位号。
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
It's night time. You and your werewolf teammates need to choose tonight's kill target.
Available targets: {targets_str} (including wolf teammates for self-kill strategy){votes_info}

**Note**:
- You can kill any alive player, including your wolf teammates
- Self-kill (killing teammate) can be used for gaining trust or baiting witch's antidote
- Coordinate with teammates for unified target

Fill action_target with the seat number to kill.
"""
    elif action_type == "verify":
        unverified = [p.seat_id for p in game.get_alive_players()
                     if p.seat_id != player.seat_id and p.seat_id not in (player.verified_players or {})]
        is_first_night = game.day == 1

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in unverified])

            # 生成查验历史表格
            verification_table = ""
            if player.verified_players:
                verification_table = "\n# 你的查验历史\n"
                verification_table += "| 夜晚 | 查验对象 | 结果 | 当前状态 |\n"
                verification_table += "|------|---------|------|----------|\n"

                night_counter = 1
                for seat_id, is_wolf in player.verified_players.items():
                    result = "狼人" if is_wolf else "好人"
                    alive_status = "存活" if game.players[seat_id].is_alive else "已出局"
                    verification_table += f"| 第{night_counter}晚 | {seat_id}号 | {result} | {alive_status} |\n"
                    night_counter += 1

            phase_instruction = f"""
# 当前任务：预言家查验
现在是夜晚，你可以查验一名玩家的身份。
{verification_table}
可选目标：{targets_str}

**查验策略**：
- 第一晚：发言激进者、边缘位置
- 后续晚上：发言矛盾者、模糊划水者、投票异常者
- 优先查验：发言可疑+站队摇摆+投票异常的玩家

在 action_target 中填写你要查验的座位号。
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in unverified])

            # Generate verification history table
            verification_table = ""
            if player.verified_players:
                verification_table = "\n# Your Verification History\n"
                verification_table += "| Night | Target | Result | Current Status |\n"
                verification_table += "|-------|--------|--------|----------------|\n"

                night_counter = 1
                for seat_id, is_wolf in player.verified_players.items():
                    result = "Wolf" if is_wolf else "Villager"
                    alive_status = "Alive" if game.players[seat_id].is_alive else "Eliminated"
                    verification_table += f"| Night {night_counter} | #{seat_id} | {result} | {alive_status} |\n"
                    night_counter += 1

            phase_instruction = f"""
# Current Task: Seer Verification
It's night time. You can verify a player's identity.
{verification_table}
Available targets: {targets_str}

**Verification Strategy**:
- First night: Aggressive speakers, edge positions
- Later nights: Contradictory speakers, silent players, abnormal voters
- Priority: Suspicious speech + wavering stance + abnormal voting

Fill action_target with the seat number to verify.
"""
    elif action_type == "witch_save":
        is_first_night = game.day == 1
        alive_count = len(game.get_alive_players())
        target_id = game.night_kill_target or ("未知" if language == "zh" else "Unknown")

        if language == "zh":
            phase_instruction = f"""
# 当前任务：女巫救人
今晚 {target_id}号 被狼人杀害。你有解药，是否要救他？

**解药使用策略**：
- 解药全场只能用一次
- 首夜默认保留，除非被刀者是明确的关键角色
- 警惕狼人自刀骗药

**决定**：
- 如果要救，在 action_target 中填写 {game.night_kill_target}
- 如果不救，填写 0
"""
        else:  # English
            phase_instruction = f"""
# Current Task: Witch Save
Tonight player #{target_id} was killed by werewolves. You have antidote, will you save them?

**Antidote Strategy**:
- Antidote can only be used once per game
- First night: save by default, unless target is clearly a key role
- Beware of werewolf self-kill to waste your antidote

**Decision**:
- To save: Fill action_target with {game.night_kill_target}
- Not to save: Fill 0
"""
    elif action_type == "witch_poison":
        alive_others = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in alive_others])
            phase_instruction = f"""
# 当前任务：女巫毒人
你有毒药，是否要使用？
可选目标：{targets_str}

**重要警告**：
- 毒药全场只能用一次
- 不要轻易在第一晚使用，信息太少易误毒好人
- 只在有充分证据时使用

**决定**：
- 如果要毒人，在 action_target 中填写目标座位号
- 如果不确定，填写 0（不使用）
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in alive_others])
            phase_instruction = f"""
# Current Task: Witch Poison
You have poison, will you use it?
Available targets: {targets_str}

**Warning**:
- Poison can only be used once per game
- Don't use on first night easily, too little info may poison villagers
- Only use with solid evidence

**Decision**:
- To poison: Fill action_target with seat number
- If uncertain: Fill 0 (don't use)
"""
    elif action_type == "shoot":
        alive_others = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]
        alive_count = len(game.get_alive_players())

        if language == "zh":
            targets_str = "、".join([f"{s}号" for s in alive_others])
            phase_instruction = f"""
# 当前任务：猎人开枪
你已出局，可以开枪带走一名玩家（最后机会为好人阵营做贡献）。
可选目标：{targets_str}

**开枪目标优先级**：
1. 确定的狼人（被真预言家查杀、假预言家）
2. 场上最大嫌疑（发言矛盾、带节奏、投票异常）
3. 站队异常者
4. 避免：金水玩家、明确好人

**决定**：
- 如果要开枪，在 action_target 中填写目标座位号
- 强烈建议不要放弃开枪（填0）
"""
        else:  # English
            targets_str = ", ".join([f"#{s}" for s in alive_others])
            phase_instruction = f"""
# Current Task: Hunter Shoot
You're eliminated. You can shoot a player (last chance to help villagers).
Available targets: {targets_str}

**Target Priority**:
1. Confirmed wolves (checked by real seer, fake seer)
2. Most suspicious (contradictory speech, leading votes, abnormal voting)
3. Abnormal stance
4. Avoid: Gold-checked players, confirmed villagers

**Decision**:
- To shoot: Fill action_target with seat number
- Strongly recommend don't skip (filling 0)
"""

    # Assemble context with language-specific headers
    if language == "zh":
        context_prompt = f"""# 当前游戏状态
第 {game.day} 天
存活玩家：{alive_str}
已出局玩家：{dead_str}

# 历史发言记录
{chat_str}
{phase_instruction}

**CRITICAL: 输出格式要求**
- 必须输出纯 JSON 对象，不要包含任何 markdown 代码块标记（如 ```json）
- 不要添加任何解释性文字或额外内容
- JSON 格式: {{"thought": "...", "speak": "...", "action_target": ...}}
"""
    else:
        context_prompt = f"""# Current Game State
Day {game.day}
Alive players: {alive_str}
Eliminated players: {dead_str}

# Chat History
{chat_str}
{phase_instruction}

**CRITICAL: Output Format Requirements**
- MUST output pure JSON object, do NOT include any markdown code block markers (like ```json)
- Do NOT add any explanatory text or extra content
- JSON format: {{"thought": "...", "speak": "...", "action_target": ...}}
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
            strategy_hints.append(t("prompts.wolf_strategy_first_claim", language=language))

    # Scenario 3: Mid-game, consider using emotional players
    if game.day >= 2:
        strategy_hints.append(t("prompts.wolf_strategy_emotional", language=language))

    return "\n".join(strategy_hints) if strategy_hints else ""
