import { useCallback, useEffect, useRef, useState } from "react";

import { ActionPanel } from "./components/ActionPanel";
import { ChatHistory, type ChatEntry } from "./components/ChatHistory";
import { PlayerList, type PlayerListItem } from "./components/PlayerList";
import { RoleGuide } from "./components/RoleGuide";
import {
  connectionPhaseCopy,
  formatSeat,
  identityStateCopy,
  narratorSpeaker,
  toRoleLabel,
} from "./copy";
import {
  createGameSocketUrl,
  GAME_OVER_CLOSE_CODE,
  getReconnectDelayMs,
  type ConnectionPhase,
  type ServerEnvelope,
} from "./ws/client";
import type { GameOverEnvelope, RequireInputEnvelope, SubmitActionPayload } from "./types/ws";

function createInitialPlayers(): PlayerListItem[] {
  return Array.from({ length: 9 }, (_, index) => ({
    seatId: index + 1,
    isAlive: true,
    isHuman: index === 0,
    roleLabel: index === 0 ? identityStateCopy.unknownRole : undefined,
    isThinking: false,
  }));
}

function applyThinkingState(players: PlayerListItem[], seatId: number, isThinking: boolean) {
  return players.map((player) =>
    player.seatId === seatId ? { ...player, isThinking } : player,
  );
}

function applyIdentityMessage(players: PlayerListItem[], message: string) {
  const identityMatch = message.match(/你的座位号是\s*(\d+)\s*号，身份是\s*([A-Z_]+)\s*。?/);

  if (!identityMatch) {
    return players;
  }

  const humanSeat = Number(identityMatch[1]);
  const humanRoleCode = identityMatch[2];
  const humanRole = toRoleLabel(humanRoleCode) ?? humanRoleCode;
  return players.map((player) => {
    const isHuman = player.seatId === humanSeat;
    return {
      ...player,
      isHuman,
      roleLabel: isHuman ? humanRole : undefined,
      roleCode: isHuman ? humanRoleCode : undefined,
    };
  });
}

function applySystemMessage(players: PlayerListItem[], message: string) {
  let nextPlayers = applyIdentityMessage(players, message);

  const directDeathSeats = [...message.matchAll(/(\d+)号(?:玩家)?(?:被放逐出局|死亡)/g)].map((match) => Number(match[1]));
  const nightlyDeathAnnouncement = message.match(/昨夜死亡的是\s*([^。]+)/);
  const announcedNightSeats = nightlyDeathAnnouncement
    ? [...nightlyDeathAnnouncement[1].matchAll(/(\d+)号/g)].map((match) => Number(match[1]))
    : [];
  const hunterShotSeat = message.match(/猎人开枪带走了\s*(\d+)号玩家/);
  const hunterShotDeaths = hunterShotSeat ? [Number(hunterShotSeat[1])] : [];

  const deadSeats = new Set([...directDeathSeats, ...announcedNightSeats, ...hunterShotDeaths]);
  if (deadSeats.size > 0) {
    nextPlayers = nextPlayers.map((player) =>
      deadSeats.has(player.seatId) ? { ...player, isAlive: false, isThinking: false } : player,
    );
  }

  return nextPlayers;
}

function applyPublicChatMessage(players: PlayerListItem[], message: string) {
  return applySystemMessage(players, message);
}

function applyGameOver(players: PlayerListItem[], payload: GameOverEnvelope["data"]) {
  return players.map((player) => {
    const revealedCode = payload.revealed_roles[player.seatId];
    return {
      ...player,
      isThinking: false,
      roleCode: revealedCode ?? player.roleCode,
      roleLabel: revealedCode
        ? (toRoleLabel(revealedCode) ?? revealedCode)
        : player.roleLabel,
    };
  });
}

function buildChatEntry(payload: ServerEnvelope): ChatEntry | null {
  if (payload.type === "SYSTEM_MSG") {
    return {
      id: `system-${crypto.randomUUID()}`,
      kind: "system",
      message: payload.data.message,
    };
  }

  if (payload.type === "CHAT_UPDATE") {
    const publicSpeechMatch = payload.data.visibility === "public"
      ? payload.data.message.match(/^(\d+)号发言[:：]/)
      : null;

    return {
      id: `chat-${crypto.randomUUID()}`,
      kind: payload.data.visibility === "private"
        ? "private"
        : publicSpeechMatch
          ? "speech"
          : "system",
      message: payload.data.message,
      speaker: payload.data.visibility === "private"
        ? payload.data.speaker ?? "你的视角"
        : publicSpeechMatch
          ? formatSeat(Number(publicSpeechMatch[1]))
          : payload.data.speaker ?? narratorSpeaker,
    };
  }

  if (payload.type === "GAME_OVER") {
    return {
      id: `game-over-${crypto.randomUUID()}`,
      kind: "system",
      message: payload.data.summary,
      speaker: narratorSpeaker,
    };
  }

  return null;
}

function findLatestOutcome(entries: ChatEntry[]) {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (entries[index]?.id.startsWith("game-over-")) {
      return entries[index];
    }
  }
  return null;
}

export function App() {
  const [phase, setPhase] = useState<ConnectionPhase>("idle");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [players, setPlayers] = useState<PlayerListItem[]>(() => createInitialPlayers());
  const [pendingAction, setPendingAction] = useState<RequireInputEnvelope["data"] | null>(null);
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const [isTerminal, setIsTerminal] = useState(false);
  const [reconnectPending, setReconnectPending] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
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
    setEntries([]);
    setPlayers(createInitialPlayers());
    setPendingAction(null);
    setIsTerminal(false);
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

      const chatEntry = buildChatEntry(payload);
      if (chatEntry) {
        setEntries((current) => [...current, chatEntry]);
      }
      if (payload.type === "SYSTEM_MSG") {
        setPlayers((current) => applySystemMessage(current, payload.data.message));
      }
      if (payload.type === "CHAT_UPDATE" && payload.data.visibility === "private") {
        setPlayers((current) => applyIdentityMessage(current, payload.data.message));
      }
      if (payload.type === "CHAT_UPDATE" && payload.data.visibility === "public") {
        setPlayers((current) => applyPublicChatMessage(current, payload.data.message));
      }
      if (payload.type === "AI_THINKING") {
        setPlayers((current) =>
          applyThinkingState(current, payload.data.seat_id, payload.data.is_thinking),
        );
      }
      if (payload.type === "REQUIRE_INPUT") {
        setPendingAction(payload.data);
      }
      if (payload.type === "GAME_OVER") {
        shouldReconnectRef.current = false;
        setIsTerminal(true);
        setPlayers((current) => applyGameOver(current, payload.data));
        setPendingAction(null);
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
      setPendingAction(null);
      if (event?.code === GAME_OVER_CLOSE_CODE) {
        setIsTerminal(true);
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
    setPendingAction(null);
  }

  return (
    <main className="app-shell" data-connection-phase={phase}>
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
