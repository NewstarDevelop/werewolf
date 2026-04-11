import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActionPanel } from "./ActionPanel";

describe("ActionPanel", () => {
  it("renders waiting state when no input is required", () => {
    render(<ActionPanel request={null} onSubmit={vi.fn()} />);

    expect(screen.getByText("等待中")).toBeInTheDocument();
  });

  it("submits speech payload", () => {
    const onSubmit = vi.fn();
    render(
      <ActionPanel
        request={{
          action_type: "SPEAK",
          prompt: "请开始发言",
          allowed_targets: [],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("输入你的发言..."), {
      target: { value: "我先听后置位。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认提交" }));

    expect(onSubmit).toHaveBeenCalledWith({
      action_type: "SPEAK",
      text: "我先听后置位。",
    });
  });

  it("submits targeted payload with selected seat", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          action_type: "VOTE",
          prompt: "请选择投票目标",
          allowed_targets: [2, 4, 7],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: "4号" }));
    fireEvent.click(within(view.container).getByRole("button", { name: "确认提交" }));

    expect(onSubmit).toHaveBeenCalledWith({
      action_type: "VOTE",
      target: 4,
    });
  });

  it("maps witch action to save, poison and pass payloads", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          action_type: "WITCH_ACTION",
          prompt: "请选择女巫行动",
          allowed_targets: [2, 5],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: "救人" }));
    fireEvent.click(within(view.container).getByRole("button", { name: "确认提交" }));
    expect(onSubmit).toHaveBeenLastCalledWith({ action_type: "WITCH_SAVE" });

    fireEvent.click(within(view.container).getByRole("button", { name: "毒人" }));
    fireEvent.click(within(view.container).getByRole("button", { name: "5号" }));
    fireEvent.click(within(view.container).getByRole("button", { name: "确认提交" }));
    expect(onSubmit).toHaveBeenLastCalledWith({
      action_type: "WITCH_POISON",
      target: 5,
    });

    fireEvent.click(within(view.container).getByRole("button", { name: "跳过" }));
    fireEvent.click(within(view.container).getByRole("button", { name: "确认提交" }));
    expect(onSubmit).toHaveBeenLastCalledWith({ action_type: "PASS" });
  });
});
