from collections.abc import Iterable

TABLE_TALK_TERMS: tuple[str, ...] = (
    "查杀",
    "金水",
    "银水",
    "警徽流",
    "站边",
    "狼坑",
    "倒钩",
    "冲票",
    "深水",
    "抗推",
    "外置位",
    "前置位",
    "后置位",
    "票型",
)

TACTIC_STYLE_HINTS: dict[str, str] = {
    "悍跳": "抢身份视角，给出查杀或金水口径，但别说出真实狼队信息。",
    "倒钩": "轻踩队友或高压位，用票型和发言漏洞做理由。",
    "冲锋": "集中火力归票目标，减少票型分散。",
    "深水": "少跳身份，顺着公共信息补逻辑，降低存在感。",
    "报验人": "稳定复述验人链，说明查杀/金水和警徽流。",
    "盘狼坑": "列发言矛盾、站边变化和票型疑点。",
    "归票": "明确给出今天要出的目标，提醒别分票。",
    "保留身份": "少交底，用信息量和站边态度保护自己。",
}


def phrasebook_prompt_guide() -> str:
    terms = "、".join(TABLE_TALK_TERMS)
    style_lines = "；".join(
        f"{label}：{hint}"
        for label, hint in TACTIC_STYLE_HINTS.items()
    )
    return (
        "局内话术偏好："
        f"优先使用这些狼人杀桌面词：{terms}。"
        "公开发言先给结论，再给一到两个局内理由；不要解释规则给玩家听。"
        f"战术话术参考：{style_lines}。"
    )


def render_checked_wolf_speech(checked_wolf: int) -> str:
    return (
        f"我是预言家，验人链先报清：{checked_wolf}号查杀。"
        f"今天先出{checked_wolf}号，警徽流往外置位顺验，票型别被冲散。"
    )


def render_checked_chain_speech(checked_results: Iterable[tuple[int, str]]) -> str:
    chain = "；".join(
        f"{seat_id}号是{result}"
        for seat_id, result in checked_results
    )
    return (
        f"我是预言家，验人链是：{chain}。"
        "今天先按发言和票型盘狼坑，警徽流留给外置位压力最大的牌。"
    )


def render_tactic_speech(label: str | None, target_seat: int | None = None) -> str | None:
    target = f"{target_seat}号" if target_seat is not None else "外置位"
    if label == "悍跳":
        return (
            f"我先跳预言家，昨晚摸到的信息指向{target}不干净。"
            "今天别散票，先听他怎么解释自己的视角和站边。"
        )
    if label == "倒钩" and target_seat is not None:
        return (
            f"{target}这轮发言我不太认，像是在顺着局势躲压力。"
            "这里先轻踩一下，后面看票型能不能对上。"
        )
    if label == "冲锋" and target_seat is not None:
        return (
            f"我今天想把焦点压在{target}身上，他前后站边变化太快。"
            "这个位置不处理，票型很容易被带散。"
        )
    if label == "深水":
        return (
            "我先不急着定死谁，前置位信息还没完全对上。"
            "今天重点看谁在硬带节奏，别把抗推位打错。"
        )
    if label == "归票" and target_seat is not None:
        return (
            f"我建议今天先归{target}，他的发言和票型都需要交代。"
            "大家别各投各的，先把这一轮信息打出来。"
        )
    if label == "盘狼坑":
        return (
            f"我先盘一下狼坑，{target}的视角最需要解释。"
            "后置位如果没人补强逻辑，这里要进今天的重点怀疑。"
        )
    if label == "保留身份":
        return (
            "我这里先不交太多身份信息，避免晚上被精准处理。"
            "今天主要看发言矛盾和票型，别被单点节奏带走。"
        )
    return None


def render_suspicion_speech(suspected_target: int) -> str:
    return (
        f"我现在更怀疑{suspected_target}号，他的发言和票型需要对齐。"
        "今天先把他的逻辑问清楚，别让焦点散掉。"
    )


def render_default_speech() -> str:
    return (
        "信息还不够，我先听后置位怎么聊。"
        "目前先看站边变化和票型，谁硬带抗推位谁就要进狼坑。"
    )
