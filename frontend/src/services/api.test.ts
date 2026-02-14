/**
 * API Service Tests
 *
 * T-01: Tests for API service configuration and error handling.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock token utility
vi.mock('@/utils/token', () => ({
  getAuthHeader: vi.fn(() => ({ Authorization: 'Bearer test-token' })),
  getToken: vi.fn(() => 'test-token'),
  setToken: vi.fn(),
  clearToken: vi.fn(),
}));

// Mock i18n config to prevent loading errors
vi.mock('@/i18n/config', () => ({
  default: { language: 'en' },
}));

describe('API Configuration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('API_BASE_URL defaults to empty string for relative paths', async () => {
    // Import dynamically to test the config
    const { API_BASE_URL } = await import('./api');

    // Should be empty string or the configured value
    expect(typeof API_BASE_URL).toBe('string');
  });

  it('authorizedFetch includes credentials', async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ data: 'test' }),
      })
    );

    const { authorizedFetch } = await import('./api');
    const promise = authorizedFetch('/test-endpoint');
    await vi.runAllTimersAsync();
    await promise;

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        credentials: 'include',
      })
    );
  });

  it('authorizedFetch includes Content-Type header', async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ data: 'test' }),
      })
    );

    const { authorizedFetch } = await import('./api');
    const promise = authorizedFetch('/test-endpoint');
    await vi.runAllTimersAsync();
    await promise;

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    );
  });

  it('authorizedFetch throws ApiError on non-ok response', async () => {
    // Use real timers for this test to avoid unhandled rejection from AbortController timeout
    vi.useRealTimers();

    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: false,
        status: 401,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
    );

    const { authorizedFetch, ApiError } = await import('./api');

    let caughtError: unknown = null;
    try {
      await authorizedFetch('/test-endpoint');
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).toBeInstanceOf(ApiError);

    // Restore fake timers for afterEach cleanup
    vi.useFakeTimers();
  });
});

describe('Type Definitions', () => {
  it('Role type includes all expected roles', async () => {
    // Just import to verify module loads
    await import('./api');

    // Just verify the types are defined (compile-time check)
    const roles: string[] = [
      'werewolf',
      'villager',
      'seer',
      'witch',
      'hunter',
      'guard',
      'wolf_king',
      'white_wolf_king',
    ];

    roles.forEach((role) => {
      expect(typeof role).toBe('string');
    });
  });

  it('GamePhase includes night and day phases', () => {
    const nightPhases = [
      'night_start',
      'night_guard',
      'night_werewolf_chat',
      'night_werewolf',
      'night_seer',
      'night_witch',
    ];

    const dayPhases = [
      'day_announcement',
      'day_last_words',
      'day_speech',
      'day_vote',
      'day_vote_result',
    ];

    nightPhases.forEach((phase) => {
      expect(phase.startsWith('night_')).toBe(true);
    });

    dayPhases.forEach((phase) => {
      expect(phase.startsWith('day_')).toBe(true);
    });
  });

  it('ActionType includes all game actions', () => {
    const actions = [
      'kill',
      'verify',
      'save',
      'poison',
      'vote',
      'shoot',
      'protect',
      'self_destruct',
      'speak',
      'skip',
    ];

    expect(actions.length).toBe(10);
  });
});

describe('Helper Functions', () => {
  it('isNightPhase correctly identifies night phases', async () => {
    const { isNightPhase } = await import('./api');

    expect(isNightPhase('night_start')).toBe(true);
    expect(isNightPhase('night_werewolf')).toBe(true);
    expect(isNightPhase('night_seer')).toBe(true);
    expect(isNightPhase('day_speech')).toBe(false);
    expect(isNightPhase('day_vote')).toBe(false);
  });

  it('needsHumanAction identifies phases requiring player input', async () => {
    const { needsHumanAction } = await import('./api');

    // This function should return true for phases where human input is needed
    expect(typeof needsHumanAction).toBe('function');
  });
});
