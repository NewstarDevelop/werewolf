/**
 * API Service for Werewolf Game Backend
 * Handles all HTTP requests to the FastAPI backend
 *
 * Uses the unified api-client from @/lib/api-client
 */

import { fetchApi } from '@/lib/api-client';
import i18n from '@/i18n/config';
import {
  GameStartRequest,
  GameStartResponse,
  GameState,
  StepResponse,
  ActionRequest,
  ActionResponse
} from '@/types/api';

// Re-export types for backward compatibility with existing consumers
export * from '@/types/api';

// Re-export ApiError for backward compatibility
export { ApiError } from '@/lib/api-client';

// Re-export API_BASE_URL for backward compatibility
export { API_BASE_URL } from '@/lib/api-client';

/**
 * Authorized fetch wrapper - Now just an alias for fetchApi
 * Retained for backward compatibility
 */
export const authorizedFetch = fetchApi;

// ==================== Game API ====================

/**
 * Start a new game
 */
export async function startGame(request: GameStartRequest = {}): Promise<GameStartResponse> {
  // Auto-detect current language if not provided
  if (!request.language) {
    request.language = i18n.language?.startsWith('en') ? 'en' : 'zh';
  }

  return fetchApi<GameStartResponse>('/api/game/start', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get current game state
 */
export async function getGameState(gameId: string): Promise<GameState> {
  return fetchApi<GameState>(`/api/game/${gameId}/state`);
}

/**
 * Advance game state by one step
 */
export async function stepGame(gameId: string): Promise<StepResponse> {
  return fetchApi<StepResponse>(`/api/game/${gameId}/step`, {
    method: 'POST',
  });
}

/**
 * Submit a player action
 */
export async function submitAction(
  gameId: string,
  action: ActionRequest
): Promise<ActionResponse> {
  return fetchApi<ActionResponse>(`/api/game/${gameId}/action`, {
    method: 'POST',
    body: JSON.stringify(action),
  });
}

/**
 * Delete a game
 */
export async function deleteGame(gameId: string): Promise<{ success: boolean; message: string }> {
  return fetchApi(`/api/game/${gameId}`, {
    method: 'DELETE',
  });
}

/**
 * Health check
 */
export async function healthCheck(): Promise<{ status: string }> {
  return fetchApi('/health');
}

// ==================== Helper Functions ====================

/**
 * Check if current phase is night
 */
export function isNightPhase(phase: import('@/types/api').GamePhase): boolean {
  return phase.startsWith('night_');
}

/**
 * Check if human player needs to act
 */
export function needsHumanAction(gameState: import('@/types/api').GameState): boolean {
  return gameState.pending_action !== null && gameState.pending_action !== undefined;
}
