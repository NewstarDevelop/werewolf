import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerList, type PlayerListItem } from "./PlayerList";

describe("PlayerList", () => {
  it("renders human, alive and thinking states", () => {
    const players: PlayerListItem[] = [
      {
        seatId: 1,
        isAlive: true,
        isHuman: true,
        roleLabel: "预言家",
        isThinking: false,
      },
      {
        seatId: 2,
        isAlive: false,
        isHuman: false,
        isThinking: false,
      },
      {
        seatId: 3,
        isAlive: true,
        isHuman: false,
        isThinking: true,
      },
    ];

    render(<PlayerList players={players} />);

    expect(screen.getByText("真人 · 预言家")).toBeInTheDocument();
    expect(screen.getByLabelText("2号状态")).toHaveTextContent("墓碑");
    expect(screen.getByLabelText("3号状态")).toHaveTextContent("思考中");
  });
});
