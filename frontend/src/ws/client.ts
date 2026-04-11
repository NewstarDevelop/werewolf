export type ConnectionPhase = "idle" | "connecting" | "open" | "closed" | "error";

export interface ServerEnvelope {
  type: "SYSTEM_MSG";
  data: {
    message: string;
  };
}

export function createGameSocketUrl(locationLike: Pick<Location, "protocol" | "hostname">): string {
  const protocol = locationLike.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${locationLike.hostname}:8000/ws/game`;
}
