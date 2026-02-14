/**
 * errorHandler Tests
 *
 * Tests error message extraction and API error parsing.
 */
import { describe, it, expect } from 'vitest';
import { getErrorMessage, parseApiError } from '../errorHandler';

// ============================================================================
// getErrorMessage
// ============================================================================

describe('getErrorMessage', () => {
  it('extracts message from Error instance', () => {
    expect(getErrorMessage(new Error('boom'), 'fallback')).toBe('boom');
  });

  it('returns string errors directly', () => {
    expect(getErrorMessage('network error', 'fallback')).toBe('network error');
  });

  it('returns fallback for null', () => {
    expect(getErrorMessage(null, 'fallback')).toBe('fallback');
  });

  it('returns fallback for undefined', () => {
    expect(getErrorMessage(undefined, 'fallback')).toBe('fallback');
  });

  it('returns fallback for number', () => {
    expect(getErrorMessage(42, 'fallback')).toBe('fallback');
  });

  it('returns fallback for object without message', () => {
    expect(getErrorMessage({ code: 500 }, 'fallback')).toBe('fallback');
  });
});

// ============================================================================
// parseApiError
// ============================================================================

describe('parseApiError', () => {
  it('extracts detail from JSON response', async () => {
    const response = new Response(JSON.stringify({ detail: 'Not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
    expect(await parseApiError(response)).toBe('Not found');
  });

  it('extracts message field when detail is absent', async () => {
    const response = new Response(JSON.stringify({ message: 'Bad request' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
    expect(await parseApiError(response)).toBe('Bad request');
  });

  it('stringifies JSON when no detail or message', async () => {
    const response = new Response(JSON.stringify({ code: 500 }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
    expect(await parseApiError(response)).toBe('{"code":500}');
  });

  it('falls back to text for non-JSON response', async () => {
    const response = new Response('<html>Server Error</html>', {
      status: 500,
      statusText: 'Internal Server Error',
    });
    const result = await parseApiError(response);
    expect(result).toContain('Server Error');
  });

  it('falls back to statusText when body is empty', async () => {
    // Create a response whose .json() will throw and .text() returns empty
    const response = new Response('', {
      status: 502,
      statusText: 'Bad Gateway',
    });
    const result = await parseApiError(response);
    expect(result).toBe('Bad Gateway');
  });
});
