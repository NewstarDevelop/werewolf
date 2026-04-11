import type { ServerEnvelope } from "../types/ws";

export type ConnectionPhase = "idle" | "connecting" | "open" | "closed" | "error";

export function createGameSocketUrl(locationLike: Pick<Location, "protocol" | "hostname">): string {
  const protocol = locationLike.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${locationLike.hostname}:8000/ws/game`;
}

export type { ServerEnvelope };
