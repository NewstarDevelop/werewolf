/**
 * useGame Hook - Facade pattern composing specialized hooks
 */
import { useState, useCallback } from 'react';
import { Role, isNightPhase, needsHumanAction } from '@/services/api';
import { useGameState } from './useGameState';
import { useGameActions } from './useGameActions';
import { useGameAutomation } from './useGameAutomation';

interface UseGameOptions {
  autoStep?: boolean;
  stepInterval?: number;
  gameId?: string;
  enableWebSocket?: boolean;
}

export function useGame(options: UseGameOptions = {}) {
  const { autoStep = true, stepInterval = 2000, gameId: initialGameId, enableWebSocket = true } = options;

  const [gameId, setGameId] = useState<string | null>(initialGameId || null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepErrorCount, setStepErrorCount] = useState(0);

  // State management hook
  const {
    gameState,
    isLoading: isLoadingState,
    refetch: refetchState,
    error: queryError,
    isError: isQueryError,
    isWebSocketConnected,
  } = useGameState({ gameId, enableWebSocket });

  // Actions management hook
  const {
    stepGameMutation,
    submitActionMutation,
    handleStartGame: baseHandleStartGame,
    handleStep,
    handleAction,
    stepMutateRef,
  } = useGameActions({
    gameId,
    gameState,
    setGameId,
    setStepErrorCount,
    refetchState,
  });

  // Automation hook
  const { isAutoStepPaused } = useGameAutomation({
    gameId,
    gameState,
    autoStep,
    stepInterval,
    stepErrorCount,
    stepMutateRef,
    isStepping: stepGameMutation.isPending,
  });

  // Wrap startGame to manage local state
  const handleStartGame = useCallback(
    async (humanSeat?: number, humanRole?: Role) => {
      setIsStarting(true);
      setError(null);
      try {
        await baseHandleStartGame(humanSeat, humanRole);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsStarting(false);
      }
    },
    [baseHandleStartGame]
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
    (targetId: number) => handleAction('self_destruct', targetId),
    [handleAction]
  );

  const handleSkip = useCallback(() => handleAction('skip'), [handleAction]);

  // Derived state
  const isNight = gameState ? isNightPhase(gameState.phase) : false;
  const needsAction = gameState ? needsHumanAction(gameState) : false;
  const isGameOver = gameState?.status === 'finished';
  const isLoading = isStarting || isLoadingState || stepGameMutation.isPending;
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
    isWebSocketConnected,
    isAutoStepPaused,

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
