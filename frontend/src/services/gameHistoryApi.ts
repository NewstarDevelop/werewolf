/**
 * Game History API Service
 */

import { authorizedFetch } from '@/services/api';

export interface PlayerInfo {
  nickname: string;
  role: string;
  is_winner: boolean;
}

export interface GameHistoryItem {
  game_id: string;
  room_name: string;
  started_at: string;
  finished_at: string;
  winner: 'werewolf' | 'villager' | 'unknown';
  player_count: number;
  my_role: string;
  is_winner: boolean;
}

export interface GameHistoryDetail extends GameHistoryItem {
  players: PlayerInfo[];
  duration_seconds: number;
}

export interface GameHistoryListResponse {
  games: GameHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Get user's game history list with optional filtering and pagination
 */
export async function getGameHistory(
  winner?: 'werewolf' | 'villager',
  page: number = 1,
  pageSize: number = 20
): Promise<GameHistoryListResponse> {
  const params = new URLSearchParams();
  if (winner) params.append('winner', winner);
  params.append('page', page.toString());
  params.append('page_size', pageSize.toString());

  const queryString = params.toString();
  return authorizedFetch<GameHistoryListResponse>(
    `/api/game-history${queryString ? `?${queryString}` : ''}`
  );
}

/**
 * Get detailed information about a specific game
 */
export async function getGameHistoryDetail(gameId: string): Promise<GameHistoryDetail> {
  return authorizedFetch<GameHistoryDetail>(`/api/game-history/${gameId}`);
}
