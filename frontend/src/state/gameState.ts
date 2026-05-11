import { type ChatEntry } from "../components/ChatHistory";
import { type PlayerListItem } from "../components/PlayerList";
import {
  formatSeat,
  identityStateCopy,
  narratorSpeaker,
  toRoleLabel,
  uiCopy,
} from "../copy";
import type {
  ChatUpdateEnvelope,
  ChatUpdateMeta,
  GameOverEnvelope,
  RequireInputEnvelope,
  ServerEnvelope,
  SystemMessageEnvelope,
} from "../types/ws";

export interface VoteResultView {
  votes: Record<number, number>;
  ballots: Record<number, number>;
  abstentions: number[];
  banishedSeat: number | null;
  summary: string;
}

export interface SettlementReviewPlayer {
  seatId: number;
  roleCode: string;
  roleLabel: string;
  side: "GOOD" | "WOLF";
  isAlive: boolean;
  isHuman: boolean;
}

export interface SettlementReviewEvent {
  dayCount: number;
  phase: string;
  eventType: string;
  message: string;
  actorSeat: number | null;
  targetSeats: number[];
}

export interface SettlementReviewNight {
  dayCount: number;
  wolfTarget: number | null;
  seerSeat: number | null;
  seerTarget: number | null;
  seerResult: "GOOD" | "WOLF" | null;
  witchSeat: number | null;
  witchSaveTarget: number | null;
  witchPoisonTarget: number | null;
  deadSeats: number[];
}

export interface SettlementReviewSpeech {
  seatId: number;
  message: string;
  eventType: string;
}

export interface SettlementReviewDay {
  dayCount: number;
  speeches: SettlementReviewSpeech[];
  vote: VoteResultView | null;
  voteExplanation: string | null;
}

export interface SettlementReviewData {
  winningSide: "GOOD" | "WOLF" | "DRAW";
  summary: string;
  outcomeReason: string;
  roleRevealSummary: string;
  dayCount: number | null;
  players: SettlementReviewPlayer[];
  nights: SettlementReviewNight[];
  days: SettlementReviewDay[];
  keyEvents: SettlementReviewEvent[];
  timeline: SettlementReviewEvent[];
  finalVote: VoteResultView | null;
}

export interface GameState {
  entries: ChatEntry[];
  players: PlayerListItem[];
  pendingAction: RequireInputEnvelope["data"] | null;
  isTerminal: boolean;
  currentPhase: string | null;
  dayCount: number;
  lastDeathReveal: {
    deadSeats: number[];
    eligibleLastWords: number[];
    dayCount: number;
  } | null;
  lastVoteResult: VoteResultView | null;
  lastNightActionFeedback: {
    message: string;
    targetSeats: number[];
  } | null;
  settlementReview: SettlementReviewData | null;
}

export type GameStateAction =
  | { type: "reset" }
  | { type: "clear-pending-action" }
  | { type: "mark-terminal" }
  | { type: "server-envelope"; envelope: ServerEnvelope };

export function createInitialPlayers(): PlayerListItem[] {
  return Array.from({ length: 9 }, (_, index) => ({
    seatId: index + 1,
    isAlive: true,
    isHuman: index === 0,
    roleLabel: index === 0 ? identityStateCopy.unknownRole : undefined,
    isThinking: false,
  }));
}

export function createInitialGameState(): GameState {
  return {
    entries: [],
    players: createInitialPlayers(),
    pendingAction: null,
    isTerminal: false,
    currentPhase: null,
    dayCount: 1,
    lastDeathReveal: null,
    lastVoteResult: null,
    lastNightActionFeedback: null,
    settlementReview: null,
  };
}

