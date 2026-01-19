/**
 * useGameSound Hook
 * Automatically triggers sound effects based on game state changes
 */
import { useEffect, useRef } from 'react';
import { useSound } from '@/contexts/SoundContext';
import { GameState, Phase } from '@/types/game';

interface UseGameSoundOptions {
  gameState: GameState | null;
  isEnabled?: boolean;
}

export function useGameSound({ gameState, isEnabled = true }: UseGameSoundOptions) {
  const { play, stop } = useSound();
  const prevGameStateRef = useRef<GameState | null>(null);
  const prevPhaseRef = useRef<Phase | null>(null);

  useEffect(() => {
    if (!isEnabled || !gameState) return;

    const prevGameState = prevGameStateRef.current;
    const prevPhase = prevPhaseRef.current;

    // Phase transition sound (Day/Night)
    // Also play on initial load (when prevPhase is null)
    if (prevPhase !== gameState.phase) {
      // Stop previous BGM (only if prevPhase exists)
      if (prevPhase === 'DAY') {
        stop('PHASE_DAY');
      } else if (prevPhase === 'NIGHT') {
        stop('PHASE_NIGHT');
      }

      // Play new phase BGM
      if (gameState.phase === 'DAY') {
        play('PHASE_DAY');
      } else if (gameState.phase === 'NIGHT') {
        play('PHASE_NIGHT');
      }
    }

    // Player death sound
    if (prevGameState && prevGameState.players) {
      const prevAlivePlayers = prevGameState.players.filter((p) => p.isAlive);
      const currentAlivePlayers = gameState.players.filter((p) => p.isAlive);

      if (currentAlivePlayers.length < prevAlivePlayers.length) {
        // Someone died
        play('DEATH');
      }
    }

    // Game over sound (Victory/Defeat)
    if (gameState.is_game_over && !prevGameState?.is_game_over) {
      // Stop BGM
      stop('PHASE_DAY');
      stop('PHASE_NIGHT');

      // Play victory/defeat sound based on winner
      // Note: You may need to check if the current player is on the winning team
      if (gameState.winner === 'VILLAGER') {
        play('VICTORY');
      } else if (gameState.winner === 'WEREWOLF') {
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
