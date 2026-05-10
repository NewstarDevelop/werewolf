export interface SystemMessageEnvelope {
  type: "SYSTEM_MSG";
  data: {
    message: string;
  };
  meta?: {
    status?: "ack" | "reject" | string;
    action_type?: string;
    request_id?: string;
    [key: string]: unknown;
  };
}

export interface ChatUpdateMeta {
  message_kind?: "system" | "speech";
  event_type?:
    | "SPEECH"
    | "LAST_WORDS"
    | "NIGHT_START"
    | "NIGHT_DEATH"
    | "PEACEFUL_NIGHT"
    | "BANISHMENT"
    | "VOTE_NO_BANISHMENT"
    | "HUNTER_SHOT"
    | "HUNTER_POISONED"
    | "HUNTER_NO_TARGET"
    | "GAME_OVER_SUMMARY"
    | "NIGHT_ACTION_FEEDBACK"
    | string;
  actor_seat?: number;
  target_seats?: number[];
}

export interface ChatUpdateEnvelope {
  type: "CHAT_UPDATE";
  data: {
    message: string;
    seat_id?: number;
    speaker?: string;
    visibility: "public" | "private";
  };
  meta?: ChatUpdateMeta;
}

export interface AIThinkingEnvelope {
  type: "AI_THINKING";
  data: {
    seat_id: number;
    is_thinking: boolean;
    message?: string;
  };
}

export interface PlayerStatePatchEnvelope {
  type: "PLAYER_STATE_PATCH";
  data: {
    players: Array<{
      seat_id: number;
      is_alive?: boolean | null;
      is_human?: boolean | null;
      role_code?: string | null;
      is_thinking?: boolean | null;
    }>;
  };
}

export interface PhaseChangedEnvelope {
  type: "PHASE_CHANGED";
  data: {
    phase: string;
    day_count: number;
  };
}

export interface DeathRevealedEnvelope {
  type: "DEATH_REVEALED";
  data: {
    dead_seats: number[];
    eligible_last_words: number[];
    day_count: number;
  };
}

export interface VoteResolvedEnvelope {
  type: "VOTE_RESOLVED";
  data: {
    votes: Record<number, number>;
    ballots?: Record<number, number>;
    abstentions: number[];
    banished_seat?: number | null;
    summary: string;
  };
}

export interface SettlementPlayerPayload {
  seat_id: number;
  role_code: string;
  side: "GOOD" | "WOLF";
  is_alive: boolean;
  is_human: boolean;
}

export interface SettlementEventPayload {
  day_count: number;
  phase: string;
  event_type: string;
  message: string;
  actor_seat?: number | null;
  target_seats: number[];
}

export interface SettlementNightPayload {
  day_count: number;
  wolf_target?: number | null;
  seer_seat?: number | null;
  seer_target?: number | null;
  seer_result?: "GOOD" | "WOLF" | null;
  witch_seat?: number | null;
  witch_save_target?: number | null;
  witch_poison_target?: number | null;
  dead_seats: number[];
}

export interface SettlementSpeechPayload {
  seat_id: number;
  message: string;
  event_type: string;
}

export interface SettlementDayPayload {
  day_count: number;
  speeches: SettlementSpeechPayload[];
  vote?: VoteResolvedEnvelope["data"] | null;
  vote_explanation?: string | null;
}

export interface SettlementRecapPayload {
  day_count: number;
  outcome_reason: string;
  role_reveal_summary: string;
  players: SettlementPlayerPayload[];
  nights: SettlementNightPayload[];
  days: SettlementDayPayload[];
  key_events: SettlementEventPayload[];
  timeline: SettlementEventPayload[];
  final_vote?: VoteResolvedEnvelope["data"] | null;
}

export interface RequireInputEnvelope {
  type: "REQUIRE_INPUT";
  data: {
    action_type: "SPEAK" | "VOTE" | "WOLF_KILL" | "SEER_CHECK" | "HUNTER_SHOOT" | "WITCH_ACTION";
    request_id: string;
    prompt: string;
    allowed_targets: number[];
    available_actions?: Array<"WITCH_SAVE" | "WITCH_POISON" | "PASS">;
    save_targets?: number[];
  };
}

export interface GameOverEnvelope {
  type: "GAME_OVER";
  data: {
    winning_side: "GOOD" | "WOLF" | "DRAW";
    summary: string;
    revealed_roles: Record<number, string>;
    recap?: SettlementRecapPayload | null;
  };
}

export interface SubmitActionPayload {
  action_type:
    | "SPEAK"
    | "VOTE"
    | "WOLF_KILL"
    | "SEER_CHECK"
    | "HUNTER_SHOOT"
    | "WITCH_SAVE"
    | "WITCH_POISON"
    | "PASS";
  target?: number;
  text?: string;
  request_id?: string;
}

export interface ClientEnvelope {
  type: "SUBMIT_ACTION";
  data: SubmitActionPayload;
  meta?: Record<string, unknown>;
}

export type ServerEnvelope =
  | SystemMessageEnvelope
  | ChatUpdateEnvelope
  | AIThinkingEnvelope
  | PlayerStatePatchEnvelope
  | PhaseChangedEnvelope
  | DeathRevealedEnvelope
  | VoteResolvedEnvelope
  | RequireInputEnvelope
  | GameOverEnvelope;
