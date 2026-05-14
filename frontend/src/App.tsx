import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ActionPanel } from "./components/ActionPanel";
import { ChatHistory } from "./components/ChatHistory";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { PlayerList } from "./components/PlayerList";
import { RoleGuide } from "./components/RoleGuide";
import { SettlementReview } from "./components/SettlementReview";
import { VoteBoard } from "./components/VoteBoard";
import {
  aiPaceOptions,
  connectionPhaseCopy,
  formatGameMessage,
  formatSeat,
  formatPhaseTitle,
  identityStateCopy,
  roleQuickTips,
  uiCopy,
  type AIPace,
} from "./copy";
import {
  createInitialGameState,
  findLatestOutcome,
  gameReducer,
} from "./state/gameState";
import { type Theme, applyTheme, persistTheme, resolveInitialTheme, toggleTheme } from "./theme";
import type { SubmitActionPayload } from "./types/ws";
import {
  createGameSocketUrl,
  GAME_OVER_CLOSE_CODE,
  getReconnectDelayMs,
  type ConnectionPhase,
  type ServerEnvelope,
} from "./ws/client";

const VALID_ENVELOPE_TYPES = new Set([
  "SYSTEM_MSG", "CHAT_UPDATE", "AI_THINKING", "PLAYER_STATE_PATCH",
  "PHASE_CHANGED", "DEATH_REVEALED", "VOTE_RESOLVED", "REQUIRE_INPUT", "GAME_OVER",
]);
const AI_PACE_STORAGE_KEY = "werewolf.aiPace";

function resolveInitialAIPace(): AIPace {
  const stored = window.localStorage.getItem(AI_PACE_STORAGE_KEY);
  return aiPaceOptions.some((option) => option.value === stored)
    ? stored as AIPace
    : "normal";
}

function aiDelayMsFor(pace: AIPace): number {
  return aiPaceOptions.find((option) => option.value === pace)?.delayMs ?? 700;
}

function persistAIPace(pace: AIPace): void {
  window.localStorage.setItem(AI_PACE_STORAGE_KEY, pace);
}

interface BattleSignal {
  title: string;
  detail: string;
  tone: "muted" | "danger" | "terminal";
}

