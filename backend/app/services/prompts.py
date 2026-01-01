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

    # Select template based on language
    template = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ZH

    system_prompt = f"""{t('prompts.game_intro', language=language)}
{t('prompts.your_role', language=language, role=role_desc)}
{t('prompts.your_seat', language=language, seat_id=player.seat_id)}
{personality_desc}
{template.format(wolf_info=wolf_info, seer_info=seer_info, witch_info=witch_info, language_instruction=language_instruction)}
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
        # 检查是否是狼人夜间讨论阶段
        if game.phase.value == "night_werewolf_chat" and player.role.value == "werewolf":
            # 狼人夜间讨论专用 prompt
            teammates_str = "、".join([f"{t}号" for t in (player.teammates or [])])
            phase_instruction = f"""
# 当前任务：狼人队内讨论
现在是夜晚，你和狼队友正在私下讨论今晚的击杀目标和明天的策略。

**重要信息**：
- 你的队友是：{teammates_str}
- **所有参与讨论的玩家都是狼人，你们彼此都知道对方的身份**
- 这是狼人队内的私密讨论，好人阵营看不到
- 讨论内容应该围绕：分析局势、选择击杀目标、制定白天演戏策略

# 必须讨论的战术清单（步骤5：结构化协同）
在发言前，必须在 thought 中评估以下问题，并在 speak 中至少回应其中 2 个：

---
## 战术优先级清单

### 【优先级1】逻辑漏洞识别与利用（最重要！）
- [ ] **真预言家今天有没有出现逻辑失误？**
  * 例如：前后矛盾、记错信息、查验顺序不合理
  * 如果有，这是我们的机会！必须讨论如何利用
- [ ] **我们如何统一攻击这个逻辑漏洞？**
  * 谁来主攻？谁来补刀？谁保持中立？
  * 避免所有狼人同时攻击同一点（容易暴露）
- [ ] **有没有好人因为情绪化而错误站边？**
  * 我们可以顺着他的情绪推波助澜

### 【优先级2】击杀目标确认
- [ ] **今晚刀谁？**（优先级：预言家 > 女巫 > 猎人 > 强势村民）
- [ ] **是否需要自刀做身份或骗药？**

### 【优先级3】明天白天的分工策略
- [ ] **如果某个队友明天被质疑，其他队友的态度是？**
  * A. 强行保护 ❌（容易暴露）
  * B. 保持中立 ✅
  * C. 适度质疑（倒钩做身份）✅
- [ ] **带节奏的目标是谁？**（选一个发言模糊的好人）
- [ ] **谁来带节奏？**（避免多人同时攻击）

### 【优先级4】票型伪装
- [ ] **明天投票时是否要分票？**（避免全员投同一人）
- [ ] **如果队友嫌疑大，谁适合倒钩？**

### 【可选】高级战术
- [ ] 是否需要悍跳预言家对抗？
- [ ] 是否考虑卖队友（Bus）战术？（仅在真预言家疑似已死时）

---

**讨论要求**：
- 发言简短（1-2句话），直奔主题
- 你们是队友，不要表现出惊讶对方是狼人
- **重点讨论如何避免白天暴露关系**（禁止说"一起保护X号"，要说"该投就投"）
"""
        else:
            # 普通白天发言 - 根据发言位置提供不同策略
            speech_position = (game.current_speech_index or 0) + 1  # 第几个发言（1-based）
            total_speakers = len(game.speech_order or [])

            # 位置策略指导
            position_strategy = ""
            if speech_position == 1:
                # 首发位
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
                # 后置位（倒数第1-2个）
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
                # 中间位
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
    elif action_type == "vote":
        # 计算场上局势
        alive_count = len(game.get_alive_players())

        # 身份特定策略
        role_specific_strategy = ""
        if player.role.value == "werewolf":
            role_specific_strategy = """
**狼人投票策略（极其重要）**：

**核心原则**：保命优先，队友其次。绝不能为了保护队友而暴露自己！

