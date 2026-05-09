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

  it("uses chat metadata for speeches and deaths when available", () => {
    const afterSpeech = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "CHAT_UPDATE",
        data: {
          message: "我站边这个预言家。",
          speaker: "系统",
          visibility: "public",
        },
        meta: {
          message_kind: "speech",
          event_type: "SPEECH",
          actor_seat: 3,
        },
      },
    });

    const afterBanishment = gameReducer(afterSpeech, {
      type: "server-envelope",
      envelope: {
        type: "CHAT_UPDATE",
        data: {
          message: "2号玩家被放逐出局。",
          speaker: "系统",
          visibility: "public",
        },
        meta: {
          event_type: "BANISHMENT",
          target_seats: [2],
        },
      },
    });

    expect(afterSpeech.entries[0]).toMatchObject({
      kind: "speech",
      speaker: "3号玩家",
      message: "我站边这个预言家。",
    });
    expect(afterBanishment.players.find((player) => player.seatId === 2)?.isAlive).toBe(false);
  });

  it("tracks private night action feedback", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
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
      },
    });

    expect(state.lastNightActionFeedback).toEqual({
      message: "你选择今晚击杀 5 号。",
      targetSeats: [5],
    });
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
          ballots: { 1: 3, 2: 3 },
          abstentions: [5],
          banished_seat: 3,
          summary: "3号玩家被放逐出局。",
        },
      },
    });

    expect(state.players.find((player) => player.seatId === 3)?.isAlive).toBe(false);
    expect(state.lastVoteResult).toEqual({
      votes: { 3: 2 },
      ballots: { 1: 3, 2: 3 },
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

  it("builds settlement review data from game over recap", () => {
    const state = gameReducer(createInitialGameState(), {
      type: "server-envelope",
      envelope: {
        type: "GAME_OVER",
        data: {
          winning_side: "WOLF",
          summary: "神职已全部出局，狼人阵营获胜。",
          revealed_roles: {
            1: "SEER",
            2: "WOLF",
          },
          recap: {
            day_count: 2,
            outcome_reason: "神职屠边。",
            players: [
              {
                seat_id: 1,
                role_code: "SEER",
                side: "GOOD",
                is_alive: false,
                is_human: true,
              },
              {
                seat_id: 2,
                role_code: "WOLF",
                side: "WOLF",
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
            nights: [
              {
                day_count: 2,
                wolf_target: 1,
                seer_seat: 1,
                seer_target: 2,
                seer_result: "WOLF",
                witch_seat: null,
                witch_save_target: null,
                witch_poison_target: null,
                dead_seats: [1],
              },
            ],
            days: [
              {
                day_count: 2,
                speeches: [
                  {
                    seat_id: 1,
                    message: "1号发言：我会归票2号。",
                    event_type: "SPEECH",
                  },
                ],
                vote: {
                  votes: { 1: 2 },
                  ballots: { 2: 1, 3: 1 },
                  abstentions: [],
                  banished_seat: 1,
                  summary: "1号玩家被放逐出局。",
                },
                vote_explanation: "1号以 2 票成为最高票，被放逐出局。",
              },
            ],
            final_vote: {
              votes: { 1: 2 },
              ballots: { 2: 1, 3: 1 },
              abstentions: [],
              banished_seat: 1,
              summary: "1号玩家被放逐出局。",
            },
          },
        },
      },
    });

    expect(state.settlementReview).toMatchObject({
      winningSide: "WOLF",
      outcomeReason: "神职屠边。",
      dayCount: 2,
      players: [
        {
          seatId: 1,
          roleLabel: "预言家",
          isHuman: true,
        },
        {
          seatId: 2,
          roleLabel: "狼人",
          isAlive: true,
        },
      ],
      keyEvents: [
        {
          phase: "VOTE_RESULT",
          message: "1号玩家被放逐出局。",
        },
      ],
      nights: [
        {
          wolfTarget: 1,
          seerResult: "WOLF",
          deadSeats: [1],
        },
      ],
      days: [
        {
          voteExplanation: "1号以 2 票成为最高票，被放逐出局。",
        },
      ],
      finalVote: {
        banishedSeat: 1,
        summary: "1号玩家被放逐出局。",
      },
    });
  });
});
