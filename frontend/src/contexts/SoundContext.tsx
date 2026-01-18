/**
 * Sound Context - Global audio management
 */
import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { Howl, Howler } from 'howler';
import { SOUND_ASSETS, SoundKey, DEFAULT_SOUND_PREFERENCES } from '@/config/soundConfig';
import { getUserPreferences, updateUserPreferences } from '@/services/preferencesApi';
import { useAuth } from '@/contexts/AuthContext';

interface SoundContextValue {
  /** Master volume (0.0-1.0) */
  masterVolume: number;
  /** Whether sound is muted */
  isMuted: boolean;
  /** Whether sounds are enabled */
  isEnabled: boolean;
  /** Whether audio context is unlocked (browser autoplay policy) */
  isUnlocked: boolean;

  /** Play a sound by key */
  play: (key: SoundKey) => void;
  /** Stop a sound by key */
  stop: (key: SoundKey) => void;
  /** Stop all currently playing sounds */
  stopAll: () => void;
  /** Update master volume */
  setMasterVolume: (volume: number) => void;
  /** Toggle mute */
  setIsMuted: (muted: boolean) => void;
  /** Toggle sound enabled */
  setIsEnabled: (enabled: boolean) => void;
}

const SoundContext = createContext<SoundContextValue | undefined>(undefined);

const STORAGE_KEY = 'sound_preferences';

export function SoundProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [masterVolume, setMasterVolumeState] = useState(DEFAULT_SOUND_PREFERENCES.volume);
  const [isMuted, setIsMutedState] = useState(DEFAULT_SOUND_PREFERENCES.muted);
  const [isEnabled, setIsEnabledState] = useState(DEFAULT_SOUND_PREFERENCES.enabled);
  const [isUnlocked, setIsUnlocked] = useState(false);

  // Store Howl instances
  const soundsRef = useRef<Map<SoundKey, Howl>>(new Map());
  const currentBGMRef = useRef<SoundKey | null>(null);

  // Debounce timer for API sync
  const syncTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load preferences from backend when user logs in
  useEffect(() => {
    if (!user) return;

    // Try to load from backend
    getUserPreferences()
      .then((prefs) => {
        setMasterVolumeState(prefs.sound_effects.volume);
        setIsMutedState(prefs.sound_effects.muted);
        setIsEnabledState(prefs.sound_effects.enabled);
      })
      .catch((error) => {
        console.warn('Failed to load preferences from backend, using localStorage:', error);
        // Fallback to localStorage
        loadFromLocalStorage();
      });
  }, [user]);

  // Load from localStorage (fallback)
  const loadFromLocalStorage = () => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const prefs = JSON.parse(stored);
        if (typeof prefs.volume === 'number') setMasterVolumeState(prefs.volume);
        if (typeof prefs.muted === 'boolean') setIsMutedState(prefs.muted);
        if (typeof prefs.enabled === 'boolean') setIsEnabledState(prefs.enabled);
      } catch (e) {
        console.warn('Failed to parse sound preferences:', e);
      }
    }
  };

  // Save preferences to localStorage whenever they change
  useEffect(() => {
    const prefs = {
      volume: masterVolume,
      muted: isMuted,
      enabled: isEnabled,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));

    // Debounced sync to backend (if user is logged in)
    if (user) {
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
      }

      syncTimerRef.current = setTimeout(() => {
        updateUserPreferences({
          sound_effects: {
            enabled: isEnabled,
            volume: masterVolume,
            muted: isMuted,
          },
        }).catch((error) => {
          console.warn('Failed to sync preferences to backend:', error);
        });
      }, 500); // 500ms debounce
    }
  }, [masterVolume, isMuted, isEnabled, user]);

  // Update Howler global volume
  useEffect(() => {
    const effectiveVolume = isMuted ? 0 : masterVolume;
    Howler.volume(effectiveVolume);
  }, [masterVolume, isMuted]);

  // Unlock audio context on first user interaction
  useEffect(() => {
    const unlockAudio = () => {
      if (isUnlocked) return;

      // Try to unlock by playing a silent sound
      const unlock = new Howl({
        src: ['data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='],
        volume: 0,
        onend: () => {
          setIsUnlocked(true);
          unlock.unload();
        },
      });
      unlock.play();
    };

    // Listen for user interactions
    document.addEventListener('click', unlockAudio, { once: true });
    document.addEventListener('keydown', unlockAudio, { once: true });
    document.addEventListener('touchstart', unlockAudio, { once: true });

    return () => {
      document.removeEventListener('click', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
      document.removeEventListener('touchstart', unlockAudio);
    };
  }, [isUnlocked]);

  // Lazy load sound
  const getOrCreateSound = useCallback((key: SoundKey): Howl | null => {
    if (!isEnabled) return null;

    // Return existing sound
    if (soundsRef.current.has(key)) {
      return soundsRef.current.get(key)!;
    }

    // Create new sound
    const asset = SOUND_ASSETS[key];
    const howl = new Howl({
      src: asset.src,
      loop: asset.loop || false,
      volume: asset.volume || 1.0,
      onloaderror: (id, error) => {
        console.warn(`Failed to load sound: ${key}`, error);
      },
    });

    soundsRef.current.set(key, howl);
    return howl;
  }, [isEnabled]);

  const play = useCallback((key: SoundKey) => {
    if (!isEnabled || isMuted) return;

    const sound = getOrCreateSound(key);
    if (!sound) return;

    const asset = SOUND_ASSETS[key];

    // Handle BGM (stop previous BGM if switching)
    if (asset.category === 'bgm') {
      if (currentBGMRef.current && currentBGMRef.current !== key) {
        const prevBGM = soundsRef.current.get(currentBGMRef.current);
        if (prevBGM) {
          // Fade out previous BGM
          prevBGM.fade(prevBGM.volume(), 0, 1000);
          setTimeout(() => prevBGM.stop(), 1000);
        }
      }
      currentBGMRef.current = key;

      // Fade in new BGM
      sound.volume(0);
      sound.play();
      sound.fade(0, asset.volume || 1.0, 2000);
    } else {
      // Play SFX normally
      sound.play();
    }
  }, [isEnabled, isMuted, getOrCreateSound]);

  const stop = useCallback((key: SoundKey) => {
    const sound = soundsRef.current.get(key);
    if (sound) {
      sound.stop();
      if (currentBGMRef.current === key) {
        currentBGMRef.current = null;
      }
    }
  }, []);

  const stopAll = useCallback(() => {
    soundsRef.current.forEach((sound) => sound.stop());
    currentBGMRef.current = null;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      soundsRef.current.forEach((sound) => sound.unload());
      soundsRef.current.clear();
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
      }
    };
  }, []);

  // Wrapper functions to update state
  const setMasterVolume = useCallback((volume: number) => {
    setMasterVolumeState(volume);
  }, []);

  const setIsMuted = useCallback((muted: boolean) => {
    setIsMutedState(muted);
  }, []);

  const setIsEnabled = useCallback((enabled: boolean) => {
    setIsEnabledState(enabled);
  }, []);

  const value: SoundContextValue = {
    masterVolume,
    isMuted,
    isEnabled,
    isUnlocked,
    play,
    stop,
    stopAll,
    setMasterVolume,
    setIsMuted,
    setIsEnabled,
  };

  return <SoundContext.Provider value={value}>{children}</SoundContext.Provider>;
}

export function useSound() {
  const context = useContext(SoundContext);
  if (!context) {
    throw new Error('useSound must be used within SoundProvider');
  }
  return context;
}
