/**
 * useGame Hook - Manages game state and API interactions
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  startGame,
  getGameState,
  stepGame,
  submitAction,
  GameState,
  GameStartResponse,
  StepResponse,
  ActionType,
  Role,
  isNightPhase,
  needsHumanAction,
} from '@/services/api';
import { saveToken } from '@/utils/token';
import { useGameWebSocket } from './useGameWebSocket';

interface UseGameOptions {
  autoStep?: boolean;
  stepInterval?: number;
  gameId?: string; // Optional game ID to load existing game
  enableWebSocket?: boolean; // Enable WebSocket for real-time updates
}

export function useGame(options: UseGameOptions = {}) {
  const { autoStep = true, stepInterval = 2000, gameId: initialGameId, enableWebSocket = true } = options;

  const [gameId, setGameId] = useState<string | null>(initialGameId || null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // H-H3 FIX: Track consecutive step errors to prevent infinite loop hammering
  const [stepErrorCount, setStepErrorCount] = useState(0);
  // Phase 2.2: Track if WebSocket has delivered first update
  const [wsReceivedFirstUpdate, setWsReceivedFirstUpdate] = useState(false);
  const queryClient = useQueryClient();
  // M4 FIX: Use ReturnType<typeof setTimeout> for cross-platform compatibility
  const stepTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // H-H4 FIX + M5 FIX: Store stepMutate with explicit type signature
  const stepMutateRef = useRef<((variables?: void) => void) | null>(null);

  // WebSocket connection for real-time updates
  const { isConnected: isWebSocketConnected, connectionError: wsError } = useGameWebSocket({
    gameId,
    enabled: enableWebSocket && !!gameId,
    onFirstUpdate: () => setWsReceivedFirstUpdate(true),
    onError: (err) => {
      console.warn('[WebSocket] Connection error, falling back to polling:', err.message);
      setWsReceivedFirstUpdate(false);  // Reset on error
    },
  });

  // Query for game state
  const {
    data: gameState,
    isLoading: isLoadingState,
    refetch: refetchState,
    error: queryError,
    isError: isQueryError,
  } = useQuery({
    queryKey: ['gameState', gameId],
    queryFn: () => (gameId ? getGameState(gameId) : null),
    enabled: !!gameId,
    refetchInterval: (query) => {
      const state = query.state.data as GameState | null;
      // Stop polling when game is finished
      if (state?.status === 'finished') return false;

      // Phase 2.2: Only slow down polling when WebSocket is healthy
      // Require: WS enabled + connected + no error + first update received
      const shouldSlowPoll =
        enableWebSocket &&
        isWebSocketConnected &&
        !wsError &&
        wsReceivedFirstUpdate;
      return shouldSlowPoll ? 10000 : 2000;
    },
    refetchIntervalInBackground: false,
    staleTime: 0,
  });

  // Mutation for starting a new game
  const startGameMutation = useMutation({
    mutationFn: startGame,
    onSuccess: (data: GameStartResponse) => {
      // Save JWT token for authentication
      if (data.token) {
        saveToken(data.token);
      }
      setGameId(data.game_id);
      setError(null);
      // HIGH-1 FIX: Reset error count to prevent cross-game pollution
      setStepErrorCount(0);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Mutation for stepping the game
  const stepGameMutation = useMutation({
    mutationFn: () => (gameId ? stepGame(gameId) : Promise.reject(new Error('No game'))),
    onSuccess: async () => {
      // H4 FIX: Only refetch state, let the main useEffect handle auto-stepping
      // This prevents auto-stepping when the new state requires human action
      // M2 FIX: Track refetch failures to prevent silent state desync
      try {
        await refetchState();
        // H-H3 FIX: Reset error count on successful step
        setStepErrorCount(0);
      } catch (err) {
        console.error('Refetch error:', err);
        // M2 FIX: Count refetch failures as step errors
        setStepErrorCount(prev => prev + 1);
      }
    },
    onError: (err: Error) => {
      // Ignore AbortError - this happens when request is cancelled due to component re-render
      // (e.g., WebSocket update triggers state change while step request is in flight)
      if (err.name === 'AbortError' || err.message?.includes('aborted')) {
        return;
      }
      console.error('Step error:', err);
      // H-H3 FIX: Increment error count to prevent infinite retry loop
      setStepErrorCount(prev => prev + 1);
    },
  });

  // H-H4 FIX: Keep stepMutate ref updated for stable scheduleNextStep callback
  stepMutateRef.current = stepGameMutation.mutate;

  // Mutation for submitting actions
  const submitActionMutation = useMutation({
    mutationFn: ({
      actionType,
      targetId,
      content,
    }: {
      actionType: ActionType;
      targetId?: number | null;
      content?: string | null;
    }) => {
      if (!gameId || !gameState) return Promise.reject(new Error('No game'));
      return submitAction(gameId, {
        seat_id: gameState.my_seat,
        action_type: actionType,
        target_id: targetId,
        content: content,
      });
    },
    onSuccess: async () => {
      // H4 FIX: Only invalidate, let the main useEffect handle auto-stepping
      // This prevents auto-stepping when the new state requires human action
      // (e.g., witch after using antidote should still decide on poison)
      // H-H2 FIX: Don't call both invalidate and refetch - invalidateQueries already
      // triggers refetch for active queries in React Query v5, causing double requests
      await queryClient.invalidateQueries({ queryKey: ['gameState', gameId] });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Schedule next step with delay
  // H-H4 FIX: Use stepMutateRef for stable callback (doesn't re-create on mutation object change)
  const scheduleNextStep = useCallback(() => {
    if (stepTimeoutRef.current) {
      clearTimeout(stepTimeoutRef.current);
    }
    stepTimeoutRef.current = setTimeout(() => {
      // M3 FIX: Validate conditions before executing delayed step
      const currentGameState = queryClient.getQueryData<GameState>(['gameState', gameId]);
      if (!currentGameState) return;

      const stillNeedsStep = !needsHumanAction(currentGameState) &&
                              currentGameState.status !== 'finished';

      if (stillNeedsStep) {
        stepMutateRef.current?.();
      }
    }, stepInterval);
  }, [stepInterval, queryClient, gameId]);

  // Start a new game
  const handleStartGame = useCallback(
    async (humanSeat?: number, humanRole?: Role) => {
      setIsStarting(true);
      setError(null);
      try {
        await startGameMutation.mutateAsync({
          human_seat: humanSeat,
          human_role: humanRole,
        });
      } finally {
        setIsStarting(false);
      }
    },
    [startGameMutation]
  );

  // Manually trigger a step
  const handleStep = useCallback(() => {
    if (gameId) {
      stepGameMutation.mutate();
    }
  }, [gameId, stepGameMutation]);

  // Submit player action
  const handleAction = useCallback(
    async (actionType: ActionType, targetId?: number | null, content?: string | null) => {
      await submitActionMutation.mutateAsync({ actionType, targetId, content });
    },
    [submitActionMutation]
  );

  // Convenience methods for specific actions
  const handleSpeak = useCallback(
    (content: string) => handleAction('speak', null, content),
    [handleAction]
  );

  const handleVote = useCallback(
    (targetId: number | null) => handleAction('vote', targetId),
    [handleAction]
  );

  const handleKill = useCallback(
    (targetId: number) => handleAction('kill', targetId),
    [handleAction]
  );

  const handleVerify = useCallback(
    (targetId: number) => handleAction('verify', targetId),
    [handleAction]
  );

  const handleSave = useCallback(() => handleAction('save'), [handleAction]);

  const handlePoison = useCallback(
    (targetId: number) => handleAction('poison', targetId),
    [handleAction]
  );

  const handleShoot = useCallback(
    (targetId: number | null) => handleAction('shoot', targetId),
    [handleAction]
  );

  const handleProtect = useCallback(
    (targetId: number | null) => handleAction('protect', targetId),
    [handleAction]
  );

  const handleSelfDestruct = useCallback(
    () => handleAction('self_destruct'),
    [handleAction]
  );

  const handleSkip = useCallback(() => handleAction('skip'), [handleAction]);

  // Auto-step when game starts or state changes
  useEffect(() => {
    if (gameId && gameState && autoStep) {
      const needsAction = needsHumanAction(gameState);
      const isGameOver = gameState.status === 'finished';
      // H-H3 FIX: Stop auto-stepping after 3 consecutive errors to prevent hammering backend
      const MAX_STEP_ERRORS = 3;
      const tooManyErrors = stepErrorCount >= MAX_STEP_ERRORS;

      if (!needsAction && !isGameOver && !stepGameMutation.isPending && !tooManyErrors) {
        scheduleNextStep();
      } else if (tooManyErrors) {
        console.warn(`Auto-stepping disabled after ${stepErrorCount} consecutive errors. Manual step required.`);
      }
    }

    return () => {
      if (stepTimeoutRef.current) {
        clearTimeout(stepTimeoutRef.current);
      }
    };
  }, [gameId, gameState, autoStep, scheduleNextStep, stepGameMutation.isPending, stepErrorCount]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (stepTimeoutRef.current) {
        clearTimeout(stepTimeoutRef.current);
      }
    };
  }, []);

  // Derived state
  const isNight = gameState ? isNightPhase(gameState.phase) : false;
  const needsAction = gameState ? needsHumanAction(gameState) : false;
  const isGameOver = gameState?.status === 'finished';
  const isLoading = isStarting || isLoadingState || stepGameMutation.isPending;

  // Combine local error and query error for unified error handling
  const combinedError = error || (queryError instanceof Error ? queryError.message : null);

  return {
    // State
    gameId,
    gameState,
    isLoading,
    isStarting,
    error: combinedError,
    queryError,
    isQueryError,
    isNight,
    needsAction,
    isGameOver,
    isWebSocketConnected,  // WebSocket connection status

    // Actions
    startGame: handleStartGame,
    step: handleStep,
    speak: handleSpeak,
    vote: handleVote,
    kill: handleKill,
    verify: handleVerify,
    save: handleSave,
    poison: handlePoison,
    shoot: handleShoot,
    protect: handleProtect,
    selfDestruct: handleSelfDestruct,
    skip: handleSkip,
    submitAction: handleAction,

    // Mutations state
    isSubmitting: submitActionMutation.isPending,
    isStepping: stepGameMutation.isPending,
  };
}

export default useGame;
