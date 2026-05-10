import type { ServerEnvelope } from "../types/ws";

export type ConnectionPhase = "idle" | "connecting" | "open" | "closed" | "error";
export const RECONNECT_DELAY_MS = 1000;
export const GAME_OVER_CLOSE_CODE = 4000;

interface GameSocketOptions {
  aiDelayMs?: number;
}

export function createGameSocketUrl(
  locationLike: Pick<Location, "protocol" | "hostname">,
  options: GameSocketOptions = {},
): string {
  const protocol = locationLike.protocol === "https:" ? "wss" : "ws";
  const params = new URLSearchParams();
  if (options.aiDelayMs && options.aiDelayMs > 0) {
    params.set("ai_delay_ms", String(options.aiDelayMs));
  }
  const query = params.toString();
  return `${protocol}://${locationLike.hostname}:8000/ws/game${query ? `?${query}` : ""}`;
}

export function getReconnectDelayMs(): number {
  return RECONNECT_DELAY_MS;
}

export type { ServerEnvelope };
