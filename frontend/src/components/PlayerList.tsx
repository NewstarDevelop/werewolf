import { formatSeat, identityStateCopy } from "../copy";

export interface PlayerListItem {
  seatId: number;
  isAlive: boolean;
  isHuman: boolean;
  roleLabel?: string;
  /** Backend role code (e.g. "SEER"). Only set for the human or after reveal. */
  roleCode?: string;
  isThinking: boolean;
}

interface PlayerListProps {
  players: PlayerListItem[];
}

export function PlayerList({ players }: PlayerListProps) {
  const aliveCount = players.filter((player) => player.isAlive).length;
  const thinkingCount = players.filter((player) => player.isThinking).length;

  return (
    <section className="player-panel" aria-labelledby="player-panel-title">
      <header className="panel-header">
        <h2 id="player-panel-title">玩家列表</h2>
        <p className="panel-stats" aria-live="polite">
          {aliveCount} 人在局
          {thinkingCount > 0 ? ` · ${thinkingCount} 人推演中` : ""}
        </p>
      </header>
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
            aria-label={formatSeat(player.seatId)}
          >
            <div className="player-orbit">
              <div className="seat-chip">{player.seatId}</div>
              {player.isHuman ? <span className="player-badge">你</span> : null}
            </div>
            <div className="player-copy">
              <strong>{formatSeat(player.seatId)}</strong>
              <span className="player-role">
                {player.isHuman
                  ? `真人 · ${player.roleLabel ?? identityStateCopy.unknownRole}`
                  : player.roleLabel ?? "局外人"}
              </span>
            </div>
            <div className="player-tags" aria-label={`${player.seatId}号状态`}>
              <span className={`state-pill ${player.isAlive ? "is-alive" : "is-dead"}`}>
                {player.isAlive ? "存活" : "墓碑"}
              </span>
              {player.isThinking ? <span className="thinking-pill">推演中</span> : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
