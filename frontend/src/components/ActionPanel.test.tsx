import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActionPanel } from "./ActionPanel";
import { getIdleCopy, speechPlaceholder, submitActionCopy, uiCopy } from "../copy";

describe("ActionPanel", () => {
  it("renders waiting state when no input is required", () => {
    render(<ActionPanel request={null} onSubmit={vi.fn()} />);

    expect(screen.getByText(getIdleCopy().heading)).toBeInTheDocument();
  });

  it("renders supplemental match review content in the panel", () => {
    const view = render(
      <ActionPanel request={null} onSubmit={vi.fn()}>
        <section aria-label="对局回看测试">复盘内容</section>
      </ActionPanel>,
    );

    expect(screen.getByLabelText("对局回看")).toHaveTextContent("复盘内容");
    expect(view.container.querySelector(".action-idle")).toBeNull();
  });

  it("renders identity content inside the panel", () => {
    render(
      <ActionPanel
        request={null}
        identityContent={<span>2号玩家 平民 仍在局内</span>}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("你的身份")).toHaveTextContent("2号玩家 平民 仍在局内");
  });

  it("renders night action feedback inside the panel", () => {
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-wolf",
          action_type: "WOLF_KILL",
          prompt: "请选择狼刀目标",
          allowed_targets: [3, 9],
        }}
        nightActionFeedback="你选择今晚击杀 9号玩家。"
        onSubmit={vi.fn()}
      />,
    );

    const panel = view.container.querySelector(".action-panel");
    expect(panel).not.toBeNull();
    expect(within(panel as HTMLElement).getByLabelText("夜晚行动反馈")).toHaveTextContent("夜晚操作结果");
    expect(within(panel as HTMLElement).getByLabelText("夜晚行动反馈")).toHaveTextContent("你选择今晚击杀 9号玩家。");
  });

  it("submits speech payload", () => {
    const onSubmit = vi.fn();
    render(
      <ActionPanel
        request={{
          request_id: "input-speech",
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

  it("collapses and restores the panel body", () => {
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-collapse",
          action_type: "WOLF_KILL",
          prompt: "请选择狼刀目标",
          allowed_targets: [1, 3, 6],
        }}
        onSubmit={vi.fn()}
      />,
    );

    expect(within(view.container).getByText("请选择狼刀目标")).toBeInTheDocument();

    fireEvent.click(
      within(view.container).getByRole("button", { name: "隐藏操作面板" }),
    );

    expect(within(view.container).queryByText("请选择狼刀目标")).toBeNull();
    expect(
      within(view.container).getByRole("button", { name: "展开操作面板" }),
    ).toBeInTheDocument();

    fireEvent.click(
      within(view.container).getByRole("button", { name: "展开操作面板" }),
    );

    expect(within(view.container).getByText("请选择狼刀目标")).toBeInTheDocument();
  });

  it("submits targeted payload with selected seat", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-vote-target",
          action_type: "VOTE",
          prompt: "请选择投票目标",
          allowed_targets: [2, 4, 7],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: /4号玩家/ }));
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

  it("renders player context in target cards", () => {
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-target-context",
          action_type: "SEER_CHECK",
          prompt: "请选择查验目标",
          allowed_targets: [2, 4],
        }}
        targetSummaries={{
          2: {
            seatId: 2,
            label: "2号玩家",
            roleLabel: "身份未知",
            stateLabel: "存活",
            isAlive: true,
          },
          4: {
            seatId: 4,
            label: "4号玩家",
            roleLabel: "女巫",
            stateLabel: "已出局",
            isAlive: false,
          },
        }}
        onSubmit={vi.fn()}
      />,
    );

    const target = within(view.container).getByRole("button", {
      name: "4号玩家，女巫，已出局",
    });
    expect(target).toHaveTextContent("4");
    expect(target).toHaveTextContent("4号玩家");
    expect(target).toHaveTextContent("女巫");
    expect(target).toHaveTextContent("已出局");
  });

  it("submits hunter shoot payload with selected seat", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-hunter",
          action_type: "HUNTER_SHOOT",
          prompt: "请选择开枪目标",
          allowed_targets: [2, 5],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: /5号玩家/ }));
    // HUNTER_SHOOT is destructive → first click arms, second click fires.
    const submit = within(view.container).getByRole("button", {
      name: submitActionCopy.HUNTER_SHOOT.submitLabel,
    });
    fireEvent.click(submit);
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.click(
      within(view.container).getByRole("button", {
        name: uiCopy.actionPanel.confirmAgain(submitActionCopy.HUNTER_SHOOT.submitLabel),
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
          request_id: "input-vote-pass",
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
          request_id: "input-witch",
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
    fireEvent.click(within(view.container).getByRole("button", { name: /5号玩家/ }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.WITCH_POISON.submitLabel,
      }),
    );
    // WITCH_POISON is destructive → second click commits.
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: uiCopy.actionPanel.confirmAgain(submitActionCopy.WITCH_POISON.submitLabel),
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

  it("hides unavailable witch save action", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-witch-options",
          action_type: "WITCH_ACTION",
          prompt: "请选择女巫行动",
          allowed_targets: [2, 5],
          available_actions: ["WITCH_POISON", "PASS"],
          save_targets: [],
        }}
        onSubmit={onSubmit}
      />,
    );

    expect(within(view.container).queryByRole("button", { name: "救人" })).toBeNull();
    fireEvent.click(within(view.container).getByRole("button", { name: "毒人" }));
    fireEvent.click(within(view.container).getByRole("button", { name: /5号玩家/ }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.WITCH_POISON.submitLabel,
      }),
    );
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: uiCopy.actionPanel.confirmAgain(submitActionCopy.WITCH_POISON.submitLabel),
      }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      action_type: "WITCH_POISON",
      target: 5,
    });
  });

  it("arms destructive actions on first click and commits on second", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-wolf-confirm",
          action_type: "WOLF_KILL",
          prompt: "请选择狼刀目标",
          allowed_targets: [3, 6],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: /6号玩家/ }));

    const submit = within(view.container).getByRole("button", {
      name: submitActionCopy.WOLF_KILL.submitLabel,
    });
    fireEvent.click(submit);
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.click(
      within(view.container).getByRole("button", {
        name: uiCopy.actionPanel.confirmAgain(submitActionCopy.WOLF_KILL.submitLabel),
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
          request_id: "input-wolf-escape",
          action_type: "WOLF_KILL",
          prompt: "请选择狼刀目标",
          allowed_targets: [3, 6],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(within(view.container).getByRole("button", { name: /6号玩家/ }));
    fireEvent.click(
      within(view.container).getByRole("button", {
        name: submitActionCopy.WOLF_KILL.submitLabel,
      }),
    );
    fireEvent.keyDown(document.body, { key: "Escape" });

    expect(
      within(view.container).queryByRole("button", {
        name: uiCopy.actionPanel.confirmAgain(submitActionCopy.WOLF_KILL.submitLabel),
      }),
    ).toBeNull();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("selects seats via 1-9 keyboard shortcut for targeted actions", () => {
    const onSubmit = vi.fn();
    const view = render(
      <ActionPanel
        request={{
          request_id: "input-keyboard",
          action_type: "VOTE",
          prompt: "请选择投票目标",
          allowed_targets: [2, 4, 7],
        }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.keyDown(document.body, { key: "4" });
    const button = within(view.container).getByRole("button", { name: /4号玩家/ });
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });
});
