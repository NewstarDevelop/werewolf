import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ActionPanel } from "./components/ActionPanel";
import { ChatHistory } from "./components/ChatHistory";
import { PlayerList } from "./components/PlayerList";
import { RoleGuide } from "./components/RoleGuide";
import {
  connectionPhaseCopy,
  formatSeat,
  identityStateCopy,
} from "./copy";
import {
  createInitialGameState,
  findLatestOutcome,
  gameReducer,
} from "./state/gameState";
import {
  createGameSocketUrl,
  GAME_OVER_CLOSE_CODE,
  getReconnectDelayMs,
  type ConnectionPhase,
  type ServerEnvelope,
} from "./ws/client";
import type { SubmitActionPayload } from "./types/ws";

export function App() {
  const [phase, setPhase] = useState<ConnectionPhase>("idle");
  const [gameState, dispatchGameState] = useReducer(gameReducer, undefined, createInitialGameState);
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const [reconnectPending, setReconnectPending] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const { entries, players, pendingAction, isTerminal, currentPhase } = gameState;
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
      let payload: ServerEnvelope;
      try {
        payload = JSON.parse(event.data) as ServerEnvelope;
      } catch (error) {
        console.warn("Received malformed message from server; ignoring.", error);
        return;
      }

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

  return (
    <main
      className="app-shell"
      data-connection-phase={phase}
      data-game-phase={currentPhase ?? "UNKNOWN"}
    >
      <div className="app-frame">
        <header className="app-header">
          <h1>狼人杀对局面板</h1>
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

        <div className="app-grid">
          <aside className="board-column">
            <section className="identity-card" aria-label="你的身份摘要">
              <p className="identity-kicker">你的席位</p>
              <strong>{humanPlayer ? formatSeat(humanPlayer.seatId) : identityStateCopy.unknownSeat}</strong>
              <p>{humanPlayer?.roleLabel ?? identityStateCopy.unknownRole}</p>
              <span className={`identity-state ${humanPlayer?.isAlive === false ? "is-dead" : "is-alive"}`}>
                {humanPlayer?.isAlive === false ? identityStateCopy.dead : identityStateCopy.alive}
              </span>
              <RoleGuide roleCode={humanPlayer?.roleCode} />
            </section>
            <PlayerList players={players} />
          </aside>

          <section className="log-column">
            <section
              className={`result-banner ${latestOutcome ? "" : "is-muted"}`}
              aria-label={latestOutcome ? "终局提示" : "战局提示"}
            >
              <strong>{latestOutcome ? latestOutcome.message : spotlightText}</strong>
              <span>
                {latestOutcome
                  ? "一局终章，身份尽数揭示。"
                  : pendingAction
                    ? "轮到你了，在右侧落下你的决定。"
                    : "桌上仍在推演，消息会持续涌入中央。"}
              </span>
            </section>
            <ChatHistory entries={entries} />
          </section>

          <aside className="action-column">
            <ActionPanel key={connectionAttempt} request={pendingAction} onSubmit={handleSubmitAction} />
          </aside>
        </div>
      </div>
    </main>
  );
}
