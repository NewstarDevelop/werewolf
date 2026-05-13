/**
 * Single source of truth for user-facing strings.
 *
 * Never expose backend code constants (WOLF_KILL / REQUIRE_INPUT / ...) to
 * the UI. Route every action_type through `actionTypeCopy`.
 *
 * Tone guide:
 *   - 日常、清楚、直接: 用玩家平时能立刻理解的话
 *   - 动词优先: 先告诉玩家现在要做什么
 *   - 规则只说必要信息: 避免氛围化、文学化表达
 *   - 高风险操作明确提醒: 击杀、用毒、开枪需要再次确认
 */

import type { ConnectionPhase } from "./ws/client";
import type { RequireInputEnvelope, SubmitActionPayload } from "./types/ws";

type InputActionType = RequireInputEnvelope["data"]["action_type"];
type SubmitActionType = SubmitActionPayload["action_type"];

export interface ActionCopy {
  /** 操作面板顶部"当前"值 */
  title: string;
  /** 动作的核心短句（置于 prompt 之上） */
  heading: string;
  /** 告诉用户现在要做什么（≤ 1 句话） */
  instruction: string;
  /** 确认按钮文案 */
  submitLabel: string;
  /** "danger" 表示 destructive，用朱砂色 */
  tone: "neutral" | "danger";
}

const IDLE_COPY: ActionCopy = {
  title: "等待中",
  heading: "等待操作",
  instruction: "游戏正在进行，轮到你时这里会出现操作。",
  submitLabel: "确认",
  tone: "neutral",
};

export const actionTypeCopy: Record<InputActionType, ActionCopy> = {
  SPEAK: {
    title: "轮到你发言",
    heading: "发言内容",
    instruction: "输入你想说的话。建议简短清楚。",
    submitLabel: "发送发言",
    tone: "neutral",
  },
  VOTE: {
    title: "投票放逐",
    heading: "选择投票目标",
    instruction: "选择你想放逐的玩家。不确定时可以弃票。",
    submitLabel: "提交投票",
    tone: "neutral",
  },
  WOLF_KILL: {
    title: "狼人行动",
    heading: "选择击杀目标",
    instruction: "选择今晚要击杀的玩家。",
    submitLabel: "确认击杀",
    tone: "danger",
  },
  SEER_CHECK: {
    title: "预言家查验",
    heading: "选择查验目标",
    instruction: "选择一位存活玩家查看身份。",
    submitLabel: "确认查验",
    tone: "neutral",
  },
  WITCH_ACTION: {
    title: "女巫行动",
    heading: "选择用药",
    instruction: "解药和毒药各一瓶，每晚最多使用一瓶。",
    submitLabel: "确认选择",
    tone: "neutral",
  },
  HUNTER_SHOOT: {
    title: "猎人开枪",
    heading: "选择开枪目标",
    instruction: "你可以带走一名存活玩家。确认后不能更改。",
    submitLabel: "确认开枪",
    tone: "danger",
  },
};

export const submitActionCopy: Record<SubmitActionType, ActionCopy> = {
  ...actionTypeCopy,
  WITCH_SAVE: {
    title: "使用解药",
    heading: "救人",
    instruction: "使用解药救回昨夜被击杀的玩家。",
    submitLabel: "使用解药",
    tone: "neutral",
  },
  WITCH_POISON: {
    title: "使用毒药",
    heading: "选择毒药目标",
    instruction: "选择今晚要毒杀的玩家。",
    submitLabel: "使用毒药",
    tone: "danger",
  },
  PASS: {
    title: "跳过行动",
    heading: "不使用技能",
    instruction: "本轮不使用技能。",
    submitLabel: "确认跳过",
    tone: "neutral",
  },
};

export function getIdleCopy(): ActionCopy {
  return IDLE_COPY;
}

/** Role code → 中文名。backend 发过来的身份以大写英文传入。 */
export const roleLabelCopy: Record<string, string> = {
  VILLAGER: "平民",
  WOLF: "狼人",
  SEER: "预言家",
  WITCH: "女巫",
  HUNTER: "猎人",
};

