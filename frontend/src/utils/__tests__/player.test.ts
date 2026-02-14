/**
 * player utility Tests
 *
 * Tests player ID generation, nickname storage, and data clearing.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { getPlayerId, getNickname, setNickname, clearPlayerData } from '../player';

describe('player utilities', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  // --- getPlayerId ---
  describe('getPlayerId', () => {
    it('generates and persists a player ID', () => {
      const id = getPlayerId();
      expect(id).toBeTruthy();
      expect(typeof id).toBe('string');
      expect(id.length).toBeGreaterThan(0);
    });

    it('returns the same ID on subsequent calls', () => {
      const id1 = getPlayerId();
      const id2 = getPlayerId();
      expect(id1).toBe(id2);
    });

    it('stores ID in localStorage', () => {
      const id = getPlayerId();
      expect(localStorage.getItem('werewolf_player_id')).toBe(id);
    });

    it('generates UUID-like format', () => {
      const id = getPlayerId();
      // Should match UUID v4 pattern
      expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    });
  });

  // --- getNickname / setNickname ---
  describe('nickname', () => {
    it('returns null when no nickname set', () => {
      expect(getNickname()).toBeNull();
    });

    it('stores and retrieves nickname', () => {
      setNickname('TestPlayer');
      expect(getNickname()).toBe('TestPlayer');
    });

    it('overwrites existing nickname', () => {
      setNickname('First');
      setNickname('Second');
      expect(getNickname()).toBe('Second');
    });
  });

  // --- clearPlayerData ---
  describe('clearPlayerData', () => {
    it('clears player ID and nickname from localStorage', () => {
      getPlayerId();
      setNickname('Test');
      clearPlayerData();
      expect(localStorage.getItem('werewolf_player_id')).toBeNull();
      expect(localStorage.getItem('werewolf_player_nickname')).toBeNull();
    });

    it('clears auth token from localStorage', () => {
      localStorage.setItem('user_auth_token', 'abc123');
      clearPlayerData();
      expect(localStorage.getItem('user_auth_token')).toBeNull();
    });

    it('clears session storage tokens', () => {
      sessionStorage.setItem('werewolf_token', 'tok');
      sessionStorage.setItem('werewolf_token_expiry', '999');
      clearPlayerData();
      expect(sessionStorage.getItem('werewolf_token')).toBeNull();
      expect(sessionStorage.getItem('werewolf_token_expiry')).toBeNull();
    });
  });
});
