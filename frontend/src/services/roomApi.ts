/**
 * Room API Service - handles all room-related HTTP requests
 */

import { saveToken, getAuthHeader } from '@/utils/token';
import { ApiError, GameMode, WolfKingVariant } from '@/services/api';

// 默认空字符串（相对路径），生产环境走 nginx 反代；开发环境需在 .env.development 配置
const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

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
}

export interface RoomPlayer {
  id: number;
  player_id: string;
  nickname: string;
  seat_id: number | null;
  is_ready: boolean;
  is_creator: boolean;
  is_me: boolean;
  user_id: string | null;  // 用户ID（已登录用户），用于重复检测
  joined_at: string;
}

export interface RoomDetail {
  room: Room;
  players: RoomPlayer[];
}

export interface CreateRoomRequest {
  name: string;
  creator_nickname: string;
  creator_id: string;
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
 */
export async function createRoom(request: CreateRoomRequest): Promise<{ room: Room; token: string }> {
  const response = await fetch(`${API_BASE_URL}/api/rooms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new ApiError(response.status, error.detail || 'Failed to create room');
  }

  const data = await response.json();
  saveToken(data.token);
  return data;
}

/**
 * Get list of rooms (optionally filtered by status)
 */
export async function getRooms(status?: 'waiting' | 'playing' | 'finished'): Promise<Room[]> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);

  const response = await fetch(`${API_BASE_URL}/api/rooms?${params}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch rooms' }));
    throw new ApiError(response.status, error.detail || 'Failed to fetch rooms');
  }

  return response.json();
}

/**
 * Get room detail including players
 */
export async function getRoomDetail(roomId: string): Promise<RoomDetail> {
  const response = await fetch(`${API_BASE_URL}/api/rooms/${roomId}`, {
    headers: {
      ...getAuthHeader()
    }
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch room detail' }));
    throw new ApiError(response.status, error.detail || 'Failed to fetch room detail');
  }

  return response.json();
}

/**
 * Join a room
 */
export async function joinRoom(roomId: string, request: JoinRoomRequest): Promise<{ token: string; player_id: string }> {
  const response = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/join`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to join room' }));
    throw new ApiError(response.status, error.detail || 'Failed to join room');
  }

  const data = await response.json();
  saveToken(data.token);
  return data;
}

/**
 * Toggle ready status
 */
export async function toggleReady(roomId: string, playerId: string): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/ready`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify({ player_id: playerId }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to toggle ready' }));
    throw new ApiError(response.status, error.detail || 'Failed to toggle ready');
  }

  const data = await response.json();
  return data.is_ready;
}

/**
 * Start game (creator only)
 */
export async function startGame(roomId: string, playerId: string, fillAi: boolean = false): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/rooms/${roomId}/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify({ player_id: playerId, fill_ai: fillAi }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to start game' }));
    throw new ApiError(response.status, error.detail || 'Failed to start game');
  }

  const data = await response.json();
  return data.game_id;
}

/**
 * Delete a room
 */
export async function deleteRoom(roomId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/rooms/${roomId}`, {
    method: 'DELETE',
    headers: {
      ...getAuthHeader()
    }
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete room' }));
    throw new ApiError(response.status, error.detail || 'Failed to delete room');
  }
}