export function toRoleLabel(role: string | undefined): string | undefined {
  if (!role) return undefined;
  return roleLabelCopy[role] ?? role;
}

/** 角色技能说明 — 折叠抽屉里给新手看。 */
export interface RoleGuide {
  name: string;
  camp: "wolf" | "good";
  oneLiner: string;
  abilities: string[];
}

export const roleGuides: Record<string, RoleGuide> = {
  WOLF: {
    name: "狼人",
    camp: "wolf",
    oneLiner: "夜晚击杀玩家，白天隐藏身份。",
    abilities: [
      "夜晚：和狼队友一起选择一名玩家击杀。",
      "白天：通过发言隐藏身份，也可以伪装成好人或神职。",
      "胜负：击杀所有平民或所有神职，狼人获胜。",
    ],
  },
  VILLAGER: {
    name: "平民",
    camp: "good",
    oneLiner: "没有技能，主要依靠发言和投票。",
    abilities: [
      "无技能，需要通过发言、投票和信息判断狼人。",
      "白天重点关注发言矛盾、投票变化和身份逻辑。",
      "胜负：狼人全部出局，好人阵营获胜。",
    ],
  },
  SEER: {
    name: "预言家",
    camp: "good",
    oneLiner: "每晚查验一名玩家的身份。",
    abilities: [
      "夜晚：查验一名存活玩家，得知对方是好人还是狼人。",
      "白天：根据查验结果组织发言，选择合适时机公布。",
      "注意：暴露身份后通常会被狼人优先击杀。",
    ],
  },
  WITCH: {
    name: "女巫",
    camp: "good",
    oneLiner: "一瓶解药可以救人，一瓶毒药可以杀人。",
    abilities: [
      "全局只有一瓶解药和一瓶毒药，用完就没有。",
      "每晚最多使用一瓶药，解药不能自救。",
      "用毒前尽量确认目标，误毒好人会很伤。",
    ],
  },
  HUNTER: {
    name: "猎人",
    camp: "good",
    oneLiner: "出局时可以开枪带走一人。",
    abilities: [
      "被投票出局或被狼人击杀时，可以立即开枪带走一位存活玩家。",
      "被女巫毒药毒死则无法开枪。",
      "开枪前先判断谁最像狼人，避免误伤好人。",
    ],
  },
};

export const roleQuickTips: Record<string, string> = {
  WOLF: "夜晚选目标，白天隐藏身份。",
  VILLAGER: "关注发言矛盾，慎重投票。",
  SEER: "查验结果很关键，公布时机要想清楚。",
  WITCH: "解药保人，毒药处理高风险目标。",
  HUNTER: "开枪前先判断谁最像狼人。",
};

export type AIPace = "fast" | "normal" | "slow";

export const aiPaceOptions: Array<{
  value: AIPace;
  label: string;
  delayMs: number;
}> = [
  { value: "fast", label: "快", delayMs: 0 },
  { value: "normal", label: "普通", delayMs: 700 },
  { value: "slow", label: "慢", delayMs: 1400 },
];

/** 不同行动类型的规则速记，放在 prompt 下方给新手提示。 */
export const actionRuleHint: Record<string, string | undefined> = {
  WITCH_ACTION: "解药、毒药各一瓶；每晚最多用一瓶，不能自救。",
  HUNTER_SHOOT: "开枪后你也会出局。被毒死时不能开枪。",
  WOLF_KILL: "确认击杀后不能更改。",
  SEER_CHECK: "查验结果只有你能看到。",
  VOTE: "平票则无人出局；弃票仍会计入本轮。",
  SPEAK: undefined,
};

/** 连接阶段的人话。 */
export const connectionPhaseCopy: Record<ConnectionPhase, string> = {
  idle: "未连接",
  connecting: "连接中",
  open: "已连接",
  closed: "连接已断",
  error: "连接错误",
};

