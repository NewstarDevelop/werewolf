/**
 * useGameSound Hook
 * Automatically triggers sound effects based on game state changes
 */
import { useEffect, useRef } from 'react';
import { useSound } from '@/contexts/SoundContext';
import { GameState, GamePhase } from '@/types/game';

interface UseGameSoundOptions {
  gameState: GameState | null;
  isEnabled?: boolean;
}

export function useGameSound({ gameState, isEnabled = true }: UseGameSoundOptions) {
  const { play, stop } = useSound();
  const prevGameStateRef = useRef<GameState | null>(null);
  const prevPhaseRef = useRef<GamePhase | null>(null);

  useEffect(() => {
    if (!isEnabled || !gameState) return;

    const prevGameState = prevGameStateRef.current;
    const prevPhase = prevPhaseRef.current;

    // Phase transition sound (Day/Night)
    // Also play on initial load (when prevPhase is null)
    if (prevPhase !== gameState.phase) {
      // Stop previous BGM (only if prevPhase exists)
      if (prevPhase && prevPhase.startsWith('day_')) {
        stop('PHASE_DAY');
      } else if (prevPhase && prevPhase.startsWith('night_')) {
        stop('PHASE_NIGHT');
      }

      // Play new phase BGM
      if (gameState.phase.startsWith('day_')) {
        play('PHASE_DAY');
      } else if (gameState.phase.startsWith('night_')) {
        play('PHASE_NIGHT');
      }
    }

    // Player death sound
    if (prevGameState && prevGameState.players) {
      const prevAlivePlayers = prevGameState.players.filter((p) => p.is_alive);
      const currentAlivePlayers = gameState.players.filter((p) => p.is_alive);

      if (currentAlivePlayers.length < prevAlivePlayers.length) {
        // Someone died
        play('DEATH');
      }
    }

    // Game over sound (Victory/Defeat)
    if (gameState.status === 'finished' && prevGameState?.status !== 'finished') {
      // Stop BGM
      stop('PHASE_DAY');
      stop('PHASE_NIGHT');

      // Play victory/defeat sound based on winner
      // Note: You may need to check if the current player is on the winning team
      if (gameState.winner === 'villager') {
        play('VICTORY');
      } else if (gameState.winner === 'werewolf') {
        play('DEFEAT');
      }
    }

    // Update refs
    prevGameStateRef.current = gameState;
    prevPhaseRef.current = gameState.phase;
  }, [gameState, isEnabled, play, stop]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop('PHASE_DAY');
      stop('PHASE_NIGHT');
      stop('VICTORY');
      stop('DEFEAT');
    };
  }, [stop]);
}