**队友保护决策树（必须严格遵守）**：

1. **判断队友的生存几率**：
   - 如果队友被预言家查杀 + 多人质疑 = 必死无疑 → **果断投他（倒钩做身份）**
   - 如果队友嫌疑很大但还有辩解空间 → **保持沉默或跟随主流，不要强行辩护**
   - 如果队友只是轻微被质疑 → **可以适度帮忙，但要装作客观分析，不能显得刻意**
   - 如果队友完全没被怀疑 → **不需要保护，正常讨论其他人即可**

2. **评估保护的风险**：
   - 如果你为队友辩护，会不会让好人觉得你们是一伙的？
   - 如果场上有多人都在质疑队友，你逆着大势为他说话会很可疑
   - 如果你前面的发言已经站在了反对队友的一边，现在突然改口会很矛盾
   - **风险高 = 放弃队友；风险低 = 可以间接帮忙**

3. **倒钩（投狼队友）的时机和好处**：
   - **什么时候必须倒钩**：队友被查杀、证据确凿、大势已去、你再保护就会一起死
   - **倒钩的好处**：做身份、获得好人信任、保护其他深水狼、延长生存时间
   - **倒钩技巧**：不要第一个投，跟随2-3个好人后再投，显得你是被说服的
   - **倒钩后的演技**：表现出"痛心""被骗""愤怒"等情绪，增强真实感

4. **间接保护技巧**（安全的保护方式）**：
   - **转移话题**："我觉得X号更可疑，他昨天投票很奇怪"
   - **提出疑点**："除了队友，我还注意到Y号一直在划水"
   - **模糊立场**："队友确实有点可疑，但Z号也说不清楚"
   - **不要直接为队友辩护**："队友是好人！你们都错了！"（这是暴露信号）

5. **带节奏技巧**：
   - **不要第一个提出投某人**，等好人先质疑，你再跟随附和
   - **适度质疑真预言家**，但不要太激进（"我有点怀疑他的查验逻辑"）
   - **寻找替罪羊**：找一个发言模糊的好人，带节奏投他而不是队友
   - **关键时刻保持中立**：如果场上分歧很大，你可以说"我还需要再想想"

6. **票型伪装**：
   - **偶尔投狼队友**，制造你们不是一伙的假象（特别是队友嫌疑不大时）
   - **不要总是和队友投同一个人**，这会暴露你们的关系
   - **观察好人的投票倾向**，跟随大部分好人的选择

7. **目标选择优先级**：
   - 最优：真预言家（如果能推出去）
   - 次优：女巫、猎人等强势神职
   - 可选：逻辑清晰、带队能力强的村民
   - 避免：明显的好人、金水玩家（推他们会暴露你）

**示例场景**：

场景A：队友被预言家查杀，3个好人都在质疑他
- **正确做法**：跟随好人投队友，表现出"失望""被骗"的情绪
- **错误做法**：强行为队友辩护"他不可能是狼！预言家才是假的！"

场景B：队友稍微被1-2个人质疑，但证据不足
- **正确做法**：转移话题"我觉得X号更可疑"，或者保持沉默
- **错误做法**：直接跳出来"队友绝对是好人！"

场景C：队友完全没被怀疑，但场上有其他人被质疑
- **正确做法**：正常讨论，投那个被质疑的好人
- **错误做法**：刻意提起队友"我觉得队友是好人"（没人问你，你为什么提？）

**最终提醒**：
- 狼人能赢不是因为保护队友，而是因为隐藏身份、带节奏、推好人
- 如果你因为保护队友而暴露，那队友的牺牲就白费了
- 深水狼的价值远大于冲锋狼，活到最后才能赢
"""
        elif player.role.value == "seer":
            role_specific_strategy = """
