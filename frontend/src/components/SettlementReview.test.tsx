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
    expect(screen.getByLabelText("结算复盘")).toHaveTextContent("第 2 日终局");
    expect(screen.getByLabelText("结算复盘")).toHaveTextContent("原因：狼人全灭。");
    expect(within(screen.getByLabelText("阵营翻牌")).getByText("预言家")).toBeInTheDocument();
    expect(within(screen.getByLabelText("阵营翻牌")).getByText("狼人")).toBeInTheDocument();
    expect(within(screen.getByLabelText("夜间因果")).getByText("狼人刀向：3号玩家")).toBeInTheDocument();
    expect(within(screen.getByLabelText("夜间因果")).getByText("夜晚结果：平安夜")).toBeInTheDocument();
    expect(screen.getByLabelText("白天因果")).toHaveTextContent("1号发言：我查杀2号。");
    expect(screen.getByLabelText("白天因果")).toHaveTextContent("投票因果：2号以 3 票成为最高票，被放逐出局。");
    expect(within(screen.getByLabelText("关键节点")).getByText("第 1 日 · 天明")).toBeInTheDocument();
    expect(within(screen.getByLabelText("终局票型")).getByText("2号玩家被放逐出局。")).toBeInTheDocument();
    expect(within(screen.getByLabelText("终局票型")).getByText("3票")).toBeInTheDocument();
    expect(within(screen.getByLabelText("终局票型")).getByText("弃票：5号玩家")).toBeInTheDocument();
  });
});
