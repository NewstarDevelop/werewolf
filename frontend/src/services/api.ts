/**
 * API Service for Werewolf Game Backend
 * Handles all HTTP requests to the FastAPI backend
 *
 * Security: Uses credentials: 'include' to send HttpOnly cookies
 */

import { getAuthHeader } from '@/utils/token';

// 默认空字符串（相对路径），生产环境走 nginx 反代；开发环境需在 .env.development 配置
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

/**
 * Authorized fetch wrapper for components that need JWT authentication
 * Use this for API calls outside of the main game flow (logs, debug, analysis)
 *
 * Security: Includes credentials to send HttpOnly cookies
 */
export async function authorizedFetch<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    credentials: 'include',  // Send HttpOnly cookies
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    }
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, errorData.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Types matching backend schemas
export type Role = 'werewolf' | 'villager' | 'seer' | 'witch' | 'hunter';
export type GameStatus = 'waiting' | 'playing' | 'finished';
export type GamePhase =
  | 'night_start'
  | 'night_werewolf_chat'
  | 'night_werewolf'
  | 'night_seer'
  | 'night_witch'
  | 'day_announcement'
  | 'day_last_words'
  | 'day_speech'
  | 'day_vote'
  | 'day_vote_result'
  | 'hunter_shoot'
  | 'game_over';
export type ActionType = 'kill' | 'verify' | 'save' | 'poison' | 'vote' | 'shoot' | 'speak' | 'skip';
// WL-013 Fix: Sync with backend MessageType enum
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

// API Error class
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

// Generic fetch wrapper with error handling, timeout, and retry
// CRITICAL FIXES APPLIED:
// - C1: Only retry idempotent methods (GET/HEAD) to prevent duplicate POST actions
// - C2: Always clear timeout in finally block to prevent timer leaks
// - C3: Support external AbortSignal and distinguish from timeout aborts
async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders: HeadersInit = {
    'Content-Type': 'application/json',
    ...getAuthHeader() // Auto-add JWT token if available
  };

  // C1 FIX: Only retry idempotent methods (GET/HEAD) to prevent duplicate POST actions
  const method = (options.method || 'GET').toUpperCase();
  const isIdempotent = ['GET', 'HEAD'].includes(method);
  const MAX_RETRIES = isIdempotent ? 3 : 0; // POST/PUT/DELETE/PATCH do not retry
  let retryCount = 0;

  while (true) {
    // C2 & C3 FIX: Create controller and timeout for each attempt
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

    // C3 FIX: Support external AbortSignal - listen and forward abort
    if (options.signal) {
      options.signal.addEventListener('abort', () => {
        controller.abort();
      }, { once: true });
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...defaultHeaders,
          ...options.headers,
        },
        signal: controller.signal,
      });

      // C2 FIX: Clear timeout on success
      clearTimeout(timeoutId);

      if (!response.ok) {
        // If 5xx error and idempotent, retry
        if (response.status >= 500 && retryCount < MAX_RETRIES) {
          throw new Error(`Server Error ${response.status}`);
        }

        let detail = 'Unknown error';
        try {
          const errorData = await response.json();
          detail = errorData.detail || errorData.message || JSON.stringify(errorData);
        } catch {
          detail = response.statusText;
        }
        throw new ApiError(response.status, detail);
      }

      return response.json();
    } catch (error) {
      // C2 FIX: Always clear timeout, even on error
      clearTimeout(timeoutId);

      // C3 FIX: Distinguish external abort from timeout abort
      const isExternalAbort = options.signal?.aborted;
      const isTimeoutAbort = error instanceof Error && error.name === 'AbortError' && !isExternalAbort;
      const isNetworkError = error instanceof Error &&
        (error.name === 'TypeError' || error.message.includes('Failed to fetch') || error.message.includes('Server Error'));

      // External abort should not retry - user explicitly cancelled
      if (isExternalAbort) {
        throw error;
      }

      // Only retry on network errors or timeout (and only for idempotent methods)
      if ((isNetworkError || isTimeoutAbort) && retryCount < MAX_RETRIES) {
        retryCount++;
        const delay = Math.pow(2, retryCount) * 1000; // 2s, 4s, 8s
        console.log(`API request failed, retrying... (${MAX_RETRIES - retryCount + 1} attempts left) in ${delay}ms`);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }

      throw error;
    }
  }
}

// ==================== Game API ====================

/**
 * Start a new game
 */
export async function startGame(request: GameStartRequest = {}): Promise<GameStartResponse> {
  // Auto-detect current language if not provided
  if (!request.language) {
    request.language = 'zh'; // Default, caller should provide specific language
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
export function isNightPhase(phase: GamePhase): boolean {
  return phase.startsWith('night_');
}

/**
 * Check if human player needs to act
 */
export function needsHumanAction(gameState: GameState): boolean {
  return gameState.pending_action !== null && gameState.pending_action !== undefined;
}
