/**
 * Error handling utilities
 */

/**
 * Extract error message from unknown error type
 * Handles Error instances, string errors, and fallback messages
 */
export function getErrorMessage(error: unknown, fallbackMessage: string): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  return fallbackMessage;
}

/**
 * Log error to console in production (can be extended for error tracking services)
 */
export function logError(context: string, error: unknown): void {
  if (import.meta.env.PROD) {
    console.error(`[${context}]`, error);
  }
}
