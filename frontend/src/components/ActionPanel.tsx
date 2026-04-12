import { useMemo, useState } from "react";

import type { RequireInputEnvelope, SubmitActionPayload } from "../types/ws";

type PendingAction = RequireInputEnvelope["data"] | null;
type WitchActionType = "WITCH_SAVE" | "WITCH_POISON" | "PASS";
type TargetSelection = number | "PASS" | null;

interface ActionPanelProps {
  request: PendingAction;
  onSubmit: (payload: SubmitActionPayload) => void;
}

function isTargetedAction(actionType: RequireInputEnvelope["data"]["action_type"]) {
  return actionType !== "SPEAK" && actionType !== "WITCH_ACTION";
}

export function ActionPanel({ request, onSubmit }: ActionPanelProps) {
  const [speechText, setSpeechText] = useState("");
  const [selectedTarget, setSelectedTarget] = useState<TargetSelection>(null);
  const [selectedWitchAction, setSelectedWitchAction] = useState<WitchActionType | null>(null);

  const canSubmitSpeech = speechText.trim().length > 0;
  const canSubmitTarget = typeof selectedTarget === "number";
  const canSubmitVote = selectedTarget === "PASS" || canSubmitTarget;
  const canSubmitWitchAction =
    selectedWitchAction === "WITCH_SAVE"
    || selectedWitchAction === "PASS"
    || (selectedWitchAction === "WITCH_POISON" && canSubmitTarget);

  const helperText = useMemo(() => {
    if (!request) {
      return "等待其他玩家行动，系统会在需要你决策时立即点亮此处。";
    }
    if (request.action_type === "SPEAK") {
      return "轮到你发言时，这里会切换为发言输入区，提交后立即回锁。";
    }
    if (request.action_type === "WITCH_ACTION") {
      return "你可以在这里选择救人、毒人或直接跳过本回合。";
    }
    if (request.action_type === "VOTE") {
      return "投票阶段支持选择放逐目标，也允许你直接弃票。";
    }
    return "所有可执行目标都在这里聚焦展示，确认后会立刻发往后端。";
  }, [request]);

  function resetSelections() {
    setSelectedTarget(null);
    setSelectedWitchAction(null);
  }

  function handleSubmit() {
    if (!request) {
      return;
    }

    if (request.action_type === "SPEAK") {
      if (!canSubmitSpeech) {
        return;
      }
      onSubmit({
        action_type: "SPEAK",
        text: speechText.trim(),
      });
      setSpeechText("");
      return;
    }

    if (request.action_type === "WITCH_ACTION") {
      if (selectedWitchAction === "WITCH_SAVE") {
        onSubmit({ action_type: "WITCH_SAVE" });
      } else if (selectedWitchAction === "PASS") {
        onSubmit({ action_type: "PASS" });
      } else if (selectedWitchAction === "WITCH_POISON" && canSubmitTarget) {
        onSubmit({
          action_type: "WITCH_POISON",
          target: selectedTarget as number,
        });
      } else {
        return;
      }
      resetSelections();
      return;
    }

    if (request.action_type === "VOTE" && selectedTarget === "PASS") {
      onSubmit({ action_type: "PASS" });
      resetSelections();
      return;
    }

    if (!canSubmitTarget) {
      return;
    }

    onSubmit({
      action_type: request.action_type,
      target: selectedTarget as number,
    });
    resetSelections();
  }

  const actionLabel = request ? request.action_type.replace(/_/g, " ") : "WAITING";

  return (
    <section className="action-panel" aria-labelledby="action-panel-title">
      <div className="panel-header">
        <div>
          <p className="panel-kicker">Directive</p>
          <h2 id="action-panel-title">操作面板</h2>
          <p className="panel-copy">{helperText}</p>
        </div>
      </div>

      <div className="action-shell">
        <div className="action-status-bar">
          <span className="action-status-label">当前指令</span>
          <strong>{actionLabel}</strong>
        </div>

        {!request ? (
          <div className="action-idle">
            <strong>等待中</strong>
            <p>收到 `REQUIRE_INPUT` 后，这里会自动切换为对应的发言或目标选择面板。</p>
            <div className="idle-pulse" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </div>
        ) : null}

        {request ? (
          <>
            <p className="action-prompt">{request.prompt}</p>

            {request.action_type === "SPEAK" ? (
              <label className="speech-form">
                <span>发言内容</span>
                <textarea
                  rows={4}
                  value={speechText}
                  maxLength={200}
                  placeholder="输入你的发言..."
                  onChange={(event) => setSpeechText(event.target.value)}
                />
                <small>{speechText.trim().length}/200</small>
              </label>
            ) : null}

            {request.action_type === "WITCH_ACTION" ? (
              <div className="target-grid target-grid--triad" aria-label="女巫行动列表">
                <button
                  type="button"
                  className={selectedWitchAction === "WITCH_SAVE" ? "target-button is-selected" : "target-button"}
                  onClick={() => {
                    setSelectedWitchAction("WITCH_SAVE");
                    setSelectedTarget(null);
                  }}
                >
                  救人
                </button>
                <button
                  type="button"
                  className={selectedWitchAction === "WITCH_POISON" ? "target-button is-selected danger" : "target-button danger"}
                  onClick={() => {
                    setSelectedWitchAction("WITCH_POISON");
                    setSelectedTarget(null);
                  }}
                >
                  毒人
                </button>
                <button
                  type="button"
                  className={selectedWitchAction === "PASS" ? "target-button is-selected" : "target-button"}
                  onClick={() => {
                    setSelectedWitchAction("PASS");
                    setSelectedTarget(null);
                  }}
                >
                  跳过
                </button>
              </div>
            ) : null}

            {request.action_type === "WITCH_ACTION" && selectedWitchAction === "WITCH_POISON" ? (
              <div className="target-grid" aria-label="女巫毒药目标列表">
                {request.allowed_targets.map((target) => (
                  <button
                    key={target}
                    type="button"
                    className={target === selectedTarget ? "target-button is-selected danger" : "target-button danger"}
                    onClick={() => setSelectedTarget(target)}
                  >
                    {target}号
                  </button>
                ))}
              </div>
            ) : null}

            {request.action_type === "VOTE" ? (
              <div className="target-grid target-grid--single" aria-label="投票操作列表">
                <button
                  type="button"
                  className={selectedTarget === "PASS" ? "target-button is-selected" : "target-button"}
                  onClick={() => setSelectedTarget("PASS")}
                >
                  弃票
                </button>
              </div>
            ) : null}

            {isTargetedAction(request.action_type) ? (
              <div className="target-grid" aria-label="合法目标列表">
                {request.allowed_targets.map((target) => (
                  <button
                    key={target}
                    type="button"
                    className={target === selectedTarget ? "target-button is-selected" : "target-button"}
                    onClick={() => setSelectedTarget(target)}
                  >
                    {target}号
                  </button>
                ))}
              </div>
            ) : null}

            <button
              type="button"
              className={`action-submit ${request.action_type === "WOLF_KILL" || request.action_type === "HUNTER_SHOOT" ? "danger" : ""}`}
              onClick={handleSubmit}
              disabled={
                request.action_type === "SPEAK"
                  ? !canSubmitSpeech
                  : request.action_type === "WITCH_ACTION"
                    ? !canSubmitWitchAction
                    : request.action_type === "VOTE"
                      ? !canSubmitVote
                      : !canSubmitTarget
              }
            >
              确认提交
            </button>
          </>
        ) : null}
      </div>
    </section>
  );
}
