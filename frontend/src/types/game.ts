/**
 * Game Types for Werewolf Game
 * These types match the backend API schemas
 */

// Re-export API types for convenience
export type {
  Role,
  GameStatus,
  GamePhase,
  ActionType,
  MessageType,
  Winner,
  PlayerPublic,
  MessageInGame,
  PendingAction,
  GameState,
  GameStartRequest,
  GameStartResponse,
  StepResponse,
  ActionRequest,
  ActionResponse,
} from '@/services/api';

// Frontend-specific types

export interface Message {
  seat_id: number;
  content: string;
  type?: 'speech' | 'system' | 'thought' | 'last_words';
}

export interface Player {
  id: number;
  name: string;
  isUser: boolean;
  isAlive: boolean;
  role?: string;
  seatId: number;
}

export interface ChatMessage {
  id: number;
  sender: string;
  message: string;
  isUser: boolean;
  isSystem?: boolean;
  timestamp: string;
  day?: number;
}

// Game context for UI
export interface GameContext {
  gameId: string | null;
  isLoading: boolean;
  error: string | null;
  gameState: import('@/services/api').GameState | null;
}