**预言家投票策略（重要）**：
- **坚定带队**：如果你已跳身份，要强势带队投出查杀
- **保护自己**：如果有假跳，要通过逻辑证明自己是真预
- **报验时机**：投票前可以报出新的查验结果，增强说服力
- **金水利用**：让你的金水玩家帮你发言、站队、冲锋
- **遗言准备**：如果你即将被投出，提前在发言中留下关键信息
"""
        elif player.role.value == "witch":
            role_specific_strategy = """
**女巫投票策略（重要）**：
- **隐藏身份**：不要暴露你是女巫，避免被狼人针对
- **理性站队**：根据逻辑判断，不要因为救过某人就盲目相信他
- **毒药威慑**：必要时可以暗示"我有办法处理XX"，但不要明说
- **银水价值**：如果你救过某人，他的身份会更可信（但警惕狼自刀）
"""
        elif player.role.value == "hunter":
            role_specific_strategy = """
**猎人投票策略（重要）**：
- **绝对隐藏**：永远不要暴露猎人身份，让狼人误以为你是民
- **保持活跃**：适度发言和投票，不要太划水也不要太跳
- **记录信息**：记住所有可疑玩家，为死后开枪做准备
- **不怕被刀**：即使被刀也能开枪，所以可以勇敢发言
"""
        else:  # villager
            role_specific_strategy = """
**村民投票策略（重要）**：
- **积极推理**：虽然没有特殊能力，但可以通过逻辑分析找狼
- **保护神职**：相信真预言家，保护好人阵营的关键角色
- **主流≠正确**：
  * 当主流由 1-2 个强势玩家驱动时，必须先判断其动机与收益
  * 若你跟票，必须在 thought 中写清：你跟的是**逻辑链**还是**音量/情绪**
  * 若是后者（音量/情绪），必须降权并提出反证问题
- **发挥价值**：通过发言和投票，帮助好人阵营找出狼人
"""

        phase_instruction = f"""
# 当前任务：投票放逐
现在是投票阶段，你需要选择一名玩家投票放逐。

**局势分析**：
- 场上剩余 {alive_count} 人
- 今天的投票至关重要：投错人可能导致局势逆转
- 根据已有信息推断剩余狼人数量，评估好人是领先还是落后

**通用投票策略**：
1. 优先投出发言最可疑、逻辑最混乱的玩家
2. 如果有预言家查杀，优先考虑投查杀对象
3. 注意观察谁在带节奏、谁在保护可疑玩家
4. **归票时机判断**：
   - 关键回合（存活≤5人 或 狼人数≥好人数-1）必须归票，避免票散导致投不出去
   - 普通回合如果有明确查杀或强势共识，也应该跟票归票
   - 如果场上意见分散且无强势主导，可以自主投票
{role_specific_strategy}

# 投票决策表（必填 - 步骤4：强制逻辑链验证）
你必须在 thought 中按以下格式完成结构化分析：

---
## 投票决策分析（6步验证法）
1. **我要投的目标**：____号

2. **证据1（可核查的事实）**：
   - 他在第__天/轮说了："____"（引用原话或概括）
   - 或：他在第__轮投了__号（投票记录）
   - 或：他的__行为（具体描述）

3. **证据2（可核查的事实）**：
   - 他的____行为与____矛盾
   - 或：他回避了____关键问题
   - 或：他____（另一个可观察的事实）

4. **推断结论**：
   - 基于证据1和2，我认为他____（是狼人/假预言家/带节奏/可疑）

5. **反证检验**（关键步骤 - 避免情绪化决策）：
   - 如果他不是狼人，证据1可以解释为：____
   - 如果他不是狼人，证据2可以解释为：____
   - 他有没有做过对好人有利的事？（例如：____）

6. **最终决策**：
   - 经过反证检验，我____（仍然投他 / 改投____号 / 弃票观望）
   - 理由：____
---

**严格要求**：
- 必须填写完整的 6 个步骤
- 证据必须是可核查的事实（发言内容、投票记录、出局信息），禁止使用"我觉得"、"感觉"
- 如果找不到 2 条证据，必须在步骤 6 中说明"证据不足，我选择____（跟随主流/随机/弃票）"
- **禁止因为单一错误就全盘否定一个玩家**（例如：预言家说错一个信息不代表他是假的）

