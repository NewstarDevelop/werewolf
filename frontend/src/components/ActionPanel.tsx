import { useCallback, useEffect, useMemo, useState } from "react";

import {
  actionRuleHint,
  actionTypeCopy,
  getIdleCopy,
  speechPlaceholder,
  submitActionCopy,
  type ActionCopy,
} from "../copy";
import { useKeyboard } from "../hooks/useKeyboard";
import type { RequireInputEnvelope, SubmitActionPayload } from "../types/ws";

type PendingAction = RequireInputEnvelope["data"] | null;
type WitchActionType = "WITCH_SAVE" | "WITCH_POISON" | "PASS";
type TargetSelection = number | "PASS" | null;

interface ActionPanelProps {
  request: PendingAction;
  onSubmit: (payload: SubmitActionPayload) => void;
}

const CONFIRM_RESET_MS = 4000;

function isTargetedAction(actionType: RequireInputEnvelope["data"]["action_type"]) {
  return actionType !== "SPEAK" && actionType !== "WITCH_ACTION";
}

function resolveCopy(
  request: PendingAction,
  witchChoice: WitchActionType | null,
): ActionCopy {
  if (!request) {
    return getIdleCopy();
  }
  if (request.action_type === "WITCH_ACTION" && witchChoice) {
    return submitActionCopy[witchChoice];
  }
  return actionTypeCopy[request.action_type];
}

