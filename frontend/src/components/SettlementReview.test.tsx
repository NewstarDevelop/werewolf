import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SettlementReview } from "./SettlementReview";

describe("SettlementReview", () => {
  it("renders outcome, revealed roles, key events and final vote", () => {
    render(
      <SettlementReview
        review={{
          winningSide: "GOOD",
          summary: "狼人已全部出局，好人阵营获胜。",
          outcomeReason: "狼人全灭。",
          roleRevealSummary: "狼人：2号；神职：1号；平民：无。",
          dayCount: 2,
          players: [
            {
              seatId: 1,
              roleCode: "SEER",
              roleLabel: "预言家",
              side: "GOOD",
              isAlive: true,
              isHuman: true,
            },
            {
              seatId: 2,
              roleCode: "WOLF",
              roleLabel: "狼人",
              side: "WOLF",
              isAlive: false,
              isHuman: false,
            },
          ],
          keyEvents: [
            {
              dayCount: 1,
              phase: "DAY_START",
              eventType: "NIGHT_DEATH",
              message: "天亮了。昨夜死亡的是 3号。",
              actorSeat: null,
              targetSeats: [3],
            },
          ],
          timeline: [
            {
              dayCount: 1,
              phase: "DAY_START",
              eventType: "NIGHT_DEATH",
              message: "天亮了。昨夜死亡的是 3号。",
              actorSeat: null,
              targetSeats: [3],
            },
            {
              dayCount: 1,
              phase: "DAY_SPEAKING",
              eventType: "SPEECH",
              message: "1号发言：我查杀2号。",
              actorSeat: 1,
              targetSeats: [],
            },
          ],
          nights: [
            {
              dayCount: 1,
              wolfTarget: 3,
              seerSeat: 1,
              seerTarget: 2,
              seerResult: "WOLF",
              witchSeat: 4,
              witchSaveTarget: 3,
              witchPoisonTarget: null,
              deadSeats: [],
            },
          ],
          days: [
            {
              dayCount: 1,
              speeches: [
                {
                  seatId: 1,
                  message: "1号发言：我查杀2号。",
                  eventType: "SPEECH",
                },
              ],
              vote: {
                votes: { 2: 3 },
                ballots: { 1: 2, 3: 2, 4: 2 },
                abstentions: [5],
                banishedSeat: 2,
                summary: "2号玩家被放逐出局。",
              },
              voteExplanation: "2号以 3 票成为最高票，被放逐出局。",
            },
            {
              dayCount: 2,
              speeches: [],
              vote: {
                votes: { 1: 1, 2: 1 },
                ballots: { 1: 2, 2: 1 },
                abstentions: [],
                banishedSeat: null,
                summary: "出现平票，本轮无人出局。",
              },
              voteExplanation: "出现平票，本轮无人出局。",
            },
          ],
          finalVote: {
            votes: { 2: 3 },
            ballots: { 1: 2, 3: 2, 4: 2 },
            abstentions: [5],
            banishedSeat: 2,
            summary: "2号玩家被放逐出局。",
          },
        }}
      />,
    );

    expect(screen.getByLabelText("结算复盘")).toHaveTextContent("好人胜利");
    expect(screen.getByLabelText("结算复盘")).toHaveTextContent("第 2 天终局");
    expect(screen.getByLabelText("结算复盘")).toHaveTextContent("原因：狼人全灭。");
    expect(screen.getByLabelText("结算复盘")).not.toHaveTextContent("狼人：2号；神职：1号；平民：无。");
    expect(within(screen.getByLabelText("阵营翻牌")).getByText("预言家")).toBeInTheDocument();
    expect(within(screen.getByLabelText("阵营翻牌")).getByText("狼人")).toBeInTheDocument();
    expect(within(screen.getByLabelText("夜间因果")).getByText("狼人击杀目标：3号玩家")).toBeInTheDocument();
    expect(within(screen.getByLabelText("夜间因果")).getByText("夜晚结果：平安夜")).toBeInTheDocument();
    expect(screen.queryByLabelText("白天因果")).toBeNull();
    expect(screen.queryByLabelText("完整时间线")).toBeNull();
    expect(within(screen.getByLabelText("全局票型")).getByText("第 1 天票型")).toBeInTheDocument();
    expect(within(screen.getByLabelText("全局票型")).getByText("第 2 天票型")).toBeInTheDocument();
    expect(within(screen.getByLabelText("全局票型")).getByText("2号玩家被放逐出局。")).toBeInTheDocument();
    expect(within(screen.getByLabelText("全局票型")).getByText("3票")).toBeInTheDocument();
    expect(within(screen.getByLabelText("第 1 天票型")).getByLabelText("2号玩家得票来源")).toHaveTextContent("1号玩家");
    expect(within(screen.getByLabelText("第 1 天票型")).getByLabelText("2号玩家得票来源")).toHaveTextContent("3号玩家");
    expect(within(screen.getByLabelText("第 1 天票型")).getByLabelText("2号玩家得票来源")).toHaveTextContent("4号玩家");
    expect(within(screen.getByLabelText("第 2 天票型")).getByLabelText("1号玩家得票来源")).toHaveTextContent("2号玩家");
    expect(within(screen.getByLabelText("全局票型")).getByText("弃票：5号玩家")).toBeInTheDocument();
  });
});