**决策要求**：
- 在 thought 中完成上述 6 步分析
- 在 speak 中用 30-80字 说明你的投票理由（简明有力，会被其他玩家看到）
- 在 action_target 中填写你要投票的座位号（不能投自己；弃票填0）

可选目标：{alive_str}（不能投自己）
"""
    elif action_type == "kill":
        # 狼人可以击杀任何存活玩家（包括队友，实现自刀策略）
        kill_targets = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]
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

        # 生成出局玩家历史（步骤3：辅助狼人制定击杀策略）
        dead_players_info = ""
        dead_players = [p for p in game.players.values() if not p.is_alive]
        if dead_players:
            dead_players_info = "\n# 已出局玩家列表（参考避免重复击杀同类型）\n"
            dead_players_info += "| 座位号 | 角色（如已知） | 备注 |\n"
            dead_players_info += "|--------|-------------|------|\n"
            for dp in dead_players:
                # 狼人可以看到所有出局玩家，但角色仅在明确暴露时显示
                role_display = "未知"
                if dp.role.value == "werewolf":
                    role_display = "狼人（队友）"
                # 如果玩家生前明确暴露身份，可以在这里显示（简化版本先显示"未知"）
                dead_players_info += f"| {dp.seat_id}号 | {role_display} | 第{game.day}天前出局 |\n"
            dead_players_info += "\n**参考建议**：优先击杀未出局的神职，避免浪费刀在已知狼人或低价值目标上\n"

        phase_instruction = f"""
# 当前任务：狼人杀人
现在是夜晚，你和狼队友需要选择今晚要击杀的目标。
{dead_players_info}
可选目标：{targets_str}（包括狼队友，可实现自刀策略）{votes_info}

**注意**：
- 你可以击杀任何存活玩家，包括你的狼队友
- 自刀（击杀队友）可以用来做身份、骗解药等高级策略
- 建议与队友讨论后统一目标

在 action_target 中填写你要击杀的座位号。
"""
    elif action_type == "verify":
        unverified = [p.seat_id for p in game.get_alive_players()
                     if p.seat_id != player.seat_id and p.seat_id not in (player.verified_players or {})]
        targets_str = "、".join([f"{s}号" for s in unverified])
        is_first_night = game.day == 1

        # 生成查验历史表格（步骤1：结构化记忆）
        verification_table = ""
        if player.verified_players:
            verification_table = "\n# 你的查验历史（必须参考此表，禁止凭记忆）\n"
            verification_table += "| 夜晚 | 查验对象 | 结果 | 当前状态 |\n"
            verification_table += "|------|---------|------|----------|\n"

            # 按查验顺序生成表格（使用 game.day 推算夜晚顺序）
            night_counter = 1
            for seat_id, is_wolf in player.verified_players.items():
                result = "狼人" if is_wolf else "好人"
                alive_status = "存活" if game.players[seat_id].is_alive else "已出局"
                verification_table += f"| 第{night_counter}晚 | {seat_id}号 | {result} | {alive_status} |\n"
                night_counter += 1

            verification_table += "\n**严格规则**：\n"
            verification_table += "- 在 speak 中引用查验结果时，必须直接复制上表内容\n"
            verification_table += "- 在 thought 中必须写明：'根据上表，第X晚查验Y号，结果是Z'\n"
            verification_table += "- 禁止凭记忆！如果不确定，重新查看上表\n"
            verification_table += "- 每次报验前，先在 thought 中自检：'我确定是第几晚查验的谁吗？'\n"

        phase_instruction = f"""
# 当前任务：预言家查验
现在是夜晚，你可以查验一名玩家的身份。
{verification_table}
可选目标：{targets_str}

**查验策略指南**：

