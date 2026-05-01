import { describe, expect, it } from "vitest";

import { createInitialGameState, gameReducer } from "./gameState";

describe("gameReducer", () => {
  it("syncs private identity messages into the player view", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "CHAT_UPDATE",
        data: {
          message: "你的座位号是 5 号，身份是 SEER。",
          speaker: "系统",
          visibility: "private",
        },
      },
    });

    expect(state.players.find((player) => player.seatId === 5)).toMatchObject({
      isHuman: true,
      roleCode: "SEER",
      roleLabel: "预言家",
    });
    expect(state.players.find((player) => player.seatId === 1)).toMatchObject({
      isHuman: false,
      roleLabel: undefined,
    });
  });

  it("updates deaths from public announcements", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "CHAT_UPDATE",
        data: {
          message: "天亮了。昨夜死亡的是 4号、1号。",
          speaker: "系统",
          visibility: "public",
        },
      },
    });

    expect(state.players.find((player) => player.seatId === 1)?.isAlive).toBe(false);
    expect(state.players.find((player) => player.seatId === 4)?.isAlive).toBe(false);
  });

  it("applies structured player state patches", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "PLAYER_STATE_PATCH",
        data: {
          players: [
            {
              seat_id: 4,
              is_alive: false,
              is_human: true,
              role_code: "WITCH",
              is_thinking: false,
            },
          ],
        },
      },
    });

    expect(state.players.find((player) => player.seatId === 4)).toMatchObject({
      isAlive: false,
      isHuman: true,
      roleCode: "WITCH",
      roleLabel: "女巫",
      isThinking: false,
    });
    expect(state.players.find((player) => player.seatId === 1)).toMatchObject({
      isHuman: false,
      roleLabel: undefined,
    });
  });

  it("tracks structured phase changes", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "PHASE_CHANGED",
        data: {
          phase: "DAY_SPEAKING",
          day_count: 2,
        },
      },
    });

    expect(state.currentPhase).toBe("DAY_SPEAKING");
    expect(state.dayCount).toBe(2);
  });

  it("applies structured death reveal events", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "DEATH_REVEALED",
        data: {
          dead_seats: [2, 7],
          eligible_last_words: [2],
          day_count: 1,
        },
      },
    });

    expect(state.players.find((player) => player.seatId === 2)?.isAlive).toBe(false);
    expect(state.players.find((player) => player.seatId === 7)?.isAlive).toBe(false);
    expect(state.lastDeathReveal).toEqual({
      deadSeats: [2, 7],
      eligibleLastWords: [2],
      dayCount: 1,
    });
  });

  it("records structured vote results and applies banishment", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "VOTE_RESOLVED",
        data: {
          votes: { 3: 2 },
          abstentions: [5],
          banished_seat: 3,
          summary: "3号玩家被放逐出局。",
        },
      },
    });

    expect(state.players.find((player) => player.seatId === 3)?.isAlive).toBe(false);
    expect(state.lastVoteResult).toEqual({
      votes: { 3: 2 },
      abstentions: [5],
      banishedSeat: 3,
      summary: "3号玩家被放逐出局。",
    });
  });

  it("clears pending action and reveals roles on game over", () => {
    const waitingState = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "REQUIRE_INPUT",
        data: {
          action_type: "VOTE",
          prompt: "请选择投票目标",
          allowed_targets: [2, 3],
        },
      },
    });

    const terminalState = gameReducer(waitingState, {
      type: "server-envelope",
      envelope: {
        type: "GAME_OVER",
        data: {
          winning_side: "GOOD",
          summary: "狼人已全部出局，好人阵营获胜。",
          revealed_roles: {
            2: "WOLF",
          },
        },
      },
    });

    expect(terminalState.isTerminal).toBe(true);
    expect(terminalState.pendingAction).toBeNull();
    expect(terminalState.entries[terminalState.entries.length - 1]).toMatchObject({
      kind: "system",
      message: "狼人已全部出局，好人阵营获胜。",
    });
    expect(terminalState.players.find((player) => player.seatId === 2)).toMatchObject({
      roleCode: "WOLF",
      roleLabel: "狼人",
    });
  });
});