export function gameReducer(state: GameState, action: GameStateAction): GameState {
  if (action.type === "reset") {
    return createInitialGameState();
  }
  if (action.type === "clear-pending-action") {
    return { ...state, pendingAction: null };
  }
  if (action.type === "mark-terminal") {
    return { ...state, isTerminal: true, pendingAction: null };
  }

  const chatEntry = buildChatEntry(action.envelope);
  const entries = chatEntry ? [...state.entries, chatEntry] : state.entries;
  let players = state.players;
  let pendingAction = state.pendingAction;
  let isTerminal = state.isTerminal;
  let currentPhase = state.currentPhase;
  let dayCount = state.dayCount;
  let lastDeathReveal = state.lastDeathReveal;
  let lastVoteResult = state.lastVoteResult;
  let lastNightActionFeedback = state.lastNightActionFeedback;
  let settlementReview = state.settlementReview;

  if (action.envelope.type === "SYSTEM_MSG") {
    players = applySystemMessage(players, action.envelope.data.message);
    if (shouldClearPendingAction(pendingAction, action.envelope)) {
      pendingAction = null;
    }
  }
  if (action.envelope.type === "CHAT_UPDATE" && action.envelope.data.visibility === "private") {
    players = applyIdentityMessage(players, action.envelope.data.message);
    if (action.envelope.meta?.event_type === "NIGHT_ACTION_FEEDBACK") {
      lastNightActionFeedback = {
        message: action.envelope.data.message,
        targetSeats: Array.isArray(action.envelope.meta.target_seats)
          ? action.envelope.meta.target_seats.filter((seatId) => Number.isInteger(seatId))
          : [],
      };
    }
  }
  if (action.envelope.type === "CHAT_UPDATE" && action.envelope.data.visibility === "public") {
    players = applyPublicChatMessage(players, action.envelope);
  }
  if (action.envelope.type === "AI_THINKING") {
    players = applyThinkingState(
      players,
      action.envelope.data.seat_id,
      action.envelope.data.is_thinking,
    );
  }
  if (action.envelope.type === "PLAYER_STATE_PATCH") {
    players = applyPlayerStatePatch(players, action.envelope.data.players);
  }
  if (action.envelope.type === "PHASE_CHANGED") {
    currentPhase = action.envelope.data.phase;
    dayCount = action.envelope.data.day_count;
  }
  if (action.envelope.type === "DEATH_REVEALED") {
    players = applyDeathReveal(players, action.envelope.data.dead_seats);
    lastDeathReveal = {
      deadSeats: action.envelope.data.dead_seats,
      eligibleLastWords: action.envelope.data.eligible_last_words,
      dayCount: action.envelope.data.day_count,
    };
  }
  if (action.envelope.type === "VOTE_RESOLVED") {
    players = applyBanishResult(players, action.envelope.data.banished_seat ?? null);
    lastVoteResult = {
      votes: action.envelope.data.votes,
      ballots: action.envelope.data.ballots ?? {},
      abstentions: action.envelope.data.abstentions,
      banishedSeat: action.envelope.data.banished_seat ?? null,
      summary: action.envelope.data.summary,
    };
  }
  if (action.envelope.type === "REQUIRE_INPUT") {
    pendingAction = action.envelope.data;
  }
  if (action.envelope.type === "GAME_OVER") {
    isTerminal = true;
    currentPhase = "GAME_OVER";
    players = applyGameOver(players, action.envelope.data);
    pendingAction = null;
    const review = buildSettlementReview(action.envelope.data);
    settlementReview = review.finalVote || lastVoteResult === null
      ? review
      : { ...review, finalVote: lastVoteResult };
  }

  return {
    entries,
    players,
    pendingAction,
    isTerminal,
    currentPhase,
    dayCount,
    lastDeathReveal,
    lastVoteResult,
    lastNightActionFeedback,
    settlementReview,
  };
}

export function findLatestOutcome(entries: ChatEntry[]) {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (entries[index]?.id.startsWith("game-over-")) {
      return entries[index];
    }
  }
  return null;
}

function applyThinkingState(players: PlayerListItem[], seatId: number, isThinking: boolean) {
  return players.map((player) =>
    player.seatId === seatId ? { ...player, isThinking } : player,
  );
}

function applyPlayerStatePatch(
  players: PlayerListItem[],
  patches: Array<{
    seat_id: number;
    is_alive?: boolean | null;
    is_human?: boolean | null;
    role_code?: string | null;
    is_thinking?: boolean | null;
  }>,
) {
  const patchBySeat = new Map(patches.map((patch) => [patch.seat_id, patch]));
  const explicitHumanSeat = patches.find((patch) => patch.is_human === true)?.seat_id;

  return players.map((player) => {
    const patch = patchBySeat.get(player.seatId);
    const roleCode = patch?.role_code ?? player.roleCode;
    const isHuman = patch?.is_human ?? (
      explicitHumanSeat === undefined ? player.isHuman : player.seatId === explicitHumanSeat
    );

    return {
      ...player,
      isAlive: patch?.is_alive ?? player.isAlive,
      isHuman,
      isThinking: patch?.is_thinking ?? player.isThinking,
      roleCode,
      roleLabel: roleCode
        ? (toRoleLabel(roleCode) ?? roleCode)
        : isHuman
          ? player.roleLabel
          : undefined,
    };
  });
}

function applyDeathReveal(players: PlayerListItem[], deadSeats: number[]) {
  const deadSeatSet = new Set(deadSeats);
  if (deadSeatSet.size === 0) {
    return players;
  }
  return players.map((player) =>
    deadSeatSet.has(player.seatId)
      ? { ...player, isAlive: false, isThinking: false }
      : player,
  );
}

function applyBanishResult(players: PlayerListItem[], banishedSeat: number | null) {
  if (banishedSeat === null) {
    return players;
  }
  return players.map((player) =>
    player.seatId === banishedSeat
      ? { ...player, isAlive: false, isThinking: false }
      : player,
  );
}