**第一晚查验建议**{"（当前就是第一晚）" if is_first_night else ""}：
1. **发言激进者**：白天如果有人发言特别激进或带节奏，优先查验
2. **边缘位置参考**：座位号边角位可作为参考，但不是绝对标准
3. **随机性**：第一晚信息有限，可适当随机选择

**后续晚上查验建议**：
1. **发言矛盾者**：前后发言逻辑不一致、站队突然变化的玩家
2. **模糊划水者**：全程不表态、跟随主流意见、没有明确立场
3. **保护特定玩家者**：刻意为某人开脱、转移话题的玩家
4. **投票异常者**：投票与发言不符、关键时刻弃票或站错队

**查验价值排序**：
- 高价值：发言可疑+站队摇摆+投票异常+单边权威的高度绑定者
- 中价值：划水摸鱼+模糊表态+拙劣表水但收益巨大者
- 低价值：明确站队好人+逻辑清晰+发言正常

**特殊情况**：
- 如果场上有悍跳预言家，优先查验他给出的金水/查杀对象
- 如果某玩家被多人质疑，可以查验后第二天报出结果
- 避免重复查验已知身份玩家，浪费查验机会

在 action_target 中填写你要查验的座位号。
"""
    elif action_type == "witch_save":
        # 计算当前天数和局势
        is_first_night = game.day == 1
        alive_count = len(game.get_alive_players())
        target_id = game.night_kill_target or "未知"

        # 生成药水状态表格（步骤2：结构化记忆）
        potion_status = "\n# 你的药水状态（决策前必须确认）\n"
        potion_status += "| 药水类型 | 剩余数量 | 状态说明 |\n"
        potion_status += "|---------|---------|----------|\n"
        save_status = "1瓶（可用）" if player.has_save_potion else "0瓶（已使用）"
        poison_status = "1瓶（可用）" if player.has_poison_potion else "0瓶（已使用）"
        potion_status += f"| 解药 | {save_status} | {'本轮可使用' if player.has_save_potion else '已无法使用'} |\n"
        potion_status += f"| 毒药 | {poison_status} | {'本轮可使用' if player.has_poison_potion else '已无法使用'} |\n"
        potion_status += "\n**严格规则**：\n"
        potion_status += "- 在 thought 中决策前，必须先确认上表中的剩余数量\n"
        potion_status += "- 如果解药显示'0瓶'，禁止填写救人目标\n"
        potion_status += "- 同一晚使用解药后，当晚无法使用毒药\n"

        phase_instruction = f"""
# 当前任务：女巫救人
今晚 {target_id}号 被狼人杀害。
你有解药，是否要救他？
{potion_status}

**解药使用策略（非常重要）**：
- 解药全场只能用一次，用完就永远没了
- **首夜救人条件式决策**：
  - 默认：首夜保留解药，等待后续救关键角色
  - **例外情况（首夜应该救）**：
    * {target_id}号 在白天发言中明确暴露了预言家、猎人等关键身份
    * {target_id}号 是被真预言家发过金水的高价值玩家
    * {target_id}号 表现出高组织能力/能提供强信息源的特征
  - **风险警惕**：首夜救人需警惕狼人自刀骗药

- **后续晚上救人评估**：
  - 必须在 thought 中分析：救/不救对轮次与信息结构的影响
  - {target_id}号 的价值评估：是否神职？是否能提供关键信息？
  - 场上好人数量是否劣势，必须救人才能保持轮次？

- **不建议救人的情况**：
  - {target_id}号 没有明确表现出神职身份或高价值
  - {target_id}号 是边缘位置的可疑玩家/划水玩家
  - 怀疑是狼人自刀骗解药（多个证据支持）

**当前局势分析**：
- 场上还有 {alive_count} 人存活
- 这是第 {game.day} 天{"（第一晚，默认保留解药，除非被刀者是高价值目标）" if is_first_night else ""}

