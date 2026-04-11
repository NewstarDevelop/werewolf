import { useEffect, useState } from "react";

import { PlayerList, type PlayerListItem } from "./components/PlayerList";
import { createGameSocketUrl, type ConnectionPhase, type ServerEnvelope } from "./ws/client";

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

function applySystemMessage(players: PlayerListItem[], message: string) {
  let nextPlayers = players;
  const identityMatch = message.match(/你的座位号是\s*(\d+)\s*号，身份是\s*([A-Z_]+)\s*。?/);

  if (identityMatch) {
    const humanSeat = Number(identityMatch[1]);
    const humanRole = roleText[identityMatch[2]] ?? identityMatch[2];
    nextPlayers = nextPlayers.map((player) => ({
      ...player,
      isHuman: player.seatId === humanSeat,
      roleLabel: player.seatId === humanSeat ? humanRole : undefined,
    }));
  }

  const deathMatches = [...message.matchAll(/(\d+)号(?:玩家)?(?:被放逐出局|死亡)/g)];
  if (deathMatches.length > 0) {
    const deadSeats = new Set(deathMatches.map((match) => Number(match[1])));
    nextPlayers = nextPlayers.map((player) =>
      deadSeats.has(player.seatId) ? { ...player, isAlive: false, isThinking: false } : player,
    );
  }

  return nextPlayers;
}

export function App() {
  const [phase, setPhase] = useState<ConnectionPhase>("idle");
  const [messages, setMessages] = useState<string[]>([]);
  const [players, setPlayers] = useState<PlayerListItem[]>(() => createInitialPlayers());
  const latestMessage = messages.length > 0 ? messages[messages.length - 1] : "等待服务端推送";

  useEffect(() => {
    const socket = new WebSocket(createGameSocketUrl(window.location));

    setPhase("connecting");

    socket.addEventListener("open", () => {
      setPhase("open");
    });

    socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data) as ServerEnvelope;
      if (payload.type === "SYSTEM_MSG") {
        setMessages((current) => [...current, payload.data.message]);
        setPlayers((current) => applySystemMessage(current, payload.data.message));
      }
      if (payload.type === "AI_THINKING") {
        setPlayers((current) =>
          applyThinkingState(current, payload.data.seat_id, payload.data.is_thinking),
        );
      }
    });

    socket.addEventListener("error", () => {
      setPhase("error");
    });

    socket.addEventListener("close", () => {
      setPhase("closed");
    });

    return () => {
      socket.close();
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">9 人局 AI 狼人杀</p>
        <h1>工程骨架已启动</h1>
        <p className="summary">
          当前阶段先完成前后端骨架、通信入口与基础回归验证，再逐步接入状态机和 UI 组件。
        </p>
        <dl className="status-board">
          <div>
            <dt>连接状态</dt>
            <dd>{statusText[phase]}</dd>
          </div>
          <div>
            <dt>最近系统消息</dt>
            <dd>{latestMessage}</dd>
          </div>
        </dl>
        <PlayerList players={players} />
      </section>
    </main>
  );
}
