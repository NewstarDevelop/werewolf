import { render, screen, within } from "@testing-library/react";
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
    expect(screen.getByLabelText("3号状态")).toHaveTextContent("推演中");
  });

  it("renders revealed non-human wolf teammates", () => {
    const players: PlayerListItem[] = [
      {
        seatId: 7,
        isAlive: true,
        isHuman: true,
        roleLabel: "狼人",
        roleCode: "WOLF",
        isThinking: false,
      },
      {
        seatId: 2,
        isAlive: true,
        isHuman: false,
        roleLabel: "狼人",
        roleCode: "WOLF",
        isThinking: false,
      },
    ];

    const view = render(<PlayerList players={players} />);

    expect(within(view.container).getByLabelText("7号玩家")).toHaveTextContent("真人 · 狼人");
    expect(within(view.container).getByLabelText("2号玩家")).toHaveTextContent("狼人");
  });
});
