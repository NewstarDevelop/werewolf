/**
 * useGameTransformers Hook Tests
 *
 * Tests player/message data transformation logic.
 */
import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useGameTransformers } from './useGameTransformers';
import type { GameState } from '@/types/api';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      const map: Record<string, string> = {
        'common:player.you': 'You',
        'common:player.system': 'System',
      };
      if (key === 'common:player.default_name') return `Player ${opts?.id}`;
      if (key === 'common:player.seat') return `Seat ${opts?.id}`;
      return map[key] || key;
    },
  }),
}));

// Mock messageTranslator
vi.mock('@/utils/messageTranslator', () => ({
  translateSystemMessage: (text: string) => text,
}));

function makeGameState(overrides: Partial<GameState> = {}): GameState {
  return {
    game_id: 'g1',
    status: 'playing',
    state_version: 1,
    day: 1,
    phase: 'day_speech',
    my_seat: 1,
    my_role: 'seer',
    players: [
      { seat_id: 1, is_alive: true, is_human: true, name: 'Alice' },
      { seat_id: 2, is_alive: true, is_human: false, name: 'Bob' },
      { seat_id: 3, is_alive: false, is_human: false, name: 'Charlie' },
    ],
    message_log: [],
    wolf_teammates: [],
    verified_results: {},
    ...overrides,
  };
}

describe('useGameTransformers', () => {
  // --- players ---
  it('returns empty arrays for null state', () => {
    const { result } = renderHook(() => useGameTransformers(null));
    expect(result.current.players).toEqual([]);
    expect(result.current.messages).toEqual([]);
  });

  it('transforms players and marks current user', () => {
    const { result } = renderHook(() => useGameTransformers(makeGameState()));
    expect(result.current.players).toHaveLength(3);
    const me = result.current.players.find(p => p.id === 1);
    expect(me?.name).toBe('You');
    expect(me?.isUser).toBe(true);
    expect(me?.role).toBe('seer');
  });

  it('sorts players by seat_id', () => {
    const gs = makeGameState({
      players: [
        { seat_id: 3, is_alive: true, is_human: false, name: 'C' },
        { seat_id: 1, is_alive: true, is_human: true, name: 'A' },
        { seat_id: 2, is_alive: true, is_human: false, name: 'B' },
      ],
    });
    const { result } = renderHook(() => useGameTransformers(gs));
    expect(result.current.players.map(p => p.id)).toEqual([1, 2, 3]);
  });

  it('hides other player roles during game', () => {
    const { result } = renderHook(() => useGameTransformers(makeGameState()));
    const other = result.current.players.find(p => p.id === 2);
    expect(other?.role).toBeUndefined();
  });

  it('shows all roles when game is finished', () => {
    const gs = makeGameState({
      status: 'finished',
      players: [
        { seat_id: 1, is_alive: true, is_human: true, name: 'A', role: 'seer' },
        { seat_id: 2, is_alive: true, is_human: false, name: 'B', role: 'werewolf' },
      ],
    });
    const { result } = renderHook(() => useGameTransformers(gs));
    expect(result.current.players[1].role).toBe('werewolf');
  });

  it('uses default name when player name is null', () => {
    const gs = makeGameState({
      players: [
        { seat_id: 1, is_alive: true, is_human: true, name: null },
        { seat_id: 2, is_alive: true, is_human: false, name: null },
      ],
    });
    const { result } = renderHook(() => useGameTransformers(gs));
    // Seat 1 is current user => "You"
    expect(result.current.players[0].name).toBe('You');
    // Seat 2 fallback name
    expect(result.current.players[1].name).toBe('Player 2');
  });

  it('tracks isAlive status', () => {
    const { result } = renderHook(() => useGameTransformers(makeGameState()));
    const dead = result.current.players.find(p => p.id === 3);
    expect(dead?.isAlive).toBe(false);
  });

  // --- playerMap ---
  it('builds playerMap as Map<seat_id, Player>', () => {
    const { result } = renderHook(() => useGameTransformers(makeGameState()));
    expect(result.current.playerMap.size).toBe(3);
    expect(result.current.playerMap.get(2)?.name).toBe('Bob');
  });

  // --- messages ---
  it('transforms messages with sender names', () => {
    const gs = makeGameState({
      message_log: [
        { seat_id: 1, text: 'Hello', type: 'speech', day: 1 },
        { seat_id: 2, text: 'Hi', type: 'speech', day: 1 },
      ],
    });
    const { result } = renderHook(() => useGameTransformers(gs));
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].sender).toBe('You');
    expect(result.current.messages[0].isUser).toBe(true);
    expect(result.current.messages[1].sender).toBe('Bob');
    expect(result.current.messages[1].isUser).toBe(false);
  });

  it('identifies system messages', () => {
    const gs = makeGameState({
      message_log: [
        { seat_id: 0, text: 'Night falls', type: 'system', day: 1 },
      ],
    });
    const { result } = renderHook(() => useGameTransformers(gs));
    expect(result.current.messages[0].isSystem).toBe(true);
    expect(result.current.messages[0].sender).toBe('System');
  });

  it('assigns sequential ids to messages', () => {
    const gs = makeGameState({
      message_log: [
        { seat_id: 1, text: 'a', type: 'speech', day: 1 },
        { seat_id: 2, text: 'b', type: 'speech', day: 1 },
        { seat_id: 3, text: 'c', type: 'speech', day: 1 },
      ],
    });
    const { result } = renderHook(() => useGameTransformers(gs));
    expect(result.current.messages.map(m => m.id)).toEqual([1, 2, 3]);
  });

  it('uses seat fallback for unknown sender', () => {
    const gs = makeGameState({
      message_log: [
        { seat_id: 99, text: 'ghost', type: 'speech', day: 1 },
      ],
    });
    const { result } = renderHook(() => useGameTransformers(gs));
    expect(result.current.messages[0].sender).toBe('Seat 99');
  });
});
