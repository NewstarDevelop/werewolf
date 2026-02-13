/**
 * Room API Service - handles all room-related HTTP requests
 */

import { saveToken } from '@/utils/token';
import { GameMode, WolfKingVariant } from '@/services/api';
import { fetchApi } from '@/lib/api-client';

// ==================== Types ====================

export interface Room {
  id: string;
  name: string;
  creator_nickname: string;
  status: 'waiting' | 'playing' | 'finished';
  current_players: number;
  max_players: number;
  created_at: string;
  game_mode: GameMode;
  wolf_king_variant?: WolfKingVariant;
  game_id?: string;  // FIX: 当房间状态为 PLAYING 时返回 game_id，用于非房主玩家导航
}

export interface RoomPlayer {
  id: number;
  player_id: string;
  nickname: string;
  seat_id: number | null;
  is_ready: boolean;
  is_creator: boolean;
  is_me: boolean;
  joined_at: string;
}

export interface RoomDetail {
  room: Room;
  players: RoomPlayer[];
  has_same_user: boolean;  // P1-SEC-004: 当前登录用户是否已在房间中
}

export interface CreateRoomRequest {
  name: string;
  game_mode: GameMode;
  wolf_king_variant?: WolfKingVariant;
  language?: string;
}

export interface JoinRoomRequest {
  player_id: string;
  nickname: string;
}

// ==================== API Functions ====================

/**
 * Create a new room
 * Requires user authentication (uses HttpOnly cookie)
 */
export async function createRoom(request: CreateRoomRequest): Promise<{ room: Room; token: string }> {
  const data = await fetchApi<{ room: Room; token: string }>('/api/rooms', {
    method: 'POST',
    body: JSON.stringify(request),
    skipRoomToken: true,
    skipRetry: true,
  });
  saveToken(data.token);
  return data;
}

/**
 * Get list of rooms (optionally filtered by status)
 */
export async function getRooms(status?: 'waiting' | 'playing' | 'finished'): Promise<Room[]> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);

  return fetchApi<Room[]>(`/api/rooms?${params}`, {
    skipRoomToken: true,
  });
}

/**
 * Get room detail including players
 */
export async function getRoomDetail(roomId: string): Promise<RoomDetail> {
  return fetchApi<RoomDetail>(`/api/rooms/${roomId}`);
}

/**
 * Join a room
 * Requires user authentication (uses HttpOnly cookie)
 */
export async function joinRoom(roomId: string, request: JoinRoomRequest): Promise<{ token: string; player_id: string }> {
  const data = await fetchApi<{ token: string; player_id: string }>(`/api/rooms/${roomId}/join`, {
    method: 'POST',
    body: JSON.stringify(request),
    skipRoomToken: true,
    skipRetry: true,
  });
  saveToken(data.token);
  return data;
}

/**
 * Toggle ready status
 */
export async function toggleReady(roomId: string, playerId: string): Promise<boolean> {
  const data = await fetchApi<{ is_ready: boolean }>(`/api/rooms/${roomId}/ready`, {
    method: 'POST',
    body: JSON.stringify({ player_id: playerId }),
    skipRetry: true,
  });
  return data.is_ready;
}

/**
 * Start game (creator only)
 */
export async function startGame(roomId: string, playerId: string, fillAi: boolean = false): Promise<string> {
  const data = await fetchApi<{ game_id: string }>(`/api/rooms/${roomId}/start`, {
    method: 'POST',
    body: JSON.stringify({ player_id: playerId, fill_ai: fillAi }),
    skipRetry: true,
  });
  return data.game_id;
}

/**
 * Leave a room (non-creator only)
 */
export async function leaveRoom(roomId: string): Promise<void> {
  await fetchApi<void>(`/api/rooms/${roomId}/leave`, {
    method: 'POST',
    skipRetry: true,
  });
}

/**
 * Delete a room
 */
export async function deleteRoom(roomId: string): Promise<void> {
  await fetchApi<void>(`/api/rooms/${roomId}`, {
    method: 'DELETE',
  });
}