function applyIdentityMessage(players: PlayerListItem[], message: string) {
  const identityMatch = message.match(/你的座位号是\s*(\d+)\s*号，身份是\s*([A-Z_]+)\s*。?/);

  if (!identityMatch) {
    return players;
  }

  const humanSeat = Number(identityMatch[1]);
  const humanRoleCode = identityMatch[2];
  const humanRole = toRoleLabel(humanRoleCode) ?? humanRoleCode;
  return players.map((player) => {
    const isHuman = player.seatId === humanSeat;
    return {
      ...player,
      isHuman,
      roleLabel: isHuman ? humanRole : undefined,
      roleCode: isHuman ? humanRoleCode : undefined,
    };
  });
}

function applySystemMessage(players: PlayerListItem[], message: string) {
  let nextPlayers = applyIdentityMessage(players, message);

  const directDeathSeats = [...message.matchAll(/(\d+)号(?:玩家)?(?:被放逐出局|死亡)/g)].map((match) => Number(match[1]));
  const nightlyDeathAnnouncement = message.match(/昨夜死亡的是\s*([^。]+)/);
  const announcedNightSeats = nightlyDeathAnnouncement
    ? [...nightlyDeathAnnouncement[1].matchAll(/(\d+)号/g)].map((match) => Number(match[1]))
    : [];
  const hunterShotSeat = message.match(/猎人开枪带走了\s*(\d+)号玩家/);
  const hunterShotDeaths = hunterShotSeat ? [Number(hunterShotSeat[1])] : [];

  const deadSeats = new Set([...directDeathSeats, ...announcedNightSeats, ...hunterShotDeaths]);
  if (deadSeats.size > 0) {
    nextPlayers = nextPlayers.map((player) =>
      deadSeats.has(player.seatId) ? { ...player, isAlive: false, isThinking: false } : player,
    );
  }

  return nextPlayers;
}

function isSubmitAckMessage(message: string) {
  return message.startsWith("ack:");
}

function submitAckRequestId(envelope: SystemMessageEnvelope) {
  const metaRequestId = envelope.meta?.request_id;
  if (typeof metaRequestId === "string" && metaRequestId.length > 0) {
    return metaRequestId;
  }

  const [, , messageRequestId] = envelope.data.message.split(":");
  return messageRequestId || null;
}

function shouldClearPendingAction(
  pendingAction: RequireInputEnvelope["data"] | null,
  envelope: SystemMessageEnvelope,
) {
  if (!pendingAction || !isSubmitAckMessage(envelope.data.message)) {
    return false;
  }

  const ackRequestId = submitAckRequestId(envelope);
  if (!pendingAction.request_id) {
    return ackRequestId === null;
  }
  return ackRequestId === pendingAction.request_id;
}

function applyPublicChatMessage(players: PlayerListItem[], envelope: ChatUpdateEnvelope) {
  const structuredDeadSeats = extractDeadSeatsFromChatMeta(envelope.meta);
  if (structuredDeadSeats.length > 0) {
    return markSeatsDead(players, structuredDeadSeats);
  }
  if (isStructuredSpeechMeta(envelope.meta)) {
    return players;
  }
  return applySystemMessage(players, envelope.data.message);
}

function markSeatsDead(players: PlayerListItem[], seatIds: number[]) {
  const deadSeats = new Set(seatIds);
  return players.map((player) =>
    deadSeats.has(player.seatId) ? { ...player, isAlive: false, isThinking: false } : player,
  );
}

function extractDeadSeatsFromChatMeta(meta: ChatUpdateMeta | undefined) {
  if (!meta?.event_type || !Array.isArray(meta.target_seats)) {
    return [];
  }

  const deathEvents = new Set(["NIGHT_DEATH", "BANISHMENT", "HUNTER_SHOT"]);
  if (!deathEvents.has(meta.event_type)) {
    return [];
  }

  return meta.target_seats.filter((seatId) => Number.isInteger(seatId));
}

function isStructuredSpeechMeta(meta: ChatUpdateMeta | undefined) {
  return meta?.message_kind === "speech"
    || meta?.event_type === "SPEECH"
    || meta?.event_type === "LAST_WORDS";
}

function applyGameOver(players: PlayerListItem[], payload: GameOverEnvelope["data"]) {
  return players.map((player) => {
    const revealedCode = payload.revealed_roles[player.seatId];
    return {
      ...player,
      isThinking: false,
      roleCode: revealedCode ?? player.roleCode,
      roleLabel: revealedCode
        ? (toRoleLabel(revealedCode) ?? revealedCode)
        : player.roleLabel,
    };
  });
}

function toRoleSide(roleCode: string): "GOOD" | "WOLF" {
  return roleCode === "WOLF" ? "WOLF" : "GOOD";
}

