/**
 * Preferences API Service
 * Handles user preferences API calls
 */
import { fetchApi } from './api';
import type { NotificationPreferences } from '@/types/notification';

export interface SoundEffectsPreferences {
  enabled: boolean;
  volume: number;
  muted: boolean;
}

export interface UserPreferences {
  sound_effects: SoundEffectsPreferences;
  notifications: NotificationPreferences;
}

export interface UserPreferencesResponse {
  preferences: UserPreferences;
}

/**
 * Get current user's preferences
 */
export async function getUserPreferences(): Promise<UserPreferences> {
  const response = await fetchApi<UserPreferencesResponse>(
    '/api/users/me/preferences',
    { skipRoomToken: true }
  );
  return response.preferences;
}

/**
 * Update current user's preferences
 */
export async function updateUserPreferences(
  preferences: UserPreferences
): Promise<UserPreferences> {
  const response = await fetchApi<UserPreferencesResponse>('/api/users/me/preferences', {
    method: 'PUT',
    body: JSON.stringify(preferences),
    skipRoomToken: true,
  });
  return response.preferences;
}
