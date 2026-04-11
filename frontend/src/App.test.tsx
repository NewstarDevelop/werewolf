import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { createGameSocketUrl } from "./ws/client";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  listeners = new Map<string, Array<(event?: MessageEvent) => void>>();

  constructor(public readonly url: string) {
    MockWebSocket.instances.push(this);
  }

  addEventListener(type: string, handler: (event?: MessageEvent) => void) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  close() {
    return undefined;
  }

  emit(type: string, data?: unknown) {
    const handlers = this.listeners.get(type) ?? [];
    const event = data === undefined ? undefined : ({ data: JSON.stringify(data) } as MessageEvent);
    handlers.forEach((handler) => handler(event));
  }
}

describe("App", () => {
  it("renders the shell heading", () => {
    vi.stubGlobal("WebSocket", MockWebSocket);

    render(<App />);

    expect(screen.getByRole("heading", { name: "工程骨架已启动" })).toBeInTheDocument();
    expect(MockWebSocket.instances[0]?.url).toContain("/ws/game");
  });

  it("creates the backend websocket url from browser location", () => {
    const url = createGameSocketUrl(
      new URL("http://localhost:5173/") as unknown as Location,
    );

    expect(url).toBe("ws://localhost:8000/ws/game");
  });
});
