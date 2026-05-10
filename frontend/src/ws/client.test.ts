import { describe, expect, it } from "vitest";

import { RECONNECT_DELAY_MS, createGameSocketUrl, getReconnectDelayMs } from "./client";

describe("ws client helpers", () => {
  it("creates the backend websocket url from browser location", () => {
    const url = createGameSocketUrl(
      new URL("http://localhost:5173/") as unknown as Location,
    );

    expect(url).toBe("ws://localhost:8000/ws/game");
  });

  it("adds AI pacing when requested", () => {
    const url = createGameSocketUrl(
      new URL("http://localhost:5173/") as unknown as Location,
      { aiDelayMs: 700 },
    );

    expect(url).toBe("ws://localhost:8000/ws/game?ai_delay_ms=700");
  });

  it("exposes the reconnect delay used by the app shell", () => {
    expect(getReconnectDelayMs()).toBe(RECONNECT_DELAY_MS);
    expect(RECONNECT_DELAY_MS).toBe(1000);
  });
});
