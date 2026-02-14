/**
 * Game Hooks - Public API
 *
 * This module exports all game-related hooks for use in components.
 *
 * ARCHITECTURE:
 * - useGame: Main facade hook that composes all sub-hooks
 * - useGameState: Game state management (query + WebSocket)
 * - useGameActions: Game action mutations (start, step, submit)
 * - useGameAutomation: Auto-step logic
 * - useGameWebSocket: Real-time WebSocket connection
 * - useGameHistory: Game history queries
 * - useGameSound: Sound effects
 * - useGameTransformers: State transformation utilities
 */

// Main facade hook - use this in most cases
export { useGame } from './useGame';
export type { default as UseGameReturn } from './useGame';

// Sub-hooks for advanced use cases
export { useGameState } from './useGameState';
export { useGameActions } from './useGameActions';
export { useGameAutomation } from './useGameAutomation';
export { useGameWebSocket } from './useGameWebSocket';
export { useGameHistory } from './useGameHistory';
export { useGameSound } from './useGameSound';

// State transformation utilities
export { useGameTransformers } from './useGameTransformers';
export type { UIPlayer, UIMessage } from './useGameTransformers';

// Notification hooks
export { useNotificationWebSocket } from './useNotificationWebSocket';
export { useNotifications } from './useNotifications';
