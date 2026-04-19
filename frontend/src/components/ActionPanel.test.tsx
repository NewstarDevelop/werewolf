import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActionPanel } from "./ActionPanel";
import { getIdleCopy, speechPlaceholder, submitActionCopy } from "../copy";

describe("ActionPanel", () => {
  it("renders waiting state when no input is required", () => {
    render(<ActionPanel request={null} onSubmit={vi.fn()} />);

    expect(screen.getByText(getIdleCopy().heading)).toBeInTheDocument();
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

    fireEvent.change(screen.getByPlaceholderText(speechPlaceholder), {
      target: { value: "我先听后置位。" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: submitActionCopy.SPEAK.submitLabel }),
    );

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
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.VOTE.submitLabel,
      }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      action_type: "VOTE",
      target: 4,
    });
  });

  it("submits hunter shoot payload with selected seat", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          action_type: "HUNTER_SHOOT",
          prompt: "请选择开枪目标",
          allowed_targets: [2, 5],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: "5号" }));
    // HUNTER_SHOOT is destructive → first click arms, second click fires.
    const submit = within(view.container).getByRole("button", {
      name: submitActionCopy.HUNTER_SHOOT.submitLabel,
    });
    fireEvent.click(submit);
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.click(
      within(view.container).getByRole("button", {
        name: `再按一次 · ${submitActionCopy.HUNTER_SHOOT.submitLabel}`,
      }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      action_type: "HUNTER_SHOOT",
      target: 5,
    });
  });

  it("submits vote pass payload", () => {
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

    fireEvent.click(within(view.container).getByRole("button", { name: "弃票" }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.VOTE.submitLabel,
      }),
    );

    expect(onSubmit).toHaveBeenCalledWith({ action_type: "PASS" });
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
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.WITCH_SAVE.submitLabel,
      }),
    );
    expect(onSubmit).toHaveBeenLastCalledWith({ action_type: "WITCH_SAVE" });

    fireEvent.click(within(view.container).getByRole("button", { name: "毒人" }));
    fireEvent.click(within(view.container).getByRole("button", { name: "5号" }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.WITCH_POISON.submitLabel,
      }),
    );
    // WITCH_POISON is destructive → second click commits.
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: `再按一次 · ${submitActionCopy.WITCH_POISON.submitLabel}`,
      }),
    );
    expect(onSubmit).toHaveBeenLastCalledWith({
      action_type: "WITCH_POISON",
      target: 5,
    });

    fireEvent.click(within(view.container).getByRole("button", { name: "跳过" }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.PASS.submitLabel,
      }),
    );
    expect(onSubmit).toHaveBeenLastCalledWith({ action_type: "PASS" });
  });

  it("arms destructive actions on first click and commits on second", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          action_type: "WOLF_KILL",
          prompt: "请选择狼刀目标",
          allowed_targets: [3, 6],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: "6号" }));

    const submit = within(view.container).getByRole("button", {
      name: submitActionCopy.WOLF_KILL.submitLabel,
    });
    fireEvent.click(submit);
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.click(
      within(view.container).getByRole("button", {
        name: `再按一次 · ${submitActionCopy.WOLF_KILL.submitLabel}`,
      }),
    );
    expect(onSubmit).toHaveBeenCalledWith({
      action_type: "WOLF_KILL",
      target: 6,
    });
  });

  it("cancels destructive confirmation on Escape", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          action_type: "WOLF_KILL",
          prompt: "请选择狼刀目标",
          allowed_targets: [3, 6],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: "6号" }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.WOLF_KILL.submitLabel,
      }),
    );
    fireEvent.keyDown(document.body, { key: "Escape" });

    expect(
      within(view.container).queryByRole("button", {
        name: `再按一次 · ${submitActionCopy.WOLF_KILL.submitLabel}`,
      }),
    ).toBeNull();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("selects seats via 1-9 keyboard shortcut for targeted actions", () => {
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

    fireEvent.keyDown(document.body, { key: "4" });
    const button = within(view.container).getByRole("button", { name: "4号" });
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });
});
