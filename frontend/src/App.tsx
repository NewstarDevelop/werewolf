import { useEffect, useState } from "react";

import { createGameSocketUrl, type ConnectionPhase, type ServerEnvelope } from "./ws/client";

const statusText: Record<ConnectionPhase, string> = {
  idle: "尚未连接",
  connecting: "连接中",
  open: "已连接",
  closed: "已断开",
  error: "连接异常",
};

export function App() {
  const [phase, setPhase] = useState<ConnectionPhase>("idle");
  const [messages, setMessages] = useState<string[]>([]);
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
      </section>
    </main>
  );
}
