/**
 * date utility Tests
 *
 * Tests server-side UTC timestamp parsing.
 */
import { describe, it, expect } from 'vitest';
import { parseServerDate } from '../date';

describe('parseServerDate', () => {
  it('returns null for null input', () => {
    expect(parseServerDate(null)).toBeNull();
  });

  it('returns null for undefined input', () => {
    expect(parseServerDate(undefined)).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(parseServerDate('')).toBeNull();
  });

  it('returns null for invalid date string', () => {
    expect(parseServerDate('not-a-date')).toBeNull();
  });

  it('parses naive datetime as UTC', () => {
    const date = parseServerDate('2023-10-27T10:00:00');
    expect(date).not.toBeNull();
    expect(date!.getUTCHours()).toBe(10);
    expect(date!.getUTCFullYear()).toBe(2023);
    expect(date!.getUTCMonth()).toBe(9); // 0-indexed
    expect(date!.getUTCDate()).toBe(27);
  });

  it('parses Z-suffixed datetime correctly', () => {
    const date = parseServerDate('2023-10-27T10:00:00Z');
    expect(date).not.toBeNull();
    expect(date!.getUTCHours()).toBe(10);
  });

  it('parses datetime with timezone offset', () => {
    const date = parseServerDate('2023-10-27T18:00:00+08:00');
    expect(date).not.toBeNull();
    // 18:00 +08:00 = 10:00 UTC
    expect(date!.getUTCHours()).toBe(10);
  });

  it('returns a valid Date object', () => {
    const date = parseServerDate('2023-01-01T00:00:00');
    expect(date).toBeInstanceOf(Date);
    expect(isNaN(date!.getTime())).toBe(false);
  });
});
