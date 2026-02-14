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

