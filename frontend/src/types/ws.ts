export interface SystemMessageEnvelope {
  type: "SYSTEM_MSG";
  data: {
    message: string;
  };
}

export interface ChatUpdateEnvelope {
  type: "CHAT_UPDATE";
  data: {
    message: string;
    seat_id?: number;
    speaker?: string;
    visibility: "public" | "private";
  };
}

export interface AIThinkingEnvelope {
  type: "AI_THINKING";
  data: {
    seat_id: number;
    is_thinking: boolean;
    message?: string;
  };
}

export interface RequireInputEnvelope {
  type: "REQUIRE_INPUT";
  data: {
    action_type: "SPEAK" | "VOTE" | "WOLF_KILL" | "SEER_CHECK" | "HUNTER_SHOOT" | "WITCH_ACTION";
    prompt: string;
    allowed_targets: number[];
  };
}

export interface GameOverEnvelope {
  type: "GAME_OVER";
  data: {
    winning_side: "GOOD" | "WOLF";
    summary: string;
    revealed_roles: Record<number, string>;
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
  | RequireInputEnvelope
  | GameOverEnvelope;
