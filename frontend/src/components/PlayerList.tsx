export interface PlayerListItem {
  seatId: number;
  isAlive: boolean;
  isHuman: boolean;
  roleLabel?: string;
  isThinking: boolean;
}

interface PlayerListProps {
  players: PlayerListItem[];
}

export function PlayerList({ players }: PlayerListProps) {
  return (
    <section className="player-panel" aria-labelledby="player-panel-title">
      <div className="panel-header">
        <p className="panel-kicker">Seat Board</p>
        <div>
          <h2 id="player-panel-title">玩家列表</h2>
          <p className="panel-copy">展示座位、存活状态、真人标识与 AI 思考态。</p>
        </div>
      </div>
      <ol className="player-grid" aria-label="玩家状态列表">
        {players.map((player) => (
          <li
            key={player.seatId}
            className={[
              "player-card",
              player.isHuman ? "is-human" : "",
              player.isAlive ? "is-alive" : "is-dead",
              player.isThinking ? "is-thinking" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-label={`${player.seatId}号玩家`}
          >
            <div className="seat-chip">{player.seatId}</div>
            <div className="player-copy">
              <strong>{player.seatId}号玩家</strong>
              <span>{player.isHuman ? `真人 · ${player.roleLabel ?? "身份待同步"}` : "AI 玩家"}</span>
            </div>
            <div className="player-tags" aria-label={`${player.seatId}号状态`}>
              <span>{player.isAlive ? "存活" : "墓碑"}</span>
              {player.isThinking ? <span className="thinking-pill">思考中</span> : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
