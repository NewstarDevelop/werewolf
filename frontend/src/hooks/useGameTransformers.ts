import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { GameState, Role, Player } from '@/services/api';
import { translateSystemMessage } from '@/utils/messageTranslator';

export interface UIPlayer {
  id: number;
  name: string;
  isUser: boolean;
  isAlive: boolean;
  role?: Role;
  seatId: number;
}

export function useGameTransformers(gameState: GameState | null | undefined) {
  const { t } = useTranslation(['common', 'game']);
  const isGameOver = gameState?.status === 'finished';

  const players = useMemo<UIPlayer[]>(() => {
    if (!gameState) return [];
    return [...gameState.players]
      .sort((a, b) => a.seat_id - b.seat_id)
      .map((p) => {
        // WL-008 Fix: Use my_seat to identify current player, not is_human
        // is_human means "is this seat a human player" (multiple can be true in multiplayer)
        // my_seat identifies "which seat belongs to the requesting player"
        const isMe = p.seat_id === gameState.my_seat;
        return {
          id: p.seat_id,
          name: isMe ? t('common:player.you') : p.name || t('common:player.default_name', { id: p.seat_id }),
          isUser: isMe,
          isAlive: p.is_alive,
          role: isMe ? gameState.my_role : (isGameOver ? (p.role ?? undefined) : undefined),
          seatId: p.seat_id,
        };
      });
  }, [gameState, isGameOver, t]);

  const playerMap = useMemo(() => {
    if (!gameState) return new Map<number, Player>();
    return new Map(gameState.players.map(p => [p.seat_id, p]));
  }, [gameState?.players]);

  const messages = useMemo(() => {
    if (!gameState) return [];
    return gameState.message_log.map((m, idx) => {
      const player = playerMap.get(m.seat_id);
      const isSystem = m.type === "system" || m.seat_id === 0;
      const isUser = m.seat_id === gameState.my_seat;
      const messageText = isSystem ? translateSystemMessage(m.text, t) : m.text;

      return {
        id: idx + 1,
        sender: isSystem ? t('common:player.system') : isUser ? t('common:player.you') : player?.name || t('common:player.seat', { id: m.seat_id }),
        message: messageText,
        isUser,
        isSystem,
        timestamp: "",
        day: m.day,
      };
    });
  }, [gameState, playerMap, t]);

  return { players, playerMap, messages };
}
