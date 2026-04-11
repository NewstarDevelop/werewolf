import { useMemo, useState } from "react";

import type { RequireInputEnvelope, SubmitActionPayload } from "../types/ws";

type PendingAction = RequireInputEnvelope["data"] | null;

interface ActionPanelProps {
  request: PendingAction;
  onSubmit: (payload: SubmitActionPayload) => void;
}

function isTargetedAction(actionType: RequireInputEnvelope["data"]["action_type"]) {
  return actionType !== "SPEAK";
}

export function ActionPanel({ request, onSubmit }: ActionPanelProps) {
  const [speechText, setSpeechText] = useState("");
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null);

  const canSubmitSpeech = speechText.trim().length > 0;
  const canSubmitTarget = selectedTarget !== null;
  const helperText = useMemo(() => {
    if (!request) {
      return "等待其他玩家行动...";
    }
    if (request.action_type === "SPEAK") {
      return "轮到你发言，提交后将立即回锁。";
    }
    return "请选择一个合法目标并确认提交。";
  }, [request]);

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

    if (!canSubmitTarget) {
      return;
    }
    onSubmit({
      action_type: request.action_type,
      target: selectedTarget,
    });
    setSelectedTarget(null);
  }

  return (
    <section className="action-panel" aria-labelledby="action-panel-title">
      <div className="panel-header">
        <p className="panel-kicker">Action Deck</p>
        <div>
          <h2 id="action-panel-title">操作面板</h2>
          <p className="panel-copy">{helperText}</p>
        </div>
      </div>

      {!request ? (
        <div className="action-idle">
          <strong>等待中</strong>
          <p>收到 `REQUIRE_INPUT` 后，这里会自动切换为对应的发言或目标选择面板。</p>
        </div>
      ) : null}

      {request ? (
        <div className="action-shell">
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
            className="action-submit"
            onClick={handleSubmit}
            disabled={request.action_type === "SPEAK" ? !canSubmitSpeech : !canSubmitTarget}
          >
            确认提交
          </button>
        </div>
      ) : null}
    </section>
  );
}
