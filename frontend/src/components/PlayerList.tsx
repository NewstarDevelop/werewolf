import { formatSeat, identityStateCopy } from "../copy";

export interface PlayerListItem {
  seatId: number;
  isAlive: boolean;
  isHuman: boolean;
  roleLabel?: string;
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
    <section className="desk" aria-label="桌面座位">
      <ol className="player-ring" aria-label="玩家状态列表">
        {players.map((player) => {
          const statusText = player.isAlive
            ? player.isThinking
              ? "仍在局内 · 推演中"
              : "仍在局内"
            : "墓碑";

          return (
            <li
              key={player.seatId}
              className={[
                "player-card",
                "seat",
                player.isHuman ? "is-human" : "",
                player.isAlive ? "is-alive" : "is-dead",
                player.isThinking ? "is-thinking" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-label={formatSeat(player.seatId)}
            >
              <div className="seat-chip">{player.seatId}</div>
              <span className="seat-name">{formatSeat(player.seatId)}</span>
              <span className="seat-role">
                {player.isHuman
                  ? `真人 · ${player.roleLabel ?? identityStateCopy.unknownRole}`
                  : player.roleLabel ?? "局外人"}
              </span>
              <span className="seat-status" aria-label={`${player.seatId}号状态`}>
                {statusText}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="desk-stats" aria-live="polite">
        {aliveCount} 人在局
        {thinkingCount > 0 ? ` · ${thinkingCount} 人推演中` : ""}
      </p>
    </section>
  );
}