/** 游戏阶段的人话，避免后端阶段常量泄漏到 UI。 */
export const gamePhaseCopy: Record<string, string> = {
  INIT: "发牌",
  CHECK_WIN: "检查胜负",
  NIGHT_START: "夜晚开始",
  WOLF_ACTION: "狼人行动",
  SEER_ACTION: "预言家行动",
  WITCH_ACTION: "女巫行动",
  NIGHT_END: "夜晚结束",
  DAY_START: "白天开始",
  DEAD_LAST_WORDS: "遗言",
  HUNTER_SHOOTING: "猎人开枪",
  DAY_SPEAKING: "发言",
  VOTING: "投票",
  VOTE_RESULT: "投票结果",
  BANISH_LAST_WORDS: "放逐遗言",
  GAME_OVER: "游戏结束",
};

/** 聊天气泡侧的小标签。 */
export const chatTagCopy: Record<"system" | "private" | "speech", string> = {
  system: "系统",
  private: "私信",
  speech: "发言",
};

/** 身份卡等处的"席位"文案。 */
export function formatSeat(seatId: number): string {
  return `${seatId}号玩家`;
}

/** 多个席位并列时的人话格式。 */
export function formatSeatList(seatIds: number[]): string {
  return seatIds.map((seatId) => formatSeat(seatId)).join("、");
}

/** 身份卡存活状态。 */
export const identityStateCopy = {
  alive: "仍在局内",
  dead: "已出局",
  unknownSeat: "等候发牌",
  unknownRole: "身份待揭",
} as const;

/** 系统消息的默认发言人。 */
export const narratorSpeaker = "游戏消息";

/** 侧栏发言输入的 placeholder。 */
export const speechPlaceholder = "输入你要说的话……";

function formatSeatMentionText(text: string): string {
  return text.replace(/(\d+)\s*号(?:玩家)?/g, (_, seatId: string) => formatSeat(Number(seatId)));
}

/** 后端保留规则日志原文，前端展示时统一成日常表达。 */
export function formatGameMessage(message: string): string {
  if (message === "connected") {
    return "已连接。";
  }
  if (message === "invalid payload") {
    return "操作未被接收，请重试。";
  }
  if (message === "游戏开始，分配身份完毕。") {
    return "游戏开始，身份已分配。";
  }
  if (message === "天黑请闭眼。") {
    return "天黑，请闭眼。";
  }
  if (message === "天亮了。昨夜是平安夜。") {
    return "天亮了，昨夜平安。";
  }
  const nightDeath = message.match(/^天亮了。昨夜死亡的是\s*(.+)。$/);
  if (nightDeath) {
    return `天亮了，昨夜死亡：${formatSeatMentionText(nightDeath[1])}。`;
  }
  const identity = message.match(/^你的座位号是\s*(\d+)\s*号，身份是\s*([A-Z_]+)。?$/);
  if (identity) {
    return `你的座位是 ${formatSeat(Number(identity[1]))}，身份是${toRoleLabel(identity[2]) ?? identity[2]}。`;
  }
  const wolfKill = message.match(/^你选择今晚击杀\s*(\d+)\s*号。$/);
  if (wolfKill) {
    return `你选择今晚击杀 ${formatSeat(Number(wolfKill[1]))}。`;
  }
  const seerCheck = message.match(/^你选择查验\s*(\d+)\s*号。$/);
  if (seerCheck) {
    return `你选择查验 ${formatSeat(Number(seerCheck[1]))}。`;
  }
  const witchSave = message.match(/^你使用解药救起\s*(\d+)\s*号。$/);
  if (witchSave) {
    return `你使用解药救起 ${formatSeat(Number(witchSave[1]))}。`;
  }
  const witchPoison = message.match(/^你对\s*(\d+)\s*号使用毒药。$/);
  if (witchPoison) {
    return `你对 ${formatSeat(Number(witchPoison[1]))} 使用毒药。`;
  }
  if (message === "你选择今晚不用药。") {
    return "你选择今晚不用药。";
  }
  if (message === "无效的用药选择已忽略，本轮不使用药。") {
    return "用药选择无效，本轮不使用药。";
  }
  if (message === "所有玩家弃票，本轮无人出局。") {
    return "所有玩家弃票，本轮无人出局。";
  }
  if (message === "出现平票，本轮无人出局。") {
    return "出现平票，本轮无人出局。";
  }
  if (message === "狼人已全部出局，好人阵营获胜。") {
    return "狼人已全部出局，好人阵营获胜。";
  }
  if (message === "平民已全部出局，狼人阵营获胜。") {
    return "平民已全部出局，狼人阵营获胜。";
  }
  if (message === "神职已全部出局，狼人阵营获胜。") {
    return "神职已全部出局，狼人阵营获胜。";
  }
  if (message === "夜尽未分胜负，本局暂止。") {
    return "夜晚结束仍未分出胜负，本局暂止。";
  }
  return formatSeatMentionText(message);
}

