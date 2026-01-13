/**
 * Hook for managing current active game/room state
 * Tracks active game ID and room ID for navigation purposes
 */
import { useLocation } from 'react-router-dom';
import { useEffect } from 'react';

const LAST_GAME_ID_KEY = 'lastGameId';
const LAST_ROOM_ID_KEY = 'lastRoomId';

/**
 * Validate UUID format
 */
function isValidUUID(id: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(id);
}

/**
 * Validate numeric ID format
 */
function isValidNumericId(id: string): boolean {
  return /^\d+$/.test(id);
}

/**
 * Save last game ID to localStorage
 */
export function saveLastGameId(gameId: string): void {
  if (isValidUUID(gameId) || isValidNumericId(gameId)) {
    localStorage.setItem(LAST_GAME_ID_KEY, gameId);
  } else {
    console.warn('Invalid game ID format:', gameId);
  }
}

/**
 * Get last game ID from localStorage
 */
export function getLastGameId(): string | null {
  const id = localStorage.getItem(LAST_GAME_ID_KEY);
  if (id && (isValidUUID(id) || isValidNumericId(id))) {
    return id;
  }
  return null;
}

/**
 * Clear last game ID
 */
export function clearLastGameId(): void {
  localStorage.removeItem(LAST_GAME_ID_KEY);
}

/**
 * Save last room ID to localStorage
 */
export function saveLastRoomId(roomId: string): void {
  if (isValidUUID(roomId) || isValidNumericId(roomId)) {
    localStorage.setItem(LAST_ROOM_ID_KEY, roomId);
  } else {
    console.warn('Invalid room ID format:', roomId);
  }
}

/**
 * Get last room ID from localStorage
 */
export function getLastRoomId(): string | null {
  const id = localStorage.getItem(LAST_ROOM_ID_KEY);
  if (id && (isValidUUID(id) || isValidNumericId(id))) {
    return id;
  }
  return null;
}

/**
 * Clear last room ID
 */
export function clearLastRoomId(): void {
  localStorage.removeItem(LAST_ROOM_ID_KEY);
}

interface UseActiveGameReturn {
  gameId: string | null;
  roomId: string | null;
  hasActiveGame: boolean;
  activeUrl: string | null;
  badgeText: string | null;
}

/**
 * Hook to track current active game or room
 * Automatically saves/loads game/room IDs from URL and localStorage
 */
export function useActiveGame(): UseActiveGameReturn {
  const location = useLocation();

  // Extract gameId from URL if on game page
  const gameIdMatch = location.pathname.match(/\/game\/([^/]+)/);
  const currentGameId = gameIdMatch ? gameIdMatch[1] : null;

  // Extract roomId from URL if on room waiting page
  const roomIdMatch = location.pathname.match(/\/room\/([^/]+)\/waiting/);
  const currentRoomId = roomIdMatch ? roomIdMatch[1] : null;

  // Save to localStorage when navigating to game/room pages
  useEffect(() => {
    if (currentGameId && (isValidUUID(currentGameId) || isValidNumericId(currentGameId))) {
      saveLastGameId(currentGameId);
      // Clear room ID when entering game
      clearLastRoomId();
    }
  }, [currentGameId]);

  useEffect(() => {
    if (currentRoomId && (isValidUUID(currentRoomId) || isValidNumericId(currentRoomId))) {
      saveLastRoomId(currentRoomId);
      // Don't clear game ID - user might return to it
    }
  }, [currentRoomId]);

  // Try to get from localStorage as fallback (only if not currently in a room)
  const storedGameId = !currentRoomId ? getLastGameId() : null;
  const activeGameId = currentGameId || storedGameId;

  const hasActiveGame = !!(activeGameId || currentRoomId);

  let activeUrl: string | null = null;
  let badgeText: string | null = null;

  if (activeGameId) {
    activeUrl = `/game/${activeGameId}`;
    badgeText = 'Live';
  } else if (currentRoomId) {
    activeUrl = `/room/${currentRoomId}/waiting`;
    badgeText = 'Waiting';
  }

  return {
    gameId: activeGameId,
    roomId: currentRoomId,
    hasActiveGame,
    activeUrl,
    badgeText,
  };
}
