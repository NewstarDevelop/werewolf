/**
 * useGameWebSocket Hook - Real-time game state updates via WebSocket
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { GameState } from '@/services/api';
import { useQueryClient } from '@tanstack/react-query';
import { getToken } from '@/utils/token';

interface UseGameWebSocketOptions {
  gameId: string | null;
  enabled?: boolean;
  onError?: (error: Error) => void;
  onFirstUpdate?: () => void;
}

interface WebSocketMessage {
  type: 'game_update' | 'connected' | 'error' | 'pong';
  data: any;
}

// Message deduplication helper
function mergeMessages(oldMessages: any[], newMessages: any[]): any[] {
  // Server message_log is authoritative; do not dedupe to avoid dropping valid duplicates.
  return Array.isArray(newMessages) ? newMessages : oldMessages;
}

export function useGameWebSocket({ gameId, enabled = true, onError, onFirstUpdate }: UseGameWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const pingIntervalRef = useRef<NodeJS.Timeout>();
  const shouldReconnectRef = useRef(false);
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
      // Determine WebSocket URL based on environment
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = import.meta.env.VITE_API_URL
        ? new URL(import.meta.env.VITE_API_URL).host
        : window.location.host;
      const wsUrl = `${protocol}//${host}/api/ws/game/${gameId}?token=${encodeURIComponent(getToken() || '')}`;

      console.log('[WebSocket] Connecting to:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      shouldReconnectRef.current = true;

      ws.onopen = () => {
        console.log('[WebSocket] Connected to game', gameId);
        setIsConnected(true);
        setConnectionError(null);

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

        // Attempt to reconnect after delay (unless intentionally closed)
        if (event.code !== 1000 && enabled && shouldReconnectRef.current) {
          console.log('[WebSocket] Reconnecting in 3 seconds...');
          reconnectTimeoutRef.current = setTimeout(connect, 3000);
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      setConnectionError('Failed to establish WebSocket connection');
      if (onErrorRef.current) {
        onErrorRef.current(error as Error);
      }

      // Retry connection after delay
      if (enabled && shouldReconnectRef.current) {
        reconnectTimeoutRef.current = setTimeout(connect, 5000);
      }
    }
  }, [gameId, enabled, cleanup, sendPing, applyIncomingState]); // 移除 onError, onFirstUpdate 依赖

  // Connect on mount and when gameId changes
  useEffect(() => {
    if (gameId && enabled) {
      connect();
    }

    return cleanup;
  }, [gameId, enabled]); // 移除 connect 和 cleanup 依赖避免无限重连

  return {
    isConnected,
    connectionError,
    reconnect: connect,
  };
}