export function formatPhaseTitle(dayCount: number, phase: string | null): string {
  if (!phase) {
    return "游戏未开始";
  }
  const phaseLabel = gamePhaseCopy[phase] ?? "进行中";
  return `第 ${dayCount} 天 · ${phaseLabel}`;
}

export const uiCopy = {
  app: {
    title: "狼人杀对局面板",
    newGame: "新局",
    aiPaceAria: "AI 节奏",
    themeToDark: "切换至暗色主题",
    themeToLight: "切换至亮色主题",
    themeDarkText: "暗",
    themeLightText: "亮",
    reconnectNow: "立即重连",
    terminalAria: "游戏结束提示",
    battleAria: "游戏状态提示",
    nightFeedbackAria: "夜晚行动反馈",
    nightFeedbackLabel: "夜晚操作结果",
    spotlight: {
      pending: "轮到你操作",
      terminal: "游戏结束",
      open: "游戏进行中",
      idle: "等待连接",
    },
    connection: {
      terminal: "本局已结束",
      reconnecting: "连接已断，正在重连",
    },
    battle: {
      terminalDetail: "身份已全部公开。",
      pendingTitle: "轮到你操作",
      pendingDetail: "请在下方完成当前操作。",
      voteMutedTitle: "无人出局",
      voteDangerTitle: "投票已结算",
      formatVoteDetail: (summary: string) => `投票结果：${formatGameMessage(summary)}`,
      deathTitle: "昨夜死亡",
      peaceTitle: "平安夜",
      formatDeathDetail: (deadSeats: number[], lastWordSeats: number[]) => (
        `${formatSeatList(deadSeats)} 已出局${
          lastWordSeats.length > 0
            ? `，${formatSeatList(lastWordSeats)} 可以发表遗言。`
            : "。"
        }`
      ),
      peaceDetail: "昨夜没有玩家死亡。",
      phaseDetail: "游戏正在进行，消息会继续更新。",
      idleDetail: "等待游戏消息。",
    },
  },
  actionPanel: {
    title: "操作面板",
    identityAria: "你的身份",
    supplementalLabel: "对局回看",
    collapsedPrefix: "当前",
    currentLabel: "当前",
    toggleCollapseAria: "隐藏操作面板",
    toggleExpandAria: "展开操作面板",
    toggleCollapseText: "隐藏",
    toggleExpandText: "展开",
    shortcutHint: "Ctrl/⌘ + Enter 发送",
    witchActionAria: "女巫行动",
    witchSave: "救人",
    witchPoison: "毒人",
    witchPass: "跳过",
    poisonTargetAria: "毒药目标",
    voteActionAria: "投票操作",
    votePass: "弃票",
    allowedTargetAria: "合法目标",
    dangerArmedHint: "再次点击确认；按 Esc 取消。",
    dangerIdleHint: "此操作不可撤销，需要再次确认。",
    targetedHint: "可按数字键 1-9 快速选择座位。",
    confirmAgain: (label: string) => `再次确认 · ${label}`,
  },
  chat: {
    title: "对局日志",
    all: "全部",
    filterAria: "日志筛选",
    listAria: "对局日志列表",
    empty: "暂无消息",
    privateSpeaker: "你的视角",
    formatStats: (visible: number, total: number) => `${visible}/${total} 条`,
  },
  playerList: {
    deskAria: "桌面座位",
    listAria: "玩家状态列表",
    alive: "存活",
    thinking: "存活 · 思考中",
    dead: "已出局",
    humanPrefix: "真人",
    hiddenRole: "身份未知",
    formatSeatStatusAria: (seatId: number) => `${seatId}号状态`,
    formatStats: (aliveCount: number, thinkingCount: number) => (
      `${aliveCount} 人存活${thinkingCount > 0 ? ` · ${thinkingCount} 人思考中` : ""}`
    ),
  },
  roleGuide: {
    suffix: "技能",
    collapse: "收起",
    expand: "展开",
  },
  voteBoard: {
    aria: "投票票型",
    title: "投票结果",
    abstain: "弃票",
    abstainAria: "弃票玩家",
    formatCount: (count: number) => `${count}票`,
    formatParticipantCount: (count: number) => `${count} 人计票`,
    formatMeterAria: (seatId: number) => `${formatSeat(seatId)}得票`,
    formatSourceAria: (seatId: number) => `${formatSeat(seatId)}得票来源`,
  },
  settlement: {
    aria: "结算复盘",
    title: "结算复盘",
    outcomeGood: "好人胜利",
    outcomeWolf: "狼人胜利",
    outcomeDraw: "平局暂止",
    sideGood: "好人阵营",
    sideWolf: "狼人阵营",
    resultGood: "好人",
    resultWolf: "狼人",
    resultUnknown: "未知",
    none: "无",
    globalVoteEmpty: "本局没有放逐票。",
    globalVoteBlockAria: "全局票型",
    finalVoteFallbackTitle: "终局票型",
    formatDayVoteTitle: (dayCount: number) => `第 ${dayCount} 天票型`,
    voteAbstainPrefix: "弃票",
    nightEmpty: "本局没有进入完整夜晚。",
    nightBlockAria: "夜间因果",
    dayEmpty: "本局没有进入白天发言与投票。",
    dayBlockAria: "白天因果",
    noPublicSpeech: "关键发言：无公开发言",
    voteCausePrefix: "投票因果",
    voteCauseEmpty: "未进入放逐投票",
    finalDay: "终局",
    formatFinalDay: (dayCount: number | null) => dayCount === null ? "终局" : `第 ${dayCount} 天终局`,
    reasonPrefix: "原因",
    survivorsPrefix: "存活",
    wolvesPrefix: "狼队",
    rosterAria: "阵营翻牌",
    rosterTitle: "阵营身份",
    timelineAria: "完整时间线",
    timelineTitle: "完整时间线",
    timelineEmpty: "本局没有记录到关键公开节点。",
    formatNightTitle: (dayCount: number) => `第 ${dayCount} 夜`,
    wolfTargetPrefix: "狼人击杀目标",
    seerPrefix: "预言家",
    seerEmpty: "未查验",
    formatSeerCheck: (seerSeat: number, targetSeat: number, result: "GOOD" | "WOLF" | null) => (
      `${formatSeat(seerSeat)} 查验 ${formatSeat(targetSeat)}，结果为${
        result === "WOLF" ? "狼人" : result === "GOOD" ? "好人" : "未知"
      }`
    ),
    witchPrefix: "女巫",
    witchEmpty: "未行动",
    witchNoUse: "未用药",
    formatWitchSave: (seatId: number) => `救起 ${formatSeat(seatId)}`,
    formatWitchPoison: (seatId: number) => `毒杀 ${formatSeat(seatId)}`,
    nightResultPrefix: "夜晚结果",
    peacefulNight: "平安夜",
    formatDayTitle: (dayCount: number) => `第 ${dayCount} 天`,
    roleRevealMissing: "身份揭示暂不可用。",
  },
  errorBoundary: {
    title: "页面出错",
    detail: "对局面板遇到问题，请刷新页面重新进入。",
    reload: "刷新页面",
  },
} as const;
