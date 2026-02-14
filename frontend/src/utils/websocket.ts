/**
 * WebSocket Utilities
 *
 * Provides unified WebSocket URL construction and authentication helpers.
 * Used by useGameWebSocket and useNotificationWebSocket.
 */
import { getToken } from './token';

/**
 * Build WebSocket URL based on environment configuration.
 *
 * @param path - WebSocket endpoint path (e.g., '/ws/game/123')
 * @returns Full WebSocket URL with correct protocol
 */
export function buildWebSocketUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_API_URL
    ? new URL(import.meta.env.VITE_API_URL).host
    : window.location.host;

  // Ensure path starts with /api
  const normalizedPath = path.startsWith('/api') ? path : `/api${path}`;

  return `${protocol}//${host}${normalizedPath}`;
}

/**
 * Get WebSocket subprotocols for authentication.
 *
 * Uses Sec-WebSocket-Protocol header to pass JWT token securely.
 * Server will respond with 'auth' subprotocol to confirm.
 *
 * @returns Array of subprotocols: ['auth', '<token>']
 */
export function getAuthSubprotocols(): string[] {
  const token = getToken();
  if (!token) {
    return ['auth'];
  }
  return ['auth', token];
}

/**
 * Create authenticated WebSocket connection.
 *
 * @param url - WebSocket URL
 * @returns WebSocket instance with auth subprotocols
 */
export function createAuthenticatedWebSocket(url: string): WebSocket {
  return new WebSocket(url, getAuthSubprotocols());
}
