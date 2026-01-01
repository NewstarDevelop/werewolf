import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { saveToken, getToken, clearToken, getAuthHeader } from '../token';

describe('Token Management', () => {
  beforeEach(() => {
    // Clear session storage before each test
    sessionStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should save and retrieve token', () => {
    const token = 'test-token-123';
    saveToken(token);
    expect(getToken()).toBe(token);
  });

  it('should return null if token is not set', () => {
    expect(getToken()).toBeNull();
  });

  it('should clear token', () => {
    saveToken('test-token');
    clearToken();
    expect(getToken()).toBeNull();
  });

  it('should generate correct auth header', () => {
    saveToken('auth-token');
    const header = getAuthHeader();
    expect(header).toEqual({ 'Authorization': 'Bearer auth-token' });
  });

  it('should return empty header when no token', () => {
    const header = getAuthHeader();
    expect(header).toEqual({});
  });

  it('should expire token after default duration', () => {
    const token = 'expiring-token';
    saveToken(token);

    // Fast forward time by 24 hours + 1 minute
    const OneDayAndBit = 24 * 60 * 60 * 1000 + 60000;
    vi.setSystemTime(Date.now() + OneDayAndBit);

    expect(getToken()).toBeNull();
  });

  it('should not save empty token', () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    saveToken('');
    expect(getToken()).toBeNull();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
