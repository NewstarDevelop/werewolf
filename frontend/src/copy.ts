/**
 * Single source of truth for user-facing strings.
 *
 * Never expose backend code constants (WOLF_KILL / REQUIRE_INPUT / ...) to
 * the UI. Route every action_type through `actionTypeCopy`.
 *
 * Tone guide (from .impeccable.md):
 *   - 墨色 克制 松动: 短、克制、文人桌游感
 *   - 动词优先：用户是为了"做"，不是为了"读说明"
 *   - 仪式感：destructive 动作的 submitLabel 要有分量（下刀/下毒/开枪）
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
  title: "候场中",
  heading: "且待",
  instruction: "桌上仍在推演，轮到你时此处会自动点亮。",
  submitLabel: "确认",
  tone: "neutral",
};

export const actionTypeCopy: Record<InputActionType, ActionCopy> = {
  SPEAK: {
    title: "轮到发言",
    heading: "你的陈词",
    instruction: "请写下你想对桌上众人说的话。简短有力更易服人。",
    submitLabel: "落言",
    tone: "neutral",
  },
  VOTE: {
    title: "白昼放逐",
    heading: "投下你的一票",
    instruction: "选出今日你要放逐的人。若心存不决，可以弃票。",
    submitLabel: "投下此票",
    tone: "neutral",
  },
  WOLF_KILL: {
    title: "狼夜出刀",
    heading: "今夜，刀向何人",
    instruction: "选择今夜要击杀的目标。",
    submitLabel: "下刀",
    tone: "danger",
  },
  SEER_CHECK: {
    title: "预言家验人",
    heading: "今夜，验谁身份",
    instruction: "选择一位存活玩家，验明身份。",
    submitLabel: "查验",
    tone: "neutral",
  },
  WITCH_ACTION: {
    title: "女巫持药",
    heading: "解药或毒药",
    instruction: "解药与毒药各限一次。选择后落下决定。",
    submitLabel: "定夺",
    tone: "neutral",
  },
  HUNTER_SHOOT: {
    title: "猎人开枪",
    heading: "枪口，要对准谁",
    instruction: "你倒下前可以带走一人。一经决定，不可更改。",
    submitLabel: "开枪",
    tone: "danger",
  },
};

export const submitActionCopy: Record<SubmitActionType, ActionCopy> = {
  ...actionTypeCopy,
  WITCH_SAVE: {
    title: "女巫救人",
    heading: "以解药救起昨夜被杀之人",
    instruction: "使用仅剩的解药，救回今夜被狼人击杀的玩家。",
    submitLabel: "救起",
    tone: "neutral",
  },
  WITCH_POISON: {
    title: "女巫下毒",
    heading: "毒向何人",
    instruction: "选择今夜要毒杀的目标。",
    submitLabel: "下毒",
    tone: "danger",
  },
  PASS: {
    title: "跳过本轮",
    heading: "不动声色",
    instruction: "本轮不行使技能。",
    submitLabel: "定下来",
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

/** 角色技能说明 — 折叠抽屉里铺陈给新手看。 */
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
    oneLiner: "隐入人群，夜间取人性命。",
    abilities: [
      "夜晚：与狼队友共同选定一位玩家击杀。",
      "白天：跟随发言顺序说话，可以伪装好人或悍跳神职。",
      "胜负：击杀所有平民或所有神职，即屠边获胜。",
    ],
  },
  VILLAGER: {
    name: "平民",
    camp: "good",
    oneLiner: "以发言与票权对抗黑夜。",
    abilities: [
      "无技能。你唯一的武器是推理与说服。",
      "白天发言时抓细节、识伪装、站好人。",
      "胜负：狼人全部出局，即好人阵营获胜。",
    ],
  },
  SEER: {
    name: "预言家",
    camp: "good",
    oneLiner: "夜夜验人身份，逐步拨开迷雾。",
    abilities: [
      "夜晚：验证一位存活玩家是好人或狼人（结果落为私见，只有你看得到）。",
      "白天：你是好人阵营的核心，谨慎选择何时公布。",
      "注意：身份暴露后常被狼人夜刀。",
    ],
  },
  WITCH: {
    name: "女巫",
    camp: "good",
    oneLiner: "一瓶解药救人，一瓶毒药除敌。",
    abilities: [
      "全程仅持一瓶解药与一瓶毒药，用完即无。",
      "每晚只能用一瓶药。解药不可用于自救。",
      "谨慎用毒——误毒神职，好人阵营会崩盘。",
    ],
  },
  HUNTER: {
    name: "猎人",
    camp: "good",
    oneLiner: "倒下之际可一同带走一人。",
    abilities: [
      "被投票出局或被狼刀时，可立即开枪带走一位存活玩家。",
      "被女巫毒药毒死则无法开枪。",
      "出枪时机要克制，暴露身份会被狼人留到最后处理。",
    ],
  },
};

/** 不同行动类型的规则速记，落在 prompt 下方以作新手兜底。 */
export const actionRuleHint: Record<string, string | undefined> = {
  WITCH_ACTION: "女巫解药与毒药各一瓶，全程仅此一用。不可用药自救。",
  HUNTER_SHOOT: "开枪后你亦会同时倒下。被毒药毒死则不能开枪。",
  WOLF_KILL: "夜晚刀出之后不可更改。",
  SEER_CHECK: "查验结果落为私见，仅你可见。",
  VOTE: "平票则无人出局。弃票不影响结算。",
  SPEAK: undefined,
};

/** 连接阶段的人话。 */
export const connectionPhaseCopy: Record<ConnectionPhase, string> = {
  idle: "尚未入场",
  connecting: "接续中",
  open: "已入场",
  closed: "连接已断",
  error: "连接有误",
};

/** 游戏阶段的人话，避免后端阶段常量泄漏到 UI。 */
export const gamePhaseCopy: Record<string, string> = {
  INIT: "发牌",
  CHECK_WIN: "验局",
  NIGHT_START: "入夜",
  WOLF_ACTION: "狼夜",
  SEER_ACTION: "查验",
  WITCH_ACTION: "持药",
  NIGHT_END: "夜结",
  DAY_START: "天明",
  DEAD_LAST_WORDS: "遗言",
  HUNTER_SHOOTING: "猎枪",
  DAY_SPEAKING: "发言",
  VOTING: "投票",
  VOTE_RESULT: "开票",
  BANISH_LAST_WORDS: "放逐遗言",
  GAME_OVER: "终局",
};

/** 聊天气泡侧的小标签。 */
export const chatTagCopy: Record<"system" | "private" | "speech", string> = {
  system: "系统",
  private: "私见",
  speech: "发言",
};

/** 身份卡等处的"席位"文案。 */
export function formatSeat(seatId: number): string {
  return `${seatId}号玩家`;
}

/** 身份卡存活状态。 */
export const identityStateCopy = {
  alive: "仍在局内",
  dead: "已出局",
  unknownSeat: "等候发牌",
  unknownRole: "身份待揭",
} as const;

/** "结算" → 更有剧场感。 */
export const narratorSpeaker = "主持人";

/** 侧栏发言输入的 placeholder。 */
export const speechPlaceholder = "在此落下你此刻想说的话……";
