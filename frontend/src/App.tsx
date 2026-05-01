import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ActionPanel } from "./components/ActionPanel";
import { ChatHistory } from "./components/ChatHistory";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { PlayerList } from "./components/PlayerList";
import { RoleGuide } from "./components/RoleGuide";
import {
  connectionPhaseCopy,
  formatSeat,
  formatSeatList,
  gamePhaseCopy,
  identityStateCopy,
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

function formatPhaseTitle(dayCount: number, phase: string | null): string {
  if (!phase) {
    return "战局未定";
  }
  const phaseLabel = gamePhaseCopy[phase] ?? "局中";
  return `第 ${dayCount} 日 · ${phaseLabel}`;
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
  } = gameState;
  const humanPlayer = players.find((player) => player.isHuman) ?? null;
  const latestOutcome = findLatestOutcome(entries);
  const spotlightText = pendingAction
    ? "轮到你落子"
    : latestOutcome
      ? "帷幕落下"
      : phase === "open"
        ? "桌上正在推演"
        : "等候入席";

  const connectionLabel = isTerminal
    ? "本局已散场"
    : reconnectPending
      ? "连接已断，正在接续"
      : connectionPhaseCopy[phase];

  const canManualReconnect = !isTerminal
    && (phase === "closed" || phase === "error");

  const battleSignal: BattleSignal = latestOutcome
    ? {
        title: latestOutcome.message,
        detail: "一局终章，身份尽数揭示。",
        tone: "terminal",
      }
    : pendingAction
      ? {
          title: "轮到你落子",
          detail: "轮到你了，下方落下你的决定。",
          tone: "danger",
        }
      : lastVoteResult
        ? {
            title: lastVoteResult.banishedSeat === null ? "票归无声" : "票落成局",
            detail: `刚刚开票：${lastVoteResult.summary}`,
            tone: lastVoteResult.banishedSeat === null ? "muted" : "danger",
          }
        : lastDeathReveal
          ? {
              title: lastDeathReveal.deadSeats.length > 0 ? "昨夜有名" : "平安夜",
              detail: lastDeathReveal.deadSeats.length > 0
                ? `${formatSeatList(lastDeathReveal.deadSeats)} 已成墓碑${
                    lastDeathReveal.eligibleLastWords.length > 0
                      ? `，${formatSeatList(lastDeathReveal.eligibleLastWords)} 尚有遗言。`
                      : "。"
                  }`
                : "天亮之后，桌上无人倒下。",
              tone: lastDeathReveal.deadSeats.length > 0 ? "danger" : "muted",
            }
          : {
              title: currentPhase ? formatPhaseTitle(dayCount, currentPhase) : spotlightText,
              detail: currentPhase
                ? "桌上仍在推演，消息会持续涌入。"
                : "等候第一条局内消息落下。",
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

  useEffect(() => {
    let disposed = false;
    shouldReconnectRef.current = true;
    dispatchGameState({ type: "reset" });
    setReconnectPending(false);
    setPhase("connecting");

    const socket = new WebSocket(createGameSocketUrl(window.location));
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

    socket.send(
      JSON.stringify({
        type: "SUBMIT_ACTION",
        data: payload,
      }),
    );
    dispatchGameState({ type: "clear-pending-action" });
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
            <h1>狼人杀对局面板</h1>
            <div className="app-header__actions">
              {humanPlayer ? (
                <span className="identity-badge">
                  <span className="identity-badge__seat">
                    {formatSeat(humanPlayer.seatId)}
                  </span>
                  <span className="identity-badge__role">
                    {humanPlayer.roleLabel ?? identityStateCopy.unknownRole}
                  </span>
                  <span className="identity-badge__state">
                    {humanPlayer.isAlive === false ? identityStateCopy.dead : identityStateCopy.alive}
                  </span>
                  <RoleGuide roleCode={humanPlayer.roleCode} />
                </span>
              ) : null}
              <button
                type="button"
                className="theme-toggle"
                onClick={handleToggleTheme}
                aria-label={theme === "light" ? "切换至暗色主题" : "切换至亮色主题"}
              >
                {theme === "light" ? "暗" : "亮"}
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
                  立即重连
                </button>
              ) : null}
            </p>
          </header>

          <section
            className={`battle-signal is-${battleSignal.tone}`}
            aria-label={latestOutcome ? "终局提示" : "战局提示"}
          >
            <strong>{battleSignal.title}</strong>
            <span>{battleSignal.detail}</span>
          </section>

          <PlayerList players={players} />

          <ChatHistory entries={entries} />

          <ActionPanel
            key={connectionAttempt}
            request={pendingAction}
            onSubmit={handleSubmitAction}
          />
        </div>
      </main>
    </ErrorBoundary>
  );
}
