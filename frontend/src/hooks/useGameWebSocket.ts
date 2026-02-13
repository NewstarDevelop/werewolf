/**
 * useGameWebSocket Hook - Real-time game state updates via WebSocket
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { GameState, MessageInGame } from '@/services/api';
import { useQueryClient } from '@tanstack/react-query';
import { buildWebSocketUrl, getAuthSubprotocols } from '@/utils/websocket';

interface UseGameWebSocketOptions {
  gameId: string | null;
  enabled?: boolean;
  onError?: (error: Error) => void;
  onFirstUpdate?: () => void;
}

type WebSocketMessage =
  | { type: 'game_update' | 'connected'; data: GameState }
  | { type: 'error'; data: { message?: string } & Record<string, unknown> }
  | { type: 'pong'; data?: never };

// Message deduplication helper
function mergeMessages(oldMessages: MessageInGame[], newMessages: MessageInGame[]): MessageInGame[] {
  // Server message_log is authoritative; do not dedupe to avoid dropping valid duplicates.
  return Array.isArray(newMessages) ? newMessages : oldMessages;
}

export function useGameWebSocket({ gameId, enabled = true, onError, onFirstUpdate }: UseGameWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const pingIntervalRef = useRef<NodeJS.Timeout>();
  const shouldReconnectRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const MAX_RECONNECT_DELAY = 30000; // 30s max
  const BASE_RECONNECT_DELAY = 3000; // 3s base
  const onErrorRef = useRef(onError);
  const onFirstUpdateRef = useRef(onFirstUpdate);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Keep refs updated
  useEffect(() => {
    onErrorRef.current = onError;
    onFirstUpdateRef.current = onFirstUpdate;
  });

  // Unified state update handler for both 'connected' and 'game_update' messages
  const applyIncomingState = useCallback(
    (incoming: GameState) => {
      queryClient.setQueryData(['gameState', gameId], (old: GameState | undefined) => {
        const incomingVersion = incoming?.state_version;
        const oldVersion = old?.state_version;

        // Version check: reject strictly older updates (allow equal versions)
        if (
          old &&
          typeof incomingVersion === 'number' &&
          typeof oldVersion === 'number' &&
          incomingVersion < oldVersion
        ) {
          console.warn(`[WebSocket] Stale update rejected (v${incomingVersion} < v${oldVersion})`);
          return old;
        }

        // Data integrity check
        const isComplete = Array.isArray(incoming?.message_log) && Array.isArray(incoming?.players);
        if (!isComplete) {
          console.warn('[WebSocket] Incomplete data, triggering refetch');
          queryClient.invalidateQueries({ queryKey: ['gameState', gameId] });
          return old;
        }

        const merged = {
          ...incoming,
          message_log: mergeMessages(old?.message_log || [], incoming.message_log),
        };

        if (onFirstUpdateRef.current) {
          onFirstUpdateRef.current();
        }

        return merged;
      });
    },
    [queryClient, gameId]
  );

  // Cleanup function
  const cleanup = useCallback(() => {
    shouldReconnectRef.current = false;
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // Send ping to keep connection alive
  const sendPing = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send('ping');
      } catch (error) {
        console.error('Failed to send ping:', error);
      }
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!gameId || !enabled) return;

    cleanup();

    try {
      // Use shared WebSocket utilities for URL and auth
      const wsUrl = buildWebSocketUrl(`/ws/game/${gameId}`);

      console.log('[WebSocket] Connecting to:', wsUrl);

      // Security: Use Sec-WebSocket-Protocol to pass token instead of query string
      // This prevents token leakage in server logs, browser history, and Referer headers
      const ws = new WebSocket(wsUrl, getAuthSubprotocols());
      wsRef.current = ws;
      shouldReconnectRef.current = true;

      ws.onopen = () => {
        console.log('[WebSocket] Connected to game', gameId);
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptRef.current = 0; // Reset backoff on successful connection

        // Start ping interval to keep connection alive
        pingIntervalRef.current = setInterval(sendPing, 30000); // Ping every 30s
      };

      ws.onmessage = (event) => {
        try {
          if (event.data === 'pong') return;
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('[WebSocket] Received message:', message.type);

          if (message.type === 'game_update' || message.type === 'connected') {
            // Unified handling for both message types with version control
            applyIncomingState(message.data);
          } else if (message.type === 'error') {
            console.error('[WebSocket] Server error:', message.data);
            setConnectionError(message.data.message || 'WebSocket error');
            if (onErrorRef.current) {
              onErrorRef.current(new Error(message.data.message || 'WebSocket error'));
            }
          }
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event);
        setConnectionError('WebSocket connection error');
        if (onErrorRef.current) {
          onErrorRef.current(new Error('WebSocket connection error'));
        }
      };

      ws.onclose = (event) => {
        console.log('[WebSocket] Disconnected:', event.code, event.reason);
        setIsConnected(false);

        // Attempt to reconnect with exponential backoff (unless intentionally closed)
        if (event.code !== 1000 && enabled && shouldReconnectRef.current) {
          const delay = Math.min(BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptRef.current), MAX_RECONNECT_DELAY);
          reconnectAttemptRef.current += 1;
          console.log(`[WebSocket] Reconnecting in ${delay / 1000}s (attempt ${reconnectAttemptRef.current})...`);
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      setConnectionError('Failed to establish WebSocket connection');
      if (onErrorRef.current) {
        onErrorRef.current(error as Error);
      }

      // Retry connection with exponential backoff
      if (enabled && shouldReconnectRef.current) {
        const delay = Math.min(BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptRef.current), MAX_RECONNECT_DELAY);
        reconnectAttemptRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      }
    }
  }, [gameId, enabled, cleanup, sendPing, applyIncomingState]); // Removed onError, onFirstUpdate from deps to avoid infinite reconnects

  // Connect on mount and when gameId changes
  useEffect(() => {
    if (gameId && enabled) {
      connect();
    }

    return cleanup;
  }, [gameId, enabled, connect, cleanup]); // connect and cleanup are stable refs via useCallback

  return {
    isConnected,
    connectionError,
    reconnect: connect,
  };
}
