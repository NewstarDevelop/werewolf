export interface UserBrief {
  id: number;
  email: string;
  nickname: string;
  avatar_url: string | null;
  is_admin: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserBrief;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  nickname: string;
}

export interface Room {
  id: number;
  name: string;
  owner_id: number;
  mode: 'classic_9' | 'classic_12';
  variant: 'wolf_king' | 'white_wolf_king' | null;
  language: 'zh' | 'en';
  max_players: number;
  status: 'waiting' | 'playing' | 'finished';
  players: RoomPlayer[];
  created_at: string;
}

export interface RoomPlayer {
  user_id: number;
  nickname: string | null;
  seat: number;
  is_ready: boolean;
  is_ai: boolean;
  ai_provider: string | null;
}

export interface RoomListItem {
  id: number;
  name: string;
  owner_id: number;
  mode: 'classic_9' | 'classic_12';
  variant: 'wolf_king' | 'white_wolf_king' | null;
  language: 'zh' | 'en';
  max_players: number;
  player_count: number;
  status: 'waiting' | 'playing' | 'finished';
  created_at: string;
}

export interface RoomListResponse {
  items: RoomListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface RoomCreateRequest {
  name: string;
  mode: 'classic_9' | 'classic_12';
  variant?: 'wolf_king' | 'white_wolf_king' | null;
  language?: 'zh' | 'en';
}

export interface GameEvent {
  type: string;
  phase: string;
  data: unknown;
  timestamp: string;
}
