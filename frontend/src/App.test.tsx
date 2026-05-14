import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { getIdleCopy, submitActionCopy, uiCopy } from "./copy";
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

  it("renders the shell controls and player list", () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    expect(view.queryByRole("heading", { name: "狼人杀对局面板" })).toBeNull();
    expect(view.getByRole("button", { name: "新局" })).toBeInTheDocument();
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

  it("starts a new game from the header controls", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    act(() => {
      MockWebSocket.instances[0]?.emit("message", {
        type: "SYSTEM_MSG",
        data: { message: "old marker" },
      });
    });

    expect(screen.getAllByText("old marker")).toHaveLength(1);

    fireEvent.click(within(view.container).getByRole("button", { name: "新局" }));

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(2);
      expect(screen.queryAllByText("old marker")).toHaveLength(0);
    });
  });

  it("persists AI pace and sends it on the next game socket", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    fireEvent.click(within(view.container).getByRole("button", { name: "快" }));
    expect(window.localStorage.getItem("werewolf.aiPace")).toBe("fast");

    fireEvent.click(within(view.container).getByRole("button", { name: "新局" }));

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(2);
      expect(MockWebSocket.instances[1]?.url).toBe("ws://localhost:8000/ws/game");
    });
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
      expect(within(view.container).getByLabelText("游戏状态提示")).toHaveTextContent("第 2 天 · 夜晚开始");
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
      expect(within(logList).getByText("你的查验结果是：5号玩家是狼人。")).toBeInTheDocument();
      expect(within(logList).getByText("私信")).toBeInTheDocument();
    });
  });

  it("promotes private night action feedback", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);

    MockWebSocket.instances[MockWebSocket.instances.length - 1]?.emit("message", {
      type: "CHAT_UPDATE",
      data: {
        message: "你选择今晚击杀 5 号。",
        speaker: "系统",
        visibility: "private",
      },
      meta: {
        event_type: "NIGHT_ACTION_FEEDBACK",
        target_seats: [5],
      },
    });

    await waitFor(() => {
      const actionPanel = view.container.querySelector(".action-panel");
      expect(actionPanel).not.toBeNull();
      expect(within(actionPanel as HTMLElement).getByLabelText("夜晚行动反馈")).toHaveTextContent(uiCopy.app.nightFeedbackLabel);
      expect(within(actionPanel as HTMLElement).getByLabelText("夜晚行动反馈")).toHaveTextContent("你选择今晚击杀 5号玩家。");
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
      expect(rows.some((row) => row.classList.contains("is-system") && row.textContent?.includes("天黑，请闭眼。"))).toBe(true);
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
      expect(within(view.container).getByLabelText("1号玩家")).toHaveTextContent("身份未知");
      const actionPanel = view.container.querySelector(".action-panel");
      expect(actionPanel).not.toBeNull();
      expect(within(actionPanel as HTMLElement).getByLabelText("你的身份")).toHaveTextContent("5号玩家");
      expect(within(actionPanel as HTMLElement).getByLabelText("你的身份")).toHaveTextContent("预言家");
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
      expect(within(view.container).getByLabelText("1号玩家")).toHaveTextContent("身份未知");
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
      expect(within(view.container).getByLabelText("2号状态")).toHaveTextContent("已出局");
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
      const banner = within(view.container).getByLabelText("游戏状态提示");
      expect(banner).toHaveTextContent("昨夜死亡");
      expect(banner).toHaveTextContent("4号玩家 已出局，4号玩家 可以发表遗言。");
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
        ballots: { 1: 2, 3: 2, 5: 2 },
        abstentions: [],
        banished_seat: 2,
        summary: "2号玩家被放逐出局。",
      },
    });

    await waitFor(() => {
      const actionPanel = view.container.querySelector(".action-panel");
      expect(actionPanel).not.toBeNull();
      expect(within(view.container).getByLabelText("4号状态")).toHaveTextContent("已出局");
      expect(within(view.container).getByLabelText("2号状态")).toHaveTextContent("已出局");
      expect(within(view.container).getByLabelText("游戏状态提示")).toHaveTextContent("投票已结算");
      expect(within(view.container).getByLabelText("游戏状态提示")).toHaveTextContent("投票结果：2号玩家被放逐出局。");
      expect(within(actionPanel as HTMLElement).getByLabelText("投票票型")).toHaveTextContent("2号玩家被放逐出局。");
      expect(within(actionPanel as HTMLElement).getByLabelText("2号玩家得票来源")).toHaveTextContent("1号玩家");
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
        recap: {
          day_count: 2,
          outcome_reason: "狼人全灭。",
          role_reveal_summary: "狼人：1号；神职：2号；平民：无。",
          players: [
            {
              seat_id: 1,
              role_code: "WOLF",
              side: "WOLF",
              is_alive: false,
              is_human: true,
            },
            {
              seat_id: 2,
              role_code: "SEER",
              side: "GOOD",
              is_alive: true,
              is_human: false,
            },
          ],
          key_events: [
            {
              day_count: 2,
              phase: "VOTE_RESULT",
              event_type: "BANISHMENT",
              message: "1号玩家被放逐出局。",
              actor_seat: null,
              target_seats: [1],
            },
          ],
          timeline: [
            {
              day_count: 1,
              phase: "NIGHT_END",
              event_type: "PEACEFUL_NIGHT",
              message: "昨夜平安夜。",
              actor_seat: null,
              target_seats: [],
            },
            {
              day_count: 2,
              phase: "VOTE_RESULT",
              event_type: "BANISHMENT",
              message: "1号玩家被放逐出局。",
              actor_seat: null,
              target_seats: [1],
            },
          ],
          nights: [
            {
              day_count: 1,
              wolf_target: 2,
              seer_seat: 2,
              seer_target: 1,
              seer_result: "WOLF",
              witch_seat: null,
              witch_save_target: null,
              witch_poison_target: null,
              dead_seats: [],
            },
          ],
          days: [
            {
              day_count: 2,
              speeches: [
                {
                  seat_id: 2,
                  message: "2号发言：我归票1号。",
                  event_type: "SPEECH",
                },
              ],
              vote: {
                votes: { 1: 3 },
                ballots: { 2: 1, 3: 1, 4: 1 },
                abstentions: [],
                banished_seat: 1,
                summary: "1号玩家被放逐出局。",
              },
              vote_explanation: "1号以 3 票成为最高票，被放逐出局。",
            },
          ],
          final_vote: {
            votes: { 1: 3 },
            ballots: { 2: 1, 3: 1, 4: 1 },
            abstentions: [],
            banished_seat: 1,
            summary: "1号玩家被放逐出局。",
          },
        },
      },
    });

    await waitFor(() => {
      const actionPanel = view.container.querySelector(".action-panel");
      expect(actionPanel).not.toBeNull();
      const logList = within(view.container).getByLabelText("对局日志列表");
      expect(within(logList).getByText("狼人已全部出局，好人阵营获胜。")).toBeInTheDocument();
      expect(within(view.container).getByLabelText("1号玩家")).toHaveTextContent("狼人");
      expect(within(view.container).getByLabelText("2号玩家")).toHaveTextContent("预言家");
      expect(within(actionPanel as HTMLElement).getByLabelText("结算复盘")).toHaveTextContent("好人胜利");
      expect(within(actionPanel as HTMLElement).getByLabelText("结算复盘")).toHaveTextContent("原因：狼人全灭。");
      expect(within(actionPanel as HTMLElement).getByLabelText("结算复盘")).not.toHaveTextContent("狼人：1号；神职：2号；平民：无。");
      expect(within(actionPanel as HTMLElement).getByLabelText("夜间因果")).toHaveTextContent("狼人击杀目标：2号玩家");
      expect(within(actionPanel as HTMLElement).queryByLabelText("白天因果")).toBeNull();
      expect(within(actionPanel as HTMLElement).queryByLabelText("完整时间线")).toBeNull();
      expect(within(actionPanel as HTMLElement).getByLabelText("全局票型")).toHaveTextContent("第 2 天票型");
      expect(within(actionPanel as HTMLElement).getByLabelText("全局票型")).toHaveTextContent("3票");
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

  it("unlocks action panel on require input and relocks after submit ack", async () => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);

    const view = render(<App />);
    const socket = MockWebSocket.instances[MockWebSocket.instances.length - 1];

    socket?.emit("message", {
      type: "REQUIRE_INPUT",
      data: {
        action_type: "VOTE",
        request_id: "input-vote",
        prompt: "请选择投票目标",
        allowed_targets: [2, 4, 7],
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByText("请选择投票目标")).toBeInTheDocument();
    });

    fireEvent.click(within(view.container).getByRole("button", { name: /4号玩家/ }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.VOTE.submitLabel,
      }),
    );

    expect(socket?.sentPayloads[0]).toContain("\"action_type\":\"VOTE\"");
    expect(socket?.sentPayloads[0]).toContain("\"target\":4");
    expect(socket?.sentPayloads[0]).toContain("\"request_id\":\"input-vote\"");
    expect(view.container.querySelector(".action-idle")).toBeNull();

    socket?.emit("message", {
      type: "SYSTEM_MSG",
      data: { message: "ack:VOTE" },
      meta: { status: "ack", action_type: "VOTE", request_id: "input-stale" },
    });

    expect(view.container.querySelector(".action-idle")).toBeNull();

    socket?.emit("message", {
      type: "SYSTEM_MSG",
      data: { message: "ack:VOTE" },
      meta: { status: "ack", action_type: "VOTE", request_id: "input-vote" },
    });

    await waitFor(() => {
      expect(within(view.container).getByText(getIdleCopy().heading)).toBeInTheDocument();
    });
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
        request_id: "input-hunter",
        prompt: "请选择开枪目标",
        allowed_targets: [2, 5],
      },
    });

    await waitFor(() => {
      expect(within(view.container).getByText("请选择开枪目标")).toBeInTheDocument();
    });

    fireEvent.click(within(view.container).getByRole("button", { name: /5号玩家/ }));
    // HUNTER_SHOOT requires two-step confirm.
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.HUNTER_SHOOT.submitLabel,
      }),
    );
    expect(socket?.sentPayloads).toHaveLength(0);
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: uiCopy.actionPanel.confirmAgain(submitActionCopy.HUNTER_SHOOT.submitLabel),
      }),
    );

    expect(socket?.sentPayloads[0]).toContain("\"action_type\":\"HUNTER_SHOOT\"");
    expect(socket?.sentPayloads[0]).toContain("\"target\":5");
    expect(socket?.sentPayloads[0]).toContain("\"request_id\":\"input-hunter\"");
    expect(view.container.querySelector(".action-idle")).toBeNull();

    socket?.emit("message", {
      type: "SYSTEM_MSG",
      data: { message: "ack:HUNTER_SHOOT" },
      meta: { status: "ack", action_type: "HUNTER_SHOOT", request_id: "input-hunter" },
    });

    await waitFor(() => {
      expect(view.container.querySelector(".action-idle")).not.toBeNull();
    });
  });
});
