/**
 * envUtils tests — isSensitiveKey detection
 */
import { describe, it, expect } from 'vitest';
import { isSensitiveKey } from '../envUtils';

describe('isSensitiveKey', () => {
  it.each([
    'OPENAI_API_KEY',
    'JWT_SECRET',
    'DB_PASSWORD',
    'AUTH_TOKEN',
    'PRIVATE_KEY',
    'MY_CREDENTIAL',
    'APIKEY',
  ])('detects "%s" as sensitive', (key) => {
    expect(isSensitiveKey(key)).toBe(true);
  });

  it.each([
    'DATABASE_URL',
    'PORT',
    'NODE_ENV',
    'VITE_APP_NAME',
    'LOG_LEVEL',
  ])('detects "%s" as non-sensitive', (key) => {
    expect(isSensitiveKey(key)).toBe(false);
  });

  it('is case-insensitive', () => {
    expect(isSensitiveKey('my_api_key')).toBe(true);
    expect(isSensitiveKey('Jwt_Secret')).toBe(true);
  });
});
