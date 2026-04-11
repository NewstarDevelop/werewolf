import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatHistory, type ChatEntry } from "./ChatHistory";

describe("ChatHistory", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("renders system, private and speech entries", () => {
    const entries: ChatEntry[] = [
      { id: "1", kind: "system", message: "天黑请闭眼。" },
      { id: "2", kind: "private", message: "你的查验结果是：5号是狼人。", speaker: "你的视角" },
      { id: "3", kind: "speech", message: "我是预言家。", speaker: "2号玩家" },
    ];

    render(<ChatHistory entries={entries} />);

    expect(screen.getByText("系统")).toBeInTheDocument();
    expect(screen.getByText("私信")).toBeInTheDocument();
    expect(screen.getByText("发言")).toBeInTheDocument();
    expect(screen.getByText("2号玩家")).toBeInTheDocument();
  });

  it("scrolls to the latest entry when entries change", () => {
    const entries: ChatEntry[] = [{ id: "1", kind: "system", message: "游戏开始。" }];
    const { rerender } = render(<ChatHistory entries={entries} />);

    rerender(
      <ChatHistory
        entries={[
          ...entries,
          { id: "2", kind: "speech", message: "我先听后置位。", speaker: "4号玩家" },
        ]}
      />,
    );

    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });
});
