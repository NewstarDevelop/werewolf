import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VoteBoard } from "./VoteBoard";

describe("VoteBoard", () => {
  it("renders vote totals, voters and abstentions", () => {
    render(
      <VoteBoard
        result={{
          votes: { 2: 3, 5: 1 },
          ballots: { 1: 2, 3: 2, 6: 5, 8: 2 },
          abstentions: [4],
          banishedSeat: 2,
          summary: "2号玩家被放逐出局。",
        }}
      />,
    );

    expect(screen.getByLabelText("投票票型")).toHaveTextContent("2号玩家被放逐出局。");
    expect(screen.getByText("5 人计票")).toBeInTheDocument();
    expect(screen.getByLabelText("2号玩家得票")).toHaveAttribute("aria-valuenow", "3");
    expect(screen.getByText("2号玩家")).toBeInTheDocument();
    expect(screen.getByText("3票")).toBeInTheDocument();

    const source = screen.getByLabelText("2号玩家得票来源");
    expect(within(source).getByText("1号玩家")).toBeInTheDocument();
    expect(within(source).getByText("3号玩家")).toBeInTheDocument();
    expect(within(source).getByText("8号玩家")).toBeInTheDocument();
    expect(within(screen.getByLabelText("弃票玩家")).getByText("4号玩家")).toBeInTheDocument();
  });
});
