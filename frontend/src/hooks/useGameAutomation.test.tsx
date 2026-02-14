/**
 * useGameAutomation Hook Tests
 *
 * Tests auto-step scheduling, pause logic, and cleanup.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import { useGameAutomation } from './useGameAutomation';
import type { GameState } from '@/types/api';

// Mock needsHumanAction
const mockNeedsHumanAction = vi.fn((_gs: unknown) => false);
vi.mock('@/services/api', () => ({
  needsHumanAction: (gs: unknown) => mockNeedsHumanAction(gs),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function makeState(overrides: Partial<GameState> = {}): GameState {
  return {
    game_id: 'g1',
    status: 'playing',
    state_version: 1,
    day: 1,
    phase: 'night_werewolf',
    my_seat: 1,
    my_role: 'villager',
    players: [],
    message_log: [],
    wolf_teammates: [],
    verified_results: {},
    pending_action: null,
    ...overrides,
  };
}

describe('useGameAutomation', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockNeedsHumanAction.mockReturnValue(false);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('returns isAutoStepPaused = false when error count < 3', () => {
    const { result } = renderHook(
      () =>
        useGameAutomation({
          gameId: 'g1',
          gameState: makeState(),
          autoStep: true,
          stepInterval: 1000,
          stepErrorCount: 0,
          stepMutateRef: { current: null },
          isStepping: false,
        }),
      { wrapper: createWrapper() },
    );
    expect(result.current.isAutoStepPaused).toBe(false);
  });

  it('returns isAutoStepPaused = true when error count >= 3', () => {
    const { result } = renderHook(
      () =>
        useGameAutomation({
          gameId: 'g1',
          gameState: makeState(),
          autoStep: true,
          stepInterval: 1000,
          stepErrorCount: 3,
          stepMutateRef: { current: null },
          isStepping: false,
        }),
      { wrapper: createWrapper() },
    );
    expect(result.current.isAutoStepPaused).toBe(true);
  });

  it('does not auto-step when autoStep is false', () => {
    const mutateFn = vi.fn();
    renderHook(
      () =>
        useGameAutomation({
          gameId: 'g1',
          gameState: makeState(),
          autoStep: false,
          stepInterval: 500,
          stepErrorCount: 0,
          stepMutateRef: { current: mutateFn },
          isStepping: false,
        }),
      { wrapper: createWrapper() },
    );
    vi.advanceTimersByTime(1000);
    expect(mutateFn).not.toHaveBeenCalled();
  });

  it('does not auto-step when game is finished', () => {
    const mutateFn = vi.fn();
    renderHook(
      () =>
        useGameAutomation({
          gameId: 'g1',
          gameState: makeState({ status: 'finished' }),
          autoStep: true,
          stepInterval: 500,
          stepErrorCount: 0,
          stepMutateRef: { current: mutateFn },
          isStepping: false,
        }),
      { wrapper: createWrapper() },
    );
    vi.advanceTimersByTime(1000);
    expect(mutateFn).not.toHaveBeenCalled();
  });

  it('does not auto-step when human action is needed', () => {
    mockNeedsHumanAction.mockReturnValue(true);
    const mutateFn = vi.fn();
    renderHook(
      () =>
        useGameAutomation({
          gameId: 'g1',
          gameState: makeState(),
          autoStep: true,
          stepInterval: 500,
          stepErrorCount: 0,
          stepMutateRef: { current: mutateFn },
          isStepping: false,
        }),
      { wrapper: createWrapper() },
    );
    vi.advanceTimersByTime(1000);
    expect(mutateFn).not.toHaveBeenCalled();
  });

  it('does not auto-step when already stepping', () => {
    const mutateFn = vi.fn();
    renderHook(
      () =>
        useGameAutomation({
          gameId: 'g1',
          gameState: makeState(),
          autoStep: true,
          stepInterval: 500,
          stepErrorCount: 0,
          stepMutateRef: { current: mutateFn },
          isStepping: true,
        }),
      { wrapper: createWrapper() },
    );
    vi.advanceTimersByTime(1000);
    expect(mutateFn).not.toHaveBeenCalled();
  });

  it('does not auto-step when paused due to errors', () => {
    const mutateFn = vi.fn();
    renderHook(
      () =>
        useGameAutomation({
          gameId: 'g1',
          gameState: makeState(),
          autoStep: true,
          stepInterval: 500,
          stepErrorCount: 5,
          stepMutateRef: { current: mutateFn },
          isStepping: false,
        }),
      { wrapper: createWrapper() },
    );
    vi.advanceTimersByTime(1000);
    expect(mutateFn).not.toHaveBeenCalled();
  });

  it('does not auto-step when gameId is null', () => {
    const mutateFn = vi.fn();
    renderHook(
      () =>
        useGameAutomation({
          gameId: null,
          gameState: makeState(),
          autoStep: true,
          stepInterval: 500,
          stepErrorCount: 0,
          stepMutateRef: { current: mutateFn },
          isStepping: false,
        }),
      { wrapper: createWrapper() },
    );
    vi.advanceTimersByTime(1000);
    expect(mutateFn).not.toHaveBeenCalled();
  });
});
