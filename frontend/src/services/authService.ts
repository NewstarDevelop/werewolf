/**
 * Authentication API service.
 *
 * Security: Uses credentials: 'include' to send HttpOnly cookies
 */
import { getUserAuthHeader, saveUserToken, clearUserToken } from '@/utils/token';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8082';

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

export const authService = {
  async register(email: string, password: string, nickname: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      credentials: 'include',  // Send cookies
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, nickname }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    const data = await response.json();
    saveUserToken(data.access_token);
    return data;
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      credentials: 'include',  // Send cookies
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    saveUserToken(data.access_token);
    return data;
  },

  async logout(): Promise<void> {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',  // Send cookies
        headers: getUserAuthHeader(),
      });
    } finally {
      clearUserToken();
    }
  },

  async getLinuxdoAuthUrl(nextUrl: string = '/lobby'): Promise<string> {
    const response = await fetch(
      `${API_BASE}/api/auth/oauth/linuxdo?next=${encodeURIComponent(nextUrl)}`,
      {
        credentials: 'include',  // Send cookies
        headers: getUserAuthHeader()
      }
    );

    if (!response.ok) {
      throw new Error('Failed to get OAuth URL');
    }

    const data = await response.json();
    return data.authorize_url;
  },

  async getCurrentUser(): Promise<User> {
    const response = await fetch(`${API_BASE}/api/users/me`, {
      credentials: 'include',  // Send cookies
      headers: getUserAuthHeader(),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch user');
    }

    return response.json();
  },

  async updateProfile(updates: { nickname?: string; bio?: string; avatar_url?: string }): Promise<User> {
    const response = await fetch(`${API_BASE}/api/users/me`, {
      method: 'PUT',
      credentials: 'include',  // Send cookies
      headers: {
        ...getUserAuthHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      throw new Error('Failed to update profile');
    }

    return response.json();
  },

  async getStats(): Promise<any> {
    const response = await fetch(`${API_BASE}/api/users/me/stats`, {
      credentials: 'include',  // Send cookies
      headers: getUserAuthHeader(),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch stats');
    }

    return response.json();
  },
};