export function App() {
  const [phase, setPhase] = useState<ConnectionPhase>("idle");
  const [gameState, dispatchGameState] = useReducer(gameReducer, undefined, createInitialGameState);
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const [reconnectPending, setReconnectPending] = useState(false);
  const [theme, setTheme] = useState<Theme>(resolveInitialTheme);
  const [aiPace, setAiPace] = useState<AIPace>(resolveInitialAIPace);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const {
    entries,
    players,
    pendingAction,
    isTerminal,
    currentPhase,
    dayCount,
    lastDeathReveal,
    lastVoteResult,
    lastNightActionFeedback,
    settlementReview,
  } = gameState;
  const humanPlayer = players.find((player) => player.isHuman) ?? null;
  const humanRoleTip = humanPlayer?.roleCode ? roleQuickTips[humanPlayer.roleCode] : undefined;
  const latestOutcome = findLatestOutcome(entries);
  const spotlightText = pendingAction
    ? uiCopy.app.spotlight.pending
    : latestOutcome
      ? uiCopy.app.spotlight.terminal
      : phase === "open"
        ? uiCopy.app.spotlight.open
        : uiCopy.app.spotlight.idle;

  const connectionLabel = isTerminal
    ? uiCopy.app.connection.terminal
    : reconnectPending
      ? uiCopy.app.connection.reconnecting
      : connectionPhaseCopy[phase];

  const canManualReconnect = !isTerminal
    && (phase === "closed" || phase === "error");

  const battleSignal: BattleSignal = latestOutcome
    ? {
        title: formatGameMessage(latestOutcome.message),
        detail: uiCopy.app.battle.terminalDetail,
        tone: "terminal",
      }
    : pendingAction
      ? {
          title: uiCopy.app.battle.pendingTitle,
          detail: uiCopy.app.battle.pendingDetail,
          tone: "danger",
        }
      : lastVoteResult
        ? {
            title: lastVoteResult.banishedSeat === null
              ? uiCopy.app.battle.voteMutedTitle
              : uiCopy.app.battle.voteDangerTitle,
            detail: uiCopy.app.battle.formatVoteDetail(lastVoteResult.summary),
            tone: lastVoteResult.banishedSeat === null ? "muted" : "danger",
          }
        : lastDeathReveal
          ? {
              title: lastDeathReveal.deadSeats.length > 0
                ? uiCopy.app.battle.deathTitle
                : uiCopy.app.battle.peaceTitle,
              detail: lastDeathReveal.deadSeats.length > 0
                ? uiCopy.app.battle.formatDeathDetail(
                    lastDeathReveal.deadSeats,
                    lastDeathReveal.eligibleLastWords,
                  )
                : uiCopy.app.battle.peaceDetail,
              tone: lastDeathReveal.deadSeats.length > 0 ? "danger" : "muted",
            }
          : {
              title: currentPhase ? formatPhaseTitle(dayCount, currentPhase) : spotlightText,
              detail: currentPhase
                ? uiCopy.app.battle.phaseDetail
                : uiCopy.app.battle.idleDetail,
              tone: "muted",
            };

  const handleManualReconnect = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    setReconnectPending(false);
    shouldReconnectRef.current = true;
    setConnectionAttempt((current) => current + 1);
  }, []);

  const handleNewGame = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    shouldReconnectRef.current = false;
    socketRef.current?.close();
    socketRef.current = null;
    dispatchGameState({ type: "reset" });
    setReconnectPending(false);
    setPhase("connecting");
    shouldReconnectRef.current = true;
    setConnectionAttempt((current) => current + 1);
  }, []);

  function handleAIPaceChange(nextPace: AIPace) {
    persistAIPace(nextPace);
    setAiPace(nextPace);
  }

  useEffect(() => {
    let disposed = false;
    shouldReconnectRef.current = true;
    dispatchGameState({ type: "reset" });
    setReconnectPending(false);
    setPhase("connecting");

    const socket = new WebSocket(
      createGameSocketUrl(window.location, { aiDelayMs: aiDelayMsFor(aiPace) }),
    );
    socketRef.current = socket;

    function scheduleReconnect() {
      if (disposed || reconnectTimerRef.current !== null) {
        return;
      }

      setReconnectPending(true);
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        if (disposed) {
          return;
        }
        setConnectionAttempt((current) => current + 1);
      }, getReconnectDelayMs());
    }

    socket.addEventListener("open", () => {
      setPhase("open");
      setReconnectPending(false);
    });

    socket.addEventListener("message", (event) => {
      let raw: unknown;
      try {
        raw = JSON.parse(event.data);
      } catch {
        console.warn("Received non-JSON message from server; ignoring.");
        return;
      }

      if (
        !raw
        || typeof raw !== "object"
        || !("type" in raw)
        || typeof (raw as Record<string, unknown>).type !== "string"
        || !VALID_ENVELOPE_TYPES.has((raw as Record<string, unknown>).type as string)
      ) {
        console.warn("Received unknown envelope type from server; ignoring.", raw);
        return;
      }

      const payload = raw as ServerEnvelope;
      dispatchGameState({ type: "server-envelope", envelope: payload });
      if (payload.type === "GAME_OVER") {
        shouldReconnectRef.current = false;
      }
    });

    socket.addEventListener("error", () => {
      setPhase("error");
    });

    socket.addEventListener("close", (event) => {
      if (disposed) {
        return;
      }

      if (socketRef.current === socket) {
        socketRef.current = null;
      }
      setPhase("closed");
      dispatchGameState({ type: "clear-pending-action" });
      if (event?.code === GAME_OVER_CLOSE_CODE) {
        dispatchGameState({ type: "mark-terminal" });
        return;
      }
      if (!shouldReconnectRef.current) {
        return;
      }
      scheduleReconnect();
    });

    return () => {
      disposed = true;
      socket.close();
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [connectionAttempt]);

  function handleSubmitAction(payload: SubmitActionPayload) {
    const socket = socketRef.current;
    if (!socket) {
      return;
    }
    const requestId = payload.request_id ?? pendingAction?.request_id;
    const data = requestId
      ? { ...payload, request_id: requestId }
      : payload;

    socket.send(
      JSON.stringify({
        type: "SUBMIT_ACTION",
        data,
      }),
    );
  }

  function handleToggleTheme() {
    const next = toggleTheme(theme);
    applyTheme(next);
    persistTheme(next);
    setTheme(next);
  }

  return (
    <ErrorBoundary>
      <main
        className="app-shell"
        data-connection-phase={phase}
        data-game-phase={currentPhase ?? "UNKNOWN"}
      >
        <div className="app-frame">
          <header className="app-header">
            <div className="app-header__actions">
              <button
                type="button"
                className="new-game-button"
                onClick={handleNewGame}
              >
                {uiCopy.app.newGame}
              </button>
              <div className="pace-control" role="group" aria-label={uiCopy.app.aiPaceAria}>
                {aiPaceOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={option.value === aiPace ? "pace-control__button is-active" : "pace-control__button"}
                    aria-pressed={option.value === aiPace}
                    onClick={() => handleAIPaceChange(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="theme-toggle"
                onClick={handleToggleTheme}
                aria-label={theme === "light" ? uiCopy.app.themeToDark : uiCopy.app.themeToLight}
              >
                {theme === "light" ? uiCopy.app.themeDarkText : uiCopy.app.themeLightText}
              </button>
            </div>
            <p className="app-status" role="status" aria-live="polite">
              <span
                className={`app-status__phase is-${isTerminal ? "terminal" : phase}`}
              >
                {connectionLabel}
              </span>
              <span className="app-status__sep" aria-hidden="true">·</span>
              <span className="app-status__spotlight">{spotlightText}</span>
              {canManualReconnect ? (
                <button
                  type="button"
                  className="app-status__retry"
                  onClick={handleManualReconnect}
                >
                  {uiCopy.app.reconnectNow}
                </button>
              ) : null}
            </p>
          </header>

          <section
            className={`battle-signal is-${battleSignal.tone}`}
            aria-label={latestOutcome ? uiCopy.app.terminalAria : uiCopy.app.battleAria}
          >
            <strong>{battleSignal.title}</strong>
            <span>{battleSignal.detail}</span>
          </section>

          <PlayerList players={players} />

          <ChatHistory entries={entries} />

          <ActionPanel
            key={connectionAttempt}
            request={pendingAction}
            nightActionFeedback={
              lastNightActionFeedback
                ? formatGameMessage(lastNightActionFeedback.message)
                : null
            }
            identityContent={humanPlayer ? (
              <div className="identity-badge">
                <span className="identity-badge__seat">
                  {formatSeat(humanPlayer.seatId)}
                </span>
                <span className="identity-badge__role">
                  {humanPlayer.roleLabel ?? identityStateCopy.unknownRole}
                </span>
                <span className="identity-badge__state">
                  {humanPlayer.isAlive === false ? identityStateCopy.dead : identityStateCopy.alive}
                </span>
                {humanRoleTip ? (
                  <span className="identity-badge__tip">{humanRoleTip}</span>
                ) : null}
                <RoleGuide roleCode={humanPlayer.roleCode} />
              </div>
            ) : null}
            onSubmit={handleSubmitAction}
          >
            {settlementReview ? (
              <SettlementReview review={settlementReview} />
            ) : lastVoteResult ? (
              <VoteBoard result={lastVoteResult} />
            ) : null}
          </ActionPanel>
        </div>
      </main>
    </ErrorBoundary>
  );
}
