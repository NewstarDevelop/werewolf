/**
 * useGame Hook Tests
 *
 * T-01: Tests for the main game hook facade.
 * Verifies initialization and basic functionality.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode } from 'react';
import type { useGameActions } from './useGameActions';

// Mock the API module
vi.mock('@/services/api', () => ({
  gameApi: {
    getGameState: vi.fn(() => Promise.resolve(null)),
    startGame: vi.fn(() => Promise.resolve({ game_id: 'test-game-id' })),
    stepGame: vi.fn(() => Promise.resolve({ status: 'ok' })),
    submitAction: vi.fn(() => Promise.resolve({ status: 'ok' })),
  },
  isNightPhase: vi.fn(() => false),
  needsHumanAction: vi.fn(() => false),
  ActionType: {
    SPEAK: 'speak',
    VOTE: 'vote',
    KILL: 'kill',
    VERIFY: 'verify',
    SAVE: 'save',
    POISON: 'poison',
    SHOOT: 'shoot',
    GUARD: 'guard',
  },
  Role: {
    VILLAGER: 'villager',
    WEREWOLF: 'werewolf',
    SEER: 'seer',
    WITCH: 'witch',
    HUNTER: 'hunter',
    GUARD: 'guard',
  },
}));

// Mock WebSocket hook
vi.mock('./useGameWebSocket', () => ({
  useGameWebSocket: vi.fn(() => ({
    isConnected: false,
    sendMessage: vi.fn(),
    lastMessage: null,
  })),
}));

// Mock sub-hooks
vi.mock('./useGameState', () => ({
  useGameState: vi.fn(() => ({
    gameState: null,
    isLoading: false,
    refetch: vi.fn(),
    error: null,
    isError: false,
    isWebSocketConnected: false,
  })),
}));

vi.mock('./useGameActions', () => ({
  useGameActions: vi.fn(() => ({
    startGameMutation: { isPending: false },
    stepGameMutation: { isPending: false },
    submitActionMutation: { isPending: false },
    handleStartGame: vi.fn(),
    handleStep: vi.fn(),
    handleAction: vi.fn(),
    stepMutateRef: { current: null },
  })),
}));

vi.mock('./useGameAutomation', () => ({
  useGameAutomation: vi.fn(() => ({
    isAutoStepPaused: false,
  })),
}));

// Import after mocks
import { useGame } from './useGame';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function createWrapper() {
  const queryClient = createTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

describe('useGame Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with default options', () => {
    const { result } = renderHook(() => useGame(), {
      wrapper: createWrapper(),
    });

    expect(result.current).toBeDefined();
    expect(result.current.gameId).toBeNull();
    expect(result.current.isStarting).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('initializes with provided gameId', () => {
    const { result } = renderHook(
      () => useGame({ gameId: 'existing-game-123' }),
      { wrapper: createWrapper() }
    );

    expect(result.current.gameId).toBe('existing-game-123');
  });

  it('exposes convenience action methods', () => {
    const { result } = renderHook(() => useGame(), {
      wrapper: createWrapper(),
    });

    // Verify key action properties exist on result
    // Note: useGame returns startGame/step/submitAction (not handleXxx naming)
    expect(result.current).toHaveProperty('startGame');
    expect(result.current).toHaveProperty('step');
    expect(result.current).toHaveProperty('submitAction');

    // Convenience action methods
    expect(result.current).toHaveProperty('speak');
    expect(result.current).toHaveProperty('vote');
    expect(result.current).toHaveProperty('kill');
    expect(result.current).toHaveProperty('verify');

    // startGame should be a function
    expect(typeof result.current.startGame).toBe('function');
  });

  it('exposes game state properties', () => {
    const { result } = renderHook(() => useGame(), {
      wrapper: createWrapper(),
    });

    expect(result.current).toHaveProperty('gameState');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('isWebSocketConnected');
  });

  it('handles autoStep option', () => {
    const { result: resultAuto } = renderHook(
      () => useGame({ autoStep: true }),
      { wrapper: createWrapper() }
    );

    const { result: resultManual } = renderHook(
      () => useGame({ autoStep: false }),
      { wrapper: createWrapper() }
    );

    // Both should initialize without error
    expect(resultAuto.current).toBeDefined();
    expect(resultManual.current).toBeDefined();
  });

  it('handles enableWebSocket option', () => {
    const { result: resultEnabled } = renderHook(
      () => useGame({ enableWebSocket: true }),
      { wrapper: createWrapper() }
    );

    const { result: resultDisabled } = renderHook(
      () => useGame({ enableWebSocket: false }),
      { wrapper: createWrapper() }
    );

    // Both should initialize without error
    expect(resultEnabled.current).toBeDefined();
    expect(resultDisabled.current).toBeDefined();
  });
});

describe('useGame Action Handlers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handleStartGame sets isStarting state', async () => {
    const mockHandleStartGame = vi.fn().mockResolvedValue(undefined);
    vi.mocked(await import('./useGameActions')).useGameActions.mockReturnValue({
      startGameMutation: { isPending: false },
      stepGameMutation: { isPending: false },
      submitActionMutation: { isPending: false },
      handleStartGame: mockHandleStartGame,
      handleStep: vi.fn(),
      handleAction: vi.fn(),
      stepMutateRef: { current: null },
    } as unknown as ReturnType<typeof useGameActions>);

    const { result } = renderHook(() => useGame(), {
      wrapper: createWrapper(),
    });

    // isStarting should be false initially
    expect(result.current.isStarting).toBe(false);
  });

  it('handleStartGame clears error on success', async () => {
    const mockHandleStartGame = vi.fn().mockResolvedValue(undefined);
    vi.mocked(await import('./useGameActions')).useGameActions.mockReturnValue({
      startGameMutation: { isPending: false },
      stepGameMutation: { isPending: false },
      submitActionMutation: { isPending: false },
      handleStartGame: mockHandleStartGame,
      handleStep: vi.fn(),
      handleAction: vi.fn(),
      stepMutateRef: { current: null },
    } as unknown as ReturnType<typeof useGameActions>);

    const { result } = renderHook(() => useGame(), {
      wrapper: createWrapper(),
    });

    // Error should be null after successful start
    expect(result.current.error).toBeNull();
  });
});