function buildVoteResultView(vote: NonNullable<GameOverEnvelope["data"]["recap"]>["final_vote"]): VoteResultView | null {
  if (!vote) {
    return null;
  }
  return {
    votes: vote.votes,
    ballots: vote.ballots ?? {},
    abstentions: vote.abstentions,
    banishedSeat: vote.banished_seat ?? null,
    summary: vote.summary,
  };
}

function buildSettlementReview(payload: GameOverEnvelope["data"]): SettlementReviewData {
  const recap = payload.recap;
  const players = recap
    ? recap.players.map((player) => ({
        seatId: player.seat_id,
        roleCode: player.role_code,
        roleLabel: toRoleLabel(player.role_code) ?? player.role_code,
        side: player.side,
        isAlive: player.is_alive,
        isHuman: player.is_human,
      }))
    : Object.entries(payload.revealed_roles)
        .map(([seatId, roleCode]) => ({
          seatId: Number(seatId),
          roleCode,
          roleLabel: toRoleLabel(roleCode) ?? roleCode,
          side: toRoleSide(roleCode),
          isAlive: false,
          isHuman: false,
        }))
        .sort((left, right) => left.seatId - right.seatId);

  return {
    winningSide: payload.winning_side,
    summary: payload.summary,
    outcomeReason: recap?.outcome_reason ?? payload.summary,
    roleRevealSummary: recap?.role_reveal_summary ?? uiCopy.settlement.roleRevealMissing,
    dayCount: recap?.day_count ?? null,
    players,
    nights: (recap?.nights ?? []).map((night) => ({
      dayCount: night.day_count,
      wolfTarget: night.wolf_target ?? null,
      seerSeat: night.seer_seat ?? null,
      seerTarget: night.seer_target ?? null,
      seerResult: night.seer_result ?? null,
      witchSeat: night.witch_seat ?? null,
      witchSaveTarget: night.witch_save_target ?? null,
      witchPoisonTarget: night.witch_poison_target ?? null,
      deadSeats: night.dead_seats,
    })),
    days: (recap?.days ?? []).map((day) => ({
      dayCount: day.day_count,
      speeches: day.speeches.map((speech) => ({
        seatId: speech.seat_id,
        message: speech.message,
        eventType: speech.event_type,
      })),
      vote: buildVoteResultView(day.vote),
      voteExplanation: day.vote_explanation ?? null,
    })),
    keyEvents: (recap?.key_events ?? []).map((event) => ({
      dayCount: event.day_count,
      phase: event.phase,
      eventType: event.event_type,
      message: event.message,
      actorSeat: event.actor_seat ?? null,
      targetSeats: event.target_seats,
    })),
    timeline: (recap?.timeline ?? recap?.key_events ?? []).map((event) => ({
      dayCount: event.day_count,
      phase: event.phase,
      eventType: event.event_type,
      message: event.message,
      actorSeat: event.actor_seat ?? null,
      targetSeats: event.target_seats,
    })),
    finalVote: buildVoteResultView(recap?.final_vote),
  };
}

function buildChatEntry(payload: ServerEnvelope): ChatEntry | null {
  if (payload.type === "SYSTEM_MSG") {
    if (payload.meta?.status === "ack" || payload.meta?.status === "reject") {
      return null;
    }
    return {
      id: `system-${crypto.randomUUID()}`,
      kind: "system",
      message: payload.data.message,
    };
  }

  if (payload.type === "CHAT_UPDATE") {
    const chatMeta = payload.meta;
    const structuredSpeaker = typeof chatMeta?.actor_seat === "number"
      ? formatSeat(chatMeta.actor_seat)
      : null;
    const publicSpeechMatch = payload.data.visibility === "public" && !structuredSpeaker
      ? payload.data.message.match(/^(\d+)号发言[:：]/)
      : null;
    const isStructuredSpeech = payload.data.visibility === "public"
      && (
        chatMeta?.message_kind === "speech"
        || chatMeta?.event_type === "SPEECH"
        || chatMeta?.event_type === "LAST_WORDS"
      );

    return {
      id: `chat-${crypto.randomUUID()}`,
      kind: payload.data.visibility === "private"
        ? "private"
        : isStructuredSpeech || publicSpeechMatch
          ? "speech"
          : "system",
      message: payload.data.message,
      speaker: payload.data.visibility === "private"
        ? uiCopy.chat.privateSpeaker
        : structuredSpeaker
          ? structuredSpeaker
          : publicSpeechMatch
          ? formatSeat(Number(publicSpeechMatch[1]))
          : narratorSpeaker,
    };
  }

  if (payload.type === "GAME_OVER") {
    return {
      id: `game-over-${crypto.randomUUID()}`,
      kind: "system",
      message: payload.data.summary,
      speaker: narratorSpeaker,
    };
  }

  return null;
}
