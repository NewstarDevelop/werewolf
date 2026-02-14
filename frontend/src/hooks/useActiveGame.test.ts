/**
 * useActiveGame utility function tests
 *
 * Tests ID validation, localStorage persistence, and clear logic.
 * (The useActiveGame hook itself requires react-router and is tested indirectly.)
 */
import { describe, it, expect, beforeEach } from 'vitest';
import {
  saveLastGameId,
  getLastGameId,
  clearLastGameId,
  saveLastRoomId,
  getLastRoomId,
  clearLastRoomId,
} from './useActiveGame';

describe('useActiveGame utilities', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // --- saveLastGameId / getLastGameId ---
  describe('game ID persistence', () => {
    it('saves and retrieves a valid UUID game ID', () => {
      const uuid = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
      expect(saveLastGameId(uuid)).toBe(true);
      expect(getLastGameId()).toBe(uuid);
    });

    it('saves and retrieves a numeric game ID', () => {
      expect(saveLastGameId('42')).toBe(true);
      expect(getLastGameId()).toBe('42');
    });

    it('rejects invalid game ID format', () => {
      expect(saveLastGameId('not-valid')).toBe(false);
      expect(getLastGameId()).toBeNull();
    });

    it('rejects empty string', () => {
      expect(saveLastGameId('')).toBe(false);
    });

    it('rejects ID with special characters', () => {
      expect(saveLastGameId('abc<script>')).toBe(false);
    });

    it('returns null when nothing stored', () => {
      expect(getLastGameId()).toBeNull();
    });
  });

  // --- clearLastGameId ---
  describe('clearLastGameId', () => {
    it('clears stored game ID', () => {
      saveLastGameId('12345');
      clearLastGameId();
      expect(getLastGameId()).toBeNull();
    });

    it('does not throw when nothing to clear', () => {
      expect(() => clearLastGameId()).not.toThrow();
    });
  });

  // --- saveLastRoomId / getLastRoomId ---
  describe('room ID persistence', () => {
    it('saves and retrieves a valid UUID room ID', () => {
      const uuid = 'f1e2d3c4-b5a6-7890-abcd-ef1234567890';
      expect(saveLastRoomId(uuid)).toBe(true);
      expect(getLastRoomId()).toBe(uuid);
    });

    it('saves and retrieves a numeric room ID', () => {
      expect(saveLastRoomId('7')).toBe(true);
      expect(getLastRoomId()).toBe('7');
    });

    it('rejects invalid room ID', () => {
      expect(saveLastRoomId('../etc/passwd')).toBe(false);
      expect(getLastRoomId()).toBeNull();
    });

    it('returns null when nothing stored', () => {
      expect(getLastRoomId()).toBeNull();
    });
  });

  // --- clearLastRoomId ---
  describe('clearLastRoomId', () => {
    it('clears stored room ID', () => {
      saveLastRoomId('99');
      clearLastRoomId();
      expect(getLastRoomId()).toBeNull();
    });
  });

  // --- isolation ---
  describe('isolation', () => {
    it('game and room IDs are independent', () => {
      saveLastGameId('111');
      saveLastRoomId('222');
      clearLastGameId();
      expect(getLastGameId()).toBeNull();
      expect(getLastRoomId()).toBe('222');
    });
  });
});
