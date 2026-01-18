/**
 * Utility functions for environment variable management
 */

const SENSITIVE_KEYWORDS = [
  'KEY',
  'SECRET',
  'PASSWORD',
  'TOKEN',
  'CREDENTIAL',
  'AUTH',
  'PRIVATE',
  'JWT',
  'API_KEY',
  'APIKEY',
];

/**
 * Determine if an environment variable key should be treated as sensitive
 */
export const isSensitiveKey = (key: string): boolean => {
  const upperKey = key.toUpperCase();
  return SENSITIVE_KEYWORDS.some(keyword => upperKey.includes(keyword));
};
