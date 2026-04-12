import type { ServerEnvelope } from "../types/ws";

export type ConnectionPhase = "idle" | "connecting" | "open" | "closed" | "error";
export const RECONNECT_DELAY_MS = 1000;
export const GAME_OVER_CLOSE_CODE = 4000;

export function createGameSocketUrl(locationLike: Pick<Location, "protocol" | "hostname">): string {
  const protocol = locationLike.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${locationLike.hostname}:8000/ws/game`;
}

export function getReconnectDelayMs(): number {
  return RECONNECT_DELAY_MS;
}

export type { ServerEnvelope };