export function ActionPanel({ request, onSubmit }: ActionPanelProps) {
  const [speechText, setSpeechText] = useState("");
  const [selectedTarget, setSelectedTarget] = useState<TargetSelection>(null);
  const [selectedWitchAction, setSelectedWitchAction] = useState<WitchActionType | null>(null);
  const [confirmingDanger, setConfirmingDanger] = useState(false);

  const canSubmitSpeech = speechText.trim().length > 0;
  const canSubmitTarget = typeof selectedTarget === "number";
  const canSubmitVote = selectedTarget === "PASS" || canSubmitTarget;
  const canSubmitWitchAction =
    selectedWitchAction === "WITCH_SAVE"
    || selectedWitchAction === "PASS"
    || (selectedWitchAction === "WITCH_POISON" && canSubmitTarget);

  const copy = useMemo(
    () => resolveCopy(request, selectedWitchAction),
    [request, selectedWitchAction],
  );

  // Reset confirmation when the request or selection changes.
  useEffect(() => {
    setConfirmingDanger(false);
  }, [request, selectedTarget, selectedWitchAction]);

  // Auto-release confirmation after a pause so a stale arm never fires.
  useEffect(() => {
    if (!confirmingDanger) return undefined;
    const timer = window.setTimeout(() => {
      setConfirmingDanger(false);
    }, CONFIRM_RESET_MS);
    return () => window.clearTimeout(timer);
  }, [confirmingDanger]);

  const resetSelections = useCallback(() => {
    setSelectedTarget(null);
    setSelectedWitchAction(null);
    setConfirmingDanger(false);
  }, []);

  const handleSubmit = useCallback(() => {
    if (!request) return;

    const canSubmit =
      request.action_type === "SPEAK"
        ? canSubmitSpeech
        : request.action_type === "WITCH_ACTION"
          ? canSubmitWitchAction
          : request.action_type === "VOTE"
            ? canSubmitVote
            : canSubmitTarget;
    if (!canSubmit) return;

    const isDanger = copy.tone === "danger";
    if (isDanger && !confirmingDanger) {
      setConfirmingDanger(true);
      return;
    }

    if (request.action_type === "SPEAK") {
      onSubmit({ action_type: "SPEAK", text: speechText.trim() });
      setSpeechText("");
      setConfirmingDanger(false);
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

    if (!canSubmitTarget) return;
    onSubmit({
      action_type: request.action_type,
      target: selectedTarget as number,
    });
    resetSelections();
  }, [
    request,
    speechText,
    selectedTarget,
    selectedWitchAction,
    canSubmitSpeech,
    canSubmitTarget,
    canSubmitVote,
    canSubmitWitchAction,
    copy.tone,
    confirmingDanger,
    onSubmit,
    resetSelections,
  ]);

  const keyboardHandler = useCallback(
    (event: KeyboardEvent) => {
      if (!request) return;

      if (event.key === "Escape") {
        if (confirmingDanger) setConfirmingDanger(false);
        else resetSelections();
        return;
      }

      if (event.key === "Enter" && !confirmingDanger) {
        // Let focused buttons handle their own Enter; only fire submit when
        // nothing actionable is focused and a submit is legal.
        return;
      }

      if (/^[1-9]$/.test(event.key) && isTargetedAction(request.action_type)) {
        const seatId = Number(event.key);
        if (request.allowed_targets.includes(seatId)) {
          event.preventDefault();
          setSelectedTarget(seatId);
        }
      }
    },
    [request, confirmingDanger, resetSelections],
  );

  useKeyboard(keyboardHandler, request !== null);

  const submitDisabled =
    !request
      ? true
      : request.action_type === "SPEAK"
        ? !canSubmitSpeech
        : request.action_type === "WITCH_ACTION"
          ? !canSubmitWitchAction
          : request.action_type === "VOTE"
            ? !canSubmitVote
            : !canSubmitTarget;

  const submitLabel = confirmingDanger
    ? `再按一次 · ${copy.submitLabel}`
    : copy.submitLabel;

  const submitClasses = [
    "action-submit",
    copy.tone === "danger" ? "danger" : "",
    confirmingDanger ? "is-confirming" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className="action-panel" aria-labelledby="action-panel-title">
      <header className="panel-header">
        <h2 id="action-panel-title">操作面板</h2>
      </header>

      <div className="action-shell">
        <div className="action-status-bar">
          <span className="action-status-label">当前</span>
          <strong>{copy.title}</strong>
        </div>

        {!request ? (
          <div className="action-idle">
            <strong>{copy.heading}</strong>
            <p>{copy.instruction}</p>
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
            {actionRuleHint[request.action_type] ? (
              <p className="action-rule">{actionRuleHint[request.action_type]}</p>
            ) : null}

            {request.action_type === "SPEAK" ? (
              <label className="speech-form">
                <span>{copy.heading}</span>
                <textarea
                  rows={4}
                  value={speechText}
                  maxLength={200}
                  placeholder={speechPlaceholder}
                  onChange={(event) => setSpeechText(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      (event.ctrlKey || event.metaKey)
                      && event.key === "Enter"
                      && canSubmitSpeech
                    ) {
                      event.preventDefault();
                      handleSubmit();
                    }
                  }}
                />
                <small>
                  <span aria-live="polite">{speechText.trim().length}/200</span>
                  <span className="hint-key">Ctrl/⌘ + Enter 发送</span>
                </small>
              </label>
            ) : null}

            {request.action_type === "WITCH_ACTION" ? (
              <div
                className="target-grid target-grid--triad"
                role="group"
                aria-label="女巫行动"
              >
                <button
                  type="button"
                  className={selectedWitchAction === "WITCH_SAVE" ? "target-button is-selected" : "target-button"}
                  aria-pressed={selectedWitchAction === "WITCH_SAVE"}
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
                  aria-pressed={selectedWitchAction === "WITCH_POISON"}
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
                  aria-pressed={selectedWitchAction === "PASS"}
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
              <div className="target-grid" role="group" aria-label="毒药目标">
                {request.allowed_targets.map((target) => (
                  <button
                    key={target}
                    type="button"
                    data-seat={target}
                    className={target === selectedTarget ? "target-button is-selected danger" : "target-button danger"}
                    aria-pressed={target === selectedTarget}
                    onClick={() => setSelectedTarget(target)}
                  >
                    {target}号
                  </button>
                ))}
              </div>
            ) : null}

            {request.action_type === "VOTE" ? (
              <div className="target-grid target-grid--single" role="group" aria-label="投票操作">
                <button
                  type="button"
                  className={selectedTarget === "PASS" ? "target-button is-selected" : "target-button"}
                  aria-pressed={selectedTarget === "PASS"}
                  onClick={() => setSelectedTarget("PASS")}
                >
                  弃票
                </button>
              </div>
            ) : null}

            {isTargetedAction(request.action_type) ? (
              <div className="target-grid" role="group" aria-label="合法目标">
                {request.allowed_targets.map((target) => (
                  <button
                    key={target}
                    type="button"
                    data-seat={target}
                    className={
                      (target === selectedTarget ? "target-button is-selected" : "target-button")
                      + (copy.tone === "danger" ? " danger" : "")
                    }
                    aria-pressed={target === selectedTarget}
                    onClick={() => setSelectedTarget(target)}
                  >
                    {target}号
                  </button>
                ))}
              </div>
            ) : null}

            <button
              type="button"
              className={submitClasses}
              onClick={handleSubmit}
              disabled={submitDisabled}
              aria-live="polite"
            >
              {submitLabel}
            </button>

            {copy.tone === "danger" && !submitDisabled ? (
              <p className="action-hint">
                {confirmingDanger
                  ? "再次按下以落定；按 Esc 取消。"
                  : "此举关乎生死，按下后需再按一次确认。"}
              </p>
            ) : null}

            {isTargetedAction(request.action_type) ? (
              <p className="action-hint action-hint--muted">数字键 1–9 可快速挑选座位。</p>
            ) : null}
          </>
        ) : null}
      </div>
    </section>
  );
}
