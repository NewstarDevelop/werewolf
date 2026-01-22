// Type definitions extracted from services/api.ts
// Single Source of Truth for API Types

export type Role = 'werewolf' | 'villager' | 'seer' | 'witch' | 'hunter' | 'guard' | 'wolf_king' | 'white_wolf_king';
export type GameStatus = 'waiting' | 'playing' | 'finished';
export type GameMode = 'classic_9' | 'classic_12';
export type WolfKingVariant = 'wolf_king' | 'white_wolf_king';

export type GamePhase =
  | 'night_start'
  | 'night_guard'
  | 'night_werewolf_chat'
  | 'night_werewolf'
  | 'night_seer'
  | 'night_witch'
  | 'day_announcement'
  | 'day_last_words'
  | 'death_shoot'
  | 'day_speech'
  | 'day_vote'
  | 'day_vote_result'
  | 'hunter_shoot'
  | 'game_over';

export type ActionType = 'kill' | 'verify' | 'save' | 'poison' | 'vote' | 'shoot' | 'protect' | 'self_destruct' | 'speak' | 'skip';

export type MessageType = 'speech' | 'system' | 'thought' | 'last_words' | 'wolf_chat' | 'vote_thought';

export type Winner = 'werewolf' | 'villager' | 'none';

export interface PlayerPublic {
  seat_id: number;
  is_alive: boolean;
  is_human: boolean;
  avatar?: string | null;
  name?: string | null;
  role?: Role | null; // only shown when game is finished
}

export interface MessageInGame {
  seat_id: number;
  text: string;
  type: MessageType;
  day: number;
}

export interface PendingAction {
  type: ActionType;
  choices: number[];
  message?: string | null;
}

export interface GameState {
  game_id: string;
  status: GameStatus;
  state_version: number;  // State version for race condition prevention
  day: number;
  phase: GamePhase;
  current_actor?: number | null;
  my_seat: number;
  my_role: Role;
  players: PlayerPublic[];
  message_log: MessageInGame[];
  pending_action?: PendingAction | null;
  winner?: Winner | null;
  night_kill_target?: number | null;
  wolf_teammates: number[];
  verified_results: Record<number, boolean>;
  wolf_votes_visible?: Record<number, number>; // teammate_seat -> target_seat
}

export interface GameStartRequest {
  human_seat?: number | null;
  human_role?: Role | null;
  language?: string;  // Game language: "zh" or "en"
}

export interface GameStartResponse {
  game_id: string;
  player_role: Role;
  player_seat: number;
  players: PlayerPublic[];
  token: string;  // JWT token for authentication
}

export interface StepResponse {
  status: string;
  new_phase?: GamePhase | null;
  message?: string | null;
}

export interface ActionRequest {
  seat_id: number;
  action_type: ActionType;
  target_id?: number | null;
  content?: string | null;
}

export interface ActionResponse {
  success: boolean;
  message?: string | null;
}
