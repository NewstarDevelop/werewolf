import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { getIdleCopy, submitActionCopy } from "./copy";
import { GAME_OVER_CLOSE_CODE, RECONNECT_DELAY_MS, createGameSocketUrl } from "./ws/client";

type MockSocketEvent = MessageEvent | CloseEvent;

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  listeners = new Map<string, Array<(event?: MockSocketEvent) => void>>();
  sentPayloads: string[] = [];
  isClosed = false;

  constructor(public readonly url: string) {
    MockWebSocket.instances.push(this);
  }

  addEventListener(type: string, handler: (event?: MockSocketEvent) => void) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  close() {
    if (this.isClosed) {
      return undefined;
    }
    this.isClosed = true;
    this.emit("close");
    return undefined;
  }

  send(payload: string) {
    this.sentPayloads.push(payload);
  }

  emit(type: string, data?: unknown) {
    const handlers = this.listeners.get(type) ?? [];
    const event = data === undefined
      ? undefined
      : type === "close"
        ? (data as CloseEvent)
        : ({ data: JSON.stringify(data) } as MessageEvent);
    handlers.forEach((handler) => handler(event));
  }
}

describe("App", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders the shell heading and player list", () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    expect(view.getByRole("heading", { name: "狼人杀对局面板" })).toBeInTheDocument();
    expect(view.getByLabelText("玩家状态列表").children).toHaveLength(9);
    expect(MockWebSocket.instances[0]?.url).toContain("/ws/game");
  });

  it("toggles and persists the manual theme", () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    fireEvent.click(within(view.container).getByRole("button", { name: "切换至暗色主题" }));

    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(window.localStorage.getItem("werewolf.theme")).toBe("dark");
    expect(within(view.container).getByRole("button", { name: "切换至亮色主题" })).toBeInTheDocument();
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
      expect(within(view.container).getByLabelText("3号状态")).toHaveTextContent("推演中");
    });
  });

  it("creates the backend websocket url from browser location", () => {
    MockWebSocket.instances = [];
    const url = createGameSocketUrl(
      new URL("http://localhost:5173/") as unknown as Location,
    );

    expect(url).toBe("ws://localhost:8000/ws/game");
  });

  it("reconnects after the websocket closes", async () => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    try {
      vi.stubGlobal("WebSocket", MockWebSocket);

      render(<App />);

      expect(MockWebSocket.instances).toHaveLength(1);

      MockWebSocket.instances[0]?.emit("close");
      await vi.advanceTimersByTimeAsync(RECONNECT_DELAY_MS);

      expect(MockWebSocket.instances).toHaveLength(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not reconnect after the app unmounts", async () => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    try {
      vi.stubGlobal("WebSocket", MockWebSocket);

      const view = render(<App />);
      expect(MockWebSocket.instances).toHaveLength(1);

      view.unmount();
      await vi.advanceTimersByTimeAsync(RECONNECT_DELAY_MS);

      expect(MockWebSocket.instances).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not reconnect after a terminal game over close", async () => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    try {
      vi.stubGlobal("WebSocket", MockWebSocket);

      render(<App />);
      expect(MockWebSocket.instances).toHaveLength(1);

      act(() => {
        MockWebSocket.instances[0]?.emit("message", {
          type: "GAME_OVER",
          data: {
            winning_side: "GOOD",
            summary: "game over",
            revealed_roles: {
              1: "SEER",
            },
          },
        });
        MockWebSocket.instances[0]?.emit("close", { code: GAME_OVER_CLOSE_CODE } as CloseEvent);
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(RECONNECT_DELAY_MS);
      });

      expect(MockWebSocket.instances).toHaveLength(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("clears prior session state before reconnecting", async () => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    try {
      vi.stubGlobal("WebSocket", MockWebSocket);

      const view = render(<App />);

      act(() => {
        MockWebSocket.instances[0]?.emit("message", {
          type: "SYSTEM_MSG",
          data: { message: "old marker" },
        });
        MockWebSocket.instances[0]?.emit("message", {
          type: "AI_THINKING",
          data: { seat_id: 3, is_thinking: true },
        });
      });

      expect(screen.getAllByText("old marker")).toHaveLength(1);
      expect(view.container.querySelector(".player-card.is-thinking")).not.toBeNull();

      act(() => {
        MockWebSocket.instances[0]?.emit("close");
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(RECONNECT_DELAY_MS);
      });

      expect(MockWebSocket.instances).toHaveLength(2);
      expect(screen.queryAllByText("old marker")).toHaveLength(0);
      expect(view.container.querySelector(".player-card.is-thinking")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("updates the connection phase across reconnect attempts", async () => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    try {
      vi.stubGlobal("WebSocket", MockWebSocket);

      const view = render(<App />);
      expect(view.container.querySelector("[data-connection-phase=\"connecting\"]")).not.toBeNull();

      act(() => {
        MockWebSocket.instances[0]?.emit("open");
      });
      expect(view.container.querySelector("[data-connection-phase=\"open\"]")).not.toBeNull();

      act(() => {
        MockWebSocket.instances[0]?.emit("close");
      });
      expect(view.container.querySelector("[data-connection-phase=\"closed\"]")).not.toBeNull();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(RECONNECT_DELAY_MS);
      });
      expect(MockWebSocket.instances).toHaveLength(2);
      expect(view.container.querySelector("[data-connection-phase=\"connecting\"]")).not.toBeNull();

      act(() => {
        MockWebSocket.instances[1]?.emit("open");
      });
      expect(view.container.querySelector("[data-connection-phase=\"open\"]")).not.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("tracks structured game phase messages on the app shell", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "PHASE_CHANGED",
      data: {
        phase: "NIGHT_START",
        day_count: 2,
      },
    });

    await waitFor(() => {
      expect(view.container.querySelector("[data-game-phase=\"NIGHT_START\"]")).not.toBeNull();
      expect(within(view.container).getByLabelText("战局提示")).toHaveTextContent("第 2 日 · 入夜");
    });
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
      expect(within(logList).getByText("私见")).toBeInTheDocument();
    });
  });

  it("classifies public chat updates as system broadcasts or speeches", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);
    const socket = MockWebSocket.instances[MockWebSocket.instances.length - 1];

    socket?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "天黑请闭眼。",
        speaker: "系统",
        visibility: "public",
      },
    });
    socket?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "3号发言：我先听后置位。",
        speaker: "系统",
        visibility: "public",
      },
    });

    await waitFor(() => {
      const rows = Array.from(view.container.querySelectorAll(".chat-row"));
      expect(rows.some((row) => row.classList.contains("is-system") && row.textContent?.includes("天黑请闭眼。"))).toBe(true);
      expect(rows.some((row) => row.classList.contains("is-speech") && row.textContent?.includes("3号玩家") && row.textContent?.includes("3号发言：我先听后置位。"))).toBe(true);
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
      expect(within(view.container).getByLabelText("1号玩家")).toHaveTextContent("局外人");
    });
  });

  it("syncs the human seat and role from structured player patches", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "PLAYER_STATE_PATCH",
      data: {
        players: [
          {
            seat_id: 5,
            is_alive: true,
            is_human: true,
            role_code: "WITCH",
            is_thinking: false,
          },
        ],
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByLabelText("5号玩家")).toHaveTextContent("真人 · 女巫");
      expect(within(view.container).getByLabelText("1号玩家")).toHaveTextContent("局外人");
    });
  });

  it("updates player alive state from public death logs", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "2号玩家被放逐出局。",
        speaker: "系统",
        visibility: "public",
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByLabelText("2号状态")).toHaveTextContent("墓碑");
    });
  });

  it("updates multiple player seats from nightly death announcements", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "天亮了。昨夜死亡的是 4号、1号。",
        speaker: "系统",
        visibility: "public",
      },
    });

    await waitFor(() => {
      const deadSeats = Array.from(view.container.querySelectorAll(".player-card.is-dead .seat-chip")).map((node) =>
        node.textContent,
      );
      expect(deadSeats).toContain("1");
      expect(deadSeats).toContain("4");
    });
  });

  it("updates player alive state from hunter shot logs", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "1号猎人开枪带走了2号玩家。",
        speaker: "系统",
        visibility: "public",
      },
    });

    await waitFor(() => {
      const deadSeats = Array.from(view.container.querySelectorAll(".player-card.is-dead .seat-chip")).map((node) =>
        node.textContent,
      );
      expect(deadSeats).toContain("2");
    });
  });

  it("summarizes structured death reveals in the result banner", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "DEATH_REVEALED",
      data: {
        dead_seats: [4],
        eligible_last_words: [4],
        day_count: 1,
      },
    });

    await waitFor(() => {
      const banner = within(view.container).getByLabelText("战局提示");
      expect(banner).toHaveTextContent("昨夜有名");
      expect(banner).toHaveTextContent("4号玩家 已成墓碑，4号玩家 尚有遗言。");
    });
  });

  it("updates player alive state from structured death and vote events", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);
    const socket = MockWebSocket.instances[MockWebSocket.instances.length - 1];

    socket?.emit("message", {
      type: "DEATH_REVEALED",
      data: {
        dead_seats: [4],
        eligible_last_words: [4],
        day_count: 1,
      },
    });
    socket?.emit("message", {
      type: "VOTE_RESOLVED",
      data: {
        votes: { 2: 3 },
        abstentions: [],
        banished_seat: 2,
        summary: "2号玩家被放逐出局。",
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByLabelText("4号状态")).toHaveTextContent("墓碑");
      expect(within(view.container).getByLabelText("2号状态")).toHaveTextContent("墓碑");
      expect(within(view.container).getByLabelText("战局提示")).toHaveTextContent("票落成局");
      expect(within(view.container).getByLabelText("战局提示")).toHaveTextContent("刚刚开票：2号玩家被放逐出局。");
    });
  });

  it("renders game over summary and revealed roles", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "GAME_OVER",
      data: {
        winning_side: "GOOD",
        summary: "狼人已全部出局，好人阵营获胜。",
        revealed_roles: {
          1: "WOLF",
          2: "SEER",
        },
      },
    });

    await waitFor(() => {
      const logList = within(view.container).getByLabelText("对局日志列表");
      expect(within(logList).getByText("狼人已全部出局，好人阵营获胜。")).toBeInTheDocument();
      expect(within(view.container).getByLabelText("1号玩家")).toHaveTextContent("狼人");
      expect(within(view.container).getByLabelText("2号玩家")).toHaveTextContent("预言家");
    });
  });

  it("clears thinking state when the game is over", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);
    const socket = MockWebSocket.instances[MockWebSocket.instances.length - 1];

    socket?.emit("message", {
      type: "AI_THINKING",
      data: { seat_id: 3, is_thinking: true },
    });

    await waitFor(() => {
      expect(view.container.querySelector(".player-card.is-thinking")).not.toBeNull();
    });

    socket?.emit("message", {
      type: "GAME_OVER",
      data: {
        winning_side: "GOOD",
        summary: "好人阵营获胜。",
        revealed_roles: {
          3: "WOLF",
        },
      },
    });

    await waitFor(() => {
      expect(view.container.querySelector(".player-card.is-thinking")).toBeNull();
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
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.VOTE.submitLabel,
      }),
    );

    expect(socket?.sentPayloads[0]).toContain("\"action_type\":\"VOTE\"");
    expect(socket?.sentPayloads[0]).toContain("\"target\":4");
    expect(within(view.container).getByText(getIdleCopy().heading)).toBeInTheDocument();
  });
  it("submits hunter shoot actions through the app websocket bridge", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);
    const socket = MockWebSocket.instances[MockWebSocket.instances.length - 1];

    socket?.emit("message", {
      type: "REQUIRE_INPUT",
      data: {
        action_type: "HUNTER_SHOOT",
        prompt: "请选择开枪目标",
        allowed_targets: [2, 5],
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByText("请选择开枪目标")).toBeInTheDocument();
    });

    fireEvent.click(within(view.container).getByRole("button", { name: "5号" }));
    // HUNTER_SHOOT requires two-step confirm.
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.HUNTER_SHOOT.submitLabel,
      }),
    );
    expect(socket?.sentPayloads).toHaveLength(0);
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: `再按一次 · ${submitActionCopy.HUNTER_SHOOT.submitLabel}`,
      }),
    );

    expect(socket?.sentPayloads[0]).toContain("\"action_type\":\"HUNTER_SHOOT\"");
    expect(socket?.sentPayloads[0]).toContain("\"target\":5");
    expect(view.container.querySelector(".action-idle")).not.toBeNull();
  });
});
