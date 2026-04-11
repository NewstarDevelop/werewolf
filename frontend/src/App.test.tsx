import { render, screen, waitFor, within } from "@testing-library/react";
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
  it("renders the shell heading and player list", () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    expect(view.getByRole("heading", { name: "工程骨架已启动" })).toBeInTheDocument();
    expect(view.getByLabelText("玩家状态列表").children).toHaveLength(9);
    expect(MockWebSocket.instances[0]?.url).toContain("/ws/game");
  });

  it("updates player thinking status from websocket events", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "AI_THINKING",
      data: { seat_id: 3, is_thinking: true },
    });

    await waitFor(() => {
      expect(within(view.container).getByLabelText("3号状态")).toHaveTextContent("思考中");
    });
  });

  it("creates the backend websocket url from browser location", () => {
    MockWebSocket.instances = [];
    const url = createGameSocketUrl(
      new URL("http://localhost:5173/") as unknown as Location,
    );

    expect(url).toBe("ws://localhost:8000/ws/game");
  });
});
