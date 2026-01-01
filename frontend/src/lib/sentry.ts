import * as Sentry from "@sentry/react";

// H2/H3 FIX: Optimized Sentry configuration for privacy and cost control
export function initSentry() {
  if (import.meta.env.VITE_SENTRY_DSN) {
    const isProd = import.meta.env.PROD;

    // C-H3 FIX: Parse float with NaN validation and correct type fallback
    const tracesSampleRate = (() => {
      const value = parseFloat(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || '');
      if (Number.isFinite(value) && value >= 0 && value <= 1) {
        return value;
      }
      return isProd ? 0.1 : 1.0; // Number fallback, not string
    })();

    // C-H2 FIX + M7 FIX: Robust boolean parsing for VITE_SENTRY_ENABLE_REPLAY
    // Environment variables are strings, so "false" is truthy - must parse explicitly
    // Support multiple formats: 'true', 'TRUE', '1', true
    const enableReplay = (() => {
      const val = import.meta.env.VITE_SENTRY_ENABLE_REPLAY;
      if (typeof val === 'boolean') return val;
      if (typeof val === 'string') {
        return val.toLowerCase() === 'true' || val === '1';
      }
      return false;
    })();

    // H-H1 FIX + M6 FIX: Environment-controlled replay sample rates with proper logic
    // IMPORTANT: Replay behavior varies by environment:
    // - DEVELOPMENT: Replay always enabled (for debugging), sample rates apply
    // - PRODUCTION: Replay disabled unless VITE_SENTRY_ENABLE_REPLAY=true
    const replaySampleRates = (() => {
      // Production with replay disabled: zero out sample rates
      if (isProd && !enableReplay) {
        return { session: 0.0, onError: 0.0 };
      }

      // Development (always enabled) or production with enableReplay=true
      const sessionRate = parseFloat(import.meta.env.VITE_SENTRY_REPLAYS_SESSION_SAMPLE_RATE || '');
      const errorRate = parseFloat(import.meta.env.VITE_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE || '');

      return {
        session: Number.isFinite(sessionRate) && sessionRate >= 0 && sessionRate <= 1
          ? sessionRate
          : 0.1, // Default: 10% session sampling
        onError: Number.isFinite(errorRate) && errorRate >= 0 && errorRate <= 1
          ? errorRate
          : 1.0, // Default: 100% error sampling
      };
    })();

    Sentry.init({
      dsn: import.meta.env.VITE_SENTRY_DSN,
      environment: import.meta.env.VITE_SENTRY_ENV || 'development',
      integrations: [
        Sentry.browserTracingIntegration(),
        // H2 FIX: Only enable replay in development or when explicitly enabled
        // In production, disable by default for privacy and cost
        ...(isProd && !enableReplay ? [] : [
          Sentry.replayIntegration({
            maskAllText: true, // Mask all text for privacy
            blockAllMedia: true, // Block images/videos for privacy
          })
        ]),
      ],
      // H3 FIX: Environment-controlled performance monitoring sample rate
      tracesSampleRate,
      // H-H1 FIX: Use computed replay sample rates (consistent with enableReplay)
      replaysSessionSampleRate: replaySampleRates.session,
      replaysOnErrorSampleRate: replaySampleRates.onError,
    });
  }
}

// M9 FIX: Better type safety for context parameter
export function captureError(error: Error, context?: Record<string, unknown>) {
  console.error(error);
  Sentry.captureException(error, { extra: context });
}
