import { useEffect, useRef, useState } from "react";

import { ActionPanel } from "./components/ActionPanel";
import { ChatHistory, type ChatEntry } from "./components/ChatHistory";
import { PlayerList, type PlayerListItem } from "./components/PlayerList";
import {
  createGameSocketUrl,
  GAME_OVER_CLOSE_CODE,
  getReconnectDelayMs,
  type ConnectionPhase,
  type ServerEnvelope,
} from "./ws/client";
import type { GameOverEnvelope, RequireInputEnvelope, SubmitActionPayload } from "./types/ws";

const statusText: Record<ConnectionPhase, string> = {
  idle: "尚未连接",
  connecting: "连接中",
  open: "已连接",
  closed: "已断开",
  error: "连接异常",
};

const roleText: Record<string, string> = {
  VILLAGER: "平民",
  WOLF: "狼人",
  SEER: "预言家",
  WITCH: "女巫",
  HUNTER: "猎人",
};

function createInitialPlayers(): PlayerListItem[] {
  return Array.from({ length: 9 }, (_, index) => ({
    seatId: index + 1,
    isAlive: true,
    isHuman: index === 0,
    roleLabel: index === 0 ? "身份待同步" : undefined,
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
  const humanRole = roleText[identityMatch[2]] ?? identityMatch[2];
  return players.map((player) => ({
    ...player,
    isHuman: player.seatId === humanSeat,
    roleLabel: player.seatId === humanSeat ? humanRole : undefined,
  }));
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
  return players.map((player) => ({
    ...player,
    isThinking: false,
    roleLabel: payload.revealed_roles[player.seatId]
      ? (roleText[payload.revealed_roles[player.seatId]] ?? payload.revealed_roles[player.seatId])
      : player.roleLabel,
  }));
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
          ? `${publicSpeechMatch[1]}号玩家`
          : payload.data.speaker ?? "系统播报",
    };
  }

  if (payload.type === "GAME_OVER") {
    return {
      id: `game-over-${crypto.randomUUID()}`,
      kind: "system",
      message: payload.data.summary,
      speaker: "结算",
    };
  }

  return null;
}

function findLatestOutcome(entries: ChatEntry[]) {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    if (entries[index]?.speaker === "结算") {
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
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const latestMessage = entries.length > 0 ? entries[entries.length - 1].message : "等待服务端推送";
  const humanPlayer = players.find((player) => player.isHuman) ?? null;
  const latestOutcome = findLatestOutcome(entries);
  const spotlightText = pendingAction
    ? "轮到你决策"
    : latestOutcome
      ? "终局揭示"
      : phase === "open"
        ? "AI 推理进行中"
        : "等待会话建立";

  useEffect(() => {
    let disposed = false;
    shouldReconnectRef.current = true;
    setEntries([]);
    setPlayers(createInitialPlayers());
    setPendingAction(null);
    setPhase("connecting");

    const socket = new WebSocket(createGameSocketUrl(window.location));
    socketRef.current = socket;

    function scheduleReconnect() {
      if (disposed || reconnectTimerRef.current !== null) {
        return;
      }

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
    });

    socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data) as ServerEnvelope;
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
      if (event?.code === GAME_OVER_CLOSE_CODE || !shouldReconnectRef.current) {
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
        <header className="status-shell">
          <div className="hero-copy">
            <p className="eyebrow">Stage Of Intrigue</p>
            <h1>狼人杀对局面板</h1>
            <p className="summary">
              这里会持续同步你的身份、对局日志和可执行操作；如果会话重建，界面会自动清空上一局的残留状态。
            </p>
          </div>
          <dl className="status-board">
            <div className="status-card">
              <dt>连接状态</dt>
              <dd>{statusText[phase]}</dd>
            </div>
            <div className="status-card">
              <dt>最近系统消息</dt>
              <dd className="status-message">{latestMessage}</dd>
            </div>
            <div className="status-card status-card--accent">
              <dt>当前节奏</dt>
              <dd>{spotlightText}</dd>
            </div>
          </dl>
        </header>

        <div className="app-grid">
          <aside className="board-column">
            <section className="identity-card" aria-label="你的身份摘要">
              <p className="identity-kicker">你的席位</p>
              <strong>{humanPlayer ? `${humanPlayer.seatId}号玩家` : "等待同步"}</strong>
              <p>{humanPlayer?.roleLabel ?? "身份待同步"}</p>
              <span className={`identity-state ${humanPlayer?.isAlive === false ? "is-dead" : "is-alive"}`}>
                {humanPlayer?.isAlive === false ? "已出局" : "仍在局内"}
              </span>
            </section>
            <PlayerList players={players} />
          </aside>

          <section className="log-column">
            <section
              className={`result-banner ${latestOutcome ? "" : "is-muted"}`}
              aria-label={latestOutcome ? "终局提示" : "战局提示"}
            >
              <p className="result-banner__kicker">{latestOutcome ? "Curtain Call" : "Live Narrative"}</p>
              <strong>{latestOutcome ? latestOutcome.message : spotlightText}</strong>
              <span>
                {latestOutcome
                  ? "身份已经揭示，连接将停留在终局态。"
                  : pendingAction
                    ? "行动通道已经解锁，请在右侧面板完成本轮指令。"
                    : "系统会持续把最新播报、私信和公开发言写入中央信息流。"}
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