**决定**：
- 如果要救，在 action_target 中填写 {game.night_kill_target}
- 如果不救，填写 0
- **必须在 thought 中说明你的决策理由**
"""
    elif action_type == "witch_poison":
        alive_others = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]
        targets_str = "、".join([f"{s}号" for s in alive_others])

        # 生成药水状态表格（步骤2：结构化记忆）
        potion_status = "\n# 你的药水状态（决策前必须确认）\n"
        potion_status += "| 药水类型 | 剩余数量 | 状态说明 |\n"
        potion_status += "|---------|---------|----------|\n"
        save_status = "1瓶（可用）" if player.has_save_potion else "0瓶（已使用）"
        poison_status = "1瓶（可用）" if player.has_poison_potion else "0瓶（已使用）"
        potion_status += f"| 解药 | {save_status} | {'本轮可使用' if player.has_save_potion else '已无法使用'} |\n"
        potion_status += f"| 毒药 | {poison_status} | {'本轮可使用' if player.has_poison_potion else '已无法使用'} |\n"
        potion_status += "\n**严格规则**：\n"
        potion_status += "- 在 thought 中决策前，必须先确认上表中的剩余数量\n"
        potion_status += "- 如果毒药显示'0瓶'，必须填写 action_target = 0\n"

        phase_instruction = f"""
# 当前任务：女巫毒人
你有毒药，是否要使用？
{potion_status}
可选目标：{targets_str}

**重要警告**：
- 毒药全场只能用一次，用完就没了，必须谨慎使用
- **不要轻易在第一晚使用毒药**，因为信息太少容易误毒好人
- 只在有**充分证据**时使用（如：预言家查杀+发言可疑、狼人暴露身份等）
- 如果不确定，建议保留毒药到后期再用
- 两个预言家对跳时，**不要立即毒死其中一个**，等白天听发言和逻辑再决定

决定：
- 如果要毒人，在 action_target 中填写目标座位号
- **如果不确定或信息不足，强烈建议填写 0（不使用）**
"""
    elif action_type == "shoot":
        alive_others = [p.seat_id for p in game.get_alive_players() if p.seat_id != player.seat_id]
        targets_str = "、".join([f"{s}号" for s in alive_others])

        # 分析场上局势
        alive_count = len(game.get_alive_players())
        dead_count = 9 - alive_count

        phase_instruction = f"""
# 当前任务：猎人开枪
你已出局，可以开枪带走一名玩家（这是你最后的机会为好人阵营做贡献）。
可选目标：{targets_str}

**开枪目标优先级**：

**最高优先级（必带走）**：
1. **确定的狼人**：
   - 被真预言家查杀的玩家
   - 悍跳预言家的假预言家
   - 狼人自爆或暴露身份的玩家

2. **场上最大嫌疑**：
   - 发言逻辑混乱、前后矛盾的玩家
   - 一直带节奏、误导好人的玩家
   - 投票与发言严重不符的玩家

**中等优先级（可以考虑）**：
3. **站队异常者**：
   - 关键时刻站错队、保护狼人的玩家
   - 全程划水摸鱼、没有贡献的边缘玩家

**低优先级（不建议）**：
4. **金水/明确好人**：
   - 被真预言家发过金水的玩家
   - 发言逻辑清晰、明确站好人队的玩家
   - 已知身份的其他神职（预言家、女巫）

**特殊情况**：
- **场上有对跳预言家**：带走假预言家（根据逻辑判断谁是假的）
- **场上狼人优势**：必须带走最可能是狼的玩家，阻止狼人胜利
- **不确定时**：宁可带走嫌疑最大的，也不要放弃开枪（浪费猎人价值）

**当前局势**：
- 场上剩余 {alive_count} 人，已出局 {dead_count} 人
- 回顾历史发言和投票记录，找出最可疑的玩家

**决定**：
- 如果要开枪，在 action_target 中填写目标座位号
- **强烈建议不要放弃开枪**，除非场上全是明确的好人（极少见）
- 如果实在不确定，选择发言最可疑或最划水的玩家
- 如果放弃开枪，填写 0（但请三思）
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
