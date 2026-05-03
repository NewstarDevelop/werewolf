import { type ChatEntry } from "../components/ChatHistory";
import { type PlayerListItem } from "../components/PlayerList";
import {
  formatSeat,
  identityStateCopy,
  narratorSpeaker,
  toRoleLabel,
} from "../copy";
import type { GameOverEnvelope, RequireInputEnvelope, ServerEnvelope } from "../types/ws";

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
  lastVoteResult: {
    votes: Record<number, number>;
    abstentions: number[];
    banishedSeat: number | null;
    summary: string;
  } | null;
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

  if (action.envelope.type === "SYSTEM_MSG") {
    players = applySystemMessage(players, action.envelope.data.message);
  }
  if (action.envelope.type === "CHAT_UPDATE" && action.envelope.data.visibility === "private") {
    players = applyIdentityMessage(players, action.envelope.data.message);
  }
  if (action.envelope.type === "CHAT_UPDATE" && action.envelope.data.visibility === "public") {
    players = applyPublicChatMessage(players, action.envelope.data.message);
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

function applyPublicChatMessage(players: PlayerListItem[], message: string) {
  return applySystemMessage(players, message);
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

function buildChatEntry(payload: ServerEnvelope): ChatEntry | null {
  if (payload.type === "SYSTEM_MSG") {
    return {
      id: `system-${crypto.randomUUID()}`,
      kind: "system",
      message: payload.data.message,
    };
  }

  if (payload.type === "CHAT_UPDATE") {
    const publicSpeechMatch = payload.data.visibility === "public"
      ? payload.data.message.match(/^(\d+)号发言[:：]/)
      : null;

    return {
      id: `chat-${crypto.randomUUID()}`,
      kind: payload.data.visibility === "private"
        ? "private"
        : publicSpeechMatch
          ? "speech"
          : "system",
      message: payload.data.message,
      speaker: payload.data.visibility === "private"
        ? payload.data.speaker ?? "你的视角"
        : publicSpeechMatch
          ? formatSeat(Number(publicSpeechMatch[1]))
          : payload.data.speaker ?? narratorSpeaker,
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
