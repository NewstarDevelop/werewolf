import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatHistory, type ChatEntry } from "./ChatHistory";
import { chatTagCopy } from "../copy";

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

    const view = render(<ChatHistory entries={entries} />);
    const logList = within(view.container).getByLabelText("对局日志列表");

    expect(within(logList).getByText(chatTagCopy.system)).toBeInTheDocument();
    expect(within(logList).getByText(chatTagCopy.private)).toBeInTheDocument();
    expect(within(logList).getByText(chatTagCopy.speech)).toBeInTheDocument();
    expect(within(logList).getByText("2号玩家")).toBeInTheDocument();
  });

  it("filters log rows by kind", () => {
    const entries: ChatEntry[] = [
      { id: "1", kind: "system", message: "天黑请闭眼。" },
      { id: "2", kind: "private", message: "你的查验结果是：5号是狼人。", speaker: "你的视角" },
      { id: "3", kind: "speech", message: "我是预言家。", speaker: "2号玩家" },
    ];

    const view = render(<ChatHistory entries={entries} />);

    fireEvent.click(within(within(view.container).getByLabelText("日志筛选")).getByRole("button", { name: chatTagCopy.speech }));

    const logList = within(view.container).getByLabelText("对局日志列表");
    expect(within(logList).getByText("我是预言家。")).toBeInTheDocument();
    expect(within(logList).queryByText("天黑请闭眼。")).toBeNull();
    expect(within(view.container).getByText("1/3 条")).toBeInTheDocument();
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
