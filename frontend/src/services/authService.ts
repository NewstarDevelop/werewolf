/**
 * Authentication API service.
 *
 * Security: Uses HttpOnly cookies as primary authentication mechanism.
 * Token storage in localStorage has been removed to prevent XSS attacks.
 *
 * Uses fetchApi for unified timeout, retry, and error handling.
 * skipRoomToken is set to true for all calls since auth APIs should
 * only rely on HttpOnly cookie authentication, not room tokens.
 */
import { clearUserToken } from '@/utils/token';
import { fetchApi, ApiError } from '@/lib/api-client';

export interface User {
  id: string;
  email: string | null;
  nickname: string;
  avatar_url: string | null;
  bio: string | null;
  is_email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface UserStats {
  games_played: number;
  games_won: number;
  win_rate: number;
  recent_games: Array<{
    game_id: string;
    seat_id: number;
    role: string;
    is_winner: boolean;
    created_at: string | null;
  }>;
}

export class AuthError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = 'AuthError';
  }
}

/**
 * Convert ApiError to AuthError for backward compatibility with consumers.
 */
function toAuthError(error: unknown): AuthError {
  if (error instanceof ApiError) {
    return new AuthError(error.detail, error.status);
  }
  if (error instanceof Error) {
    return new AuthError(error.message, 0);
  }
  return new AuthError('Unknown error', 0);
}

export const authService = {
  async register(email: string, password: string, nickname: string): Promise<AuthResponse> {
    try {
      return await fetchApi<AuthResponse>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, nickname }),
        skipRoomToken: true,
        skipRetry: true,
      });
    } catch (error) {
      throw toAuthError(error);
    }
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    try {
      return await fetchApi<AuthResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
        skipRoomToken: true,
        skipRetry: true,
      });
    } catch (error) {
      throw toAuthError(error);
    }
  },

  async logout(): Promise<void> {
    try {
      await fetchApi<void>('/api/auth/logout', {
        method: 'POST',
        skipRoomToken: true,
        skipRetry: true,
      });
    } catch (error) {
      console.error('Logout API call failed:', error);
    } finally {
      clearUserToken();
    }
  },

  async getLinuxdoAuthUrl(nextUrl: string = '/lobby'): Promise<string> {
    const data = await fetchApi<{ authorize_url: string }>(
      `/api/auth/oauth/linuxdo?next=${encodeURIComponent(nextUrl)}`,
      { skipRoomToken: true }
    );
    return data.authorize_url;
  },

  async getCurrentUser(): Promise<User> {
    try {
      return await fetchApi<User>('/api/users/me', {
        skipRoomToken: true,
      });
    } catch (error) {
      throw toAuthError(error);
    }
  },

  async updateProfile(updates: { nickname?: string; bio?: string; avatar_url?: string }): Promise<User> {
    return fetchApi<User>('/api/users/me', {
      method: 'PUT',
      body: JSON.stringify(updates),
      skipRoomToken: true,
      skipRetry: true,
    });
  },

  async getStats(): Promise<UserStats> {
    return fetchApi<UserStats>('/api/users/me/stats', {
      skipRoomToken: true,
    });
  },
};
