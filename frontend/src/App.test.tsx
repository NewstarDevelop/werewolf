import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { createGameSocketUrl } from "./ws/client";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  listeners = new Map<string, Array<(event?: MessageEvent) => void>>();
  sentPayloads: string[] = [];

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

  send(payload: string) {
    this.sentPayloads.push(payload);
  }

  emit(type: string, data?: unknown) {
    const handlers = this.listeners.get(type) ?? [];
    const event = data === undefined ? undefined : ({ data: JSON.stringify(data) } as MessageEvent);
    handlers.forEach((handler) => handler(event));
  }
}

describe("App", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

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

  it("renders structured chat entries from websocket messages", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "你的查验结果是：5号是狼人。",
        speaker: "你的视角",
        visibility: "private",
      },
    });

    await waitFor(() => {
      const logList = within(view.container).getByLabelText("对局日志列表");
      expect(within(logList).getByText("你的查验结果是：5号是狼人。")).toBeInTheDocument();
      expect(within(logList).getByText("私信")).toBeInTheDocument();
    });
  });

  it("syncs the human seat and role from private identity messages", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "你的座位号是 5 号，身份是 SEER。",
        speaker: "系统",
        visibility: "private",
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByLabelText("5号玩家")).toHaveTextContent("真人 · 预言家");
      expect(within(view.container).getByLabelText("1号玩家")).toHaveTextContent("AI 玩家");
    });
  });

  it("unlocks action panel on require input and relocks after submit", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);
    const socket = MockWebSocket.instances[MockWebSocket.instances.length - 1];

    socket?.emit("message", {
      type: "REQUIRE_INPUT",
      data: {
        action_type: "VOTE",
        prompt: "请选择投票目标",
        allowed_targets: [2, 4, 7],
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByText("请选择投票目标")).toBeInTheDocument();
    });

    fireEvent.click(within(view.container).getByRole("button", { name: "4号" }));
    fireEvent.click(within(view.container).getByRole("button", { name: "确认提交" }));

    expect(socket?.sentPayloads[0]).toContain("\"action_type\":\"VOTE\"");
    expect(socket?.sentPayloads[0]).toContain("\"target\":4");
    expect(within(view.container).getByText("等待中")).toBeInTheDocument();
  });
});
