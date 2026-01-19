/**
 * Sound Assets Configuration
 * Defines all audio resources used in the application
 */

export type SoundCategory = 'sfx' | 'bgm';

export interface SoundAsset {
  /** Array of file paths (supports format fallback: ['path.wav', 'path.mp3']) */
  src: string[];
  /** Sound category for volume control */
  category: SoundCategory;
  /** Whether to loop the audio */
  loop?: boolean;
  /** Base volume modifier (0.0-1.0) */
  volume?: number;
}

export type SoundKey = keyof typeof SOUND_ASSETS;

/**
 * Sound Assets Registry
 * IMPORTANT: Files must be placed in frontend/public/sounds/
 * Note: WAV files are listed first as they are the available format
 */
export const SOUND_ASSETS = {
  // UI Interaction Sounds
  CLICK: {
    src: ['/sounds/ui_click.wav', '/sounds/ui_click.mp3'],
    category: 'sfx',
    volume: 0.6,
  },
  HOVER: {
    src: ['/sounds/ui_hover.wav', '/sounds/ui_hover.mp3'],
    category: 'sfx',
    volume: 0.3,
  },
  NOTIFICATION: {
    src: ['/sounds/notification.wav', '/sounds/notification.mp3'],
    category: 'sfx',
    volume: 0.7,
  },

  // Game Phase Transitions
  PHASE_DAY: {
    src: ['/sounds/day_start.wav', '/sounds/day_start.mp3'],
    category: 'bgm',
    loop: true,
    volume: 0.5,
  },
  PHASE_NIGHT: {
    src: ['/sounds/night_start.wav', '/sounds/night_start.mp3'],
    category: 'bgm',
    loop: true,
    volume: 0.5,
  },

  // Game Events
  VOTE: {
    src: ['/sounds/vote_cast.wav', '/sounds/vote_cast.mp3'],
    category: 'sfx',
    volume: 0.7,
  },
  DEATH: {
    src: ['/sounds/player_death.wav', '/sounds/player_death.mp3'],
    category: 'sfx',
    volume: 0.8,
  },
  VICTORY: {
    src: ['/sounds/victory.wav', '/sounds/victory.mp3'],
    category: 'bgm',
    volume: 0.7,
  },
  DEFEAT: {
    src: ['/sounds/defeat.wav', '/sounds/defeat.mp3'],
    category: 'bgm',
    volume: 0.7,
  },
} as const satisfies Record<string, SoundAsset>;

/**
 * Default sound preferences
 */
export const DEFAULT_SOUND_PREFERENCES = {
  enabled: true,
  volume: 1.0,
  muted: false,
} as const;
