import { formatSeat, identityStateCopy, uiCopy } from "../copy";

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
    <section className="desk" aria-label={uiCopy.playerList.deskAria}>
      <ol className="player-ring" aria-label={uiCopy.playerList.listAria}>
        {players.map((player) => {
          const statusText = player.isAlive
            ? player.isThinking
              ? uiCopy.playerList.thinking
              : uiCopy.playerList.alive
            : uiCopy.playerList.dead;

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
                  ? `${uiCopy.playerList.humanPrefix} · ${player.roleLabel ?? identityStateCopy.unknownRole}`
                  : player.roleLabel ?? uiCopy.playerList.hiddenRole}
              </span>
              <span className="seat-status" aria-label={uiCopy.playerList.formatSeatStatusAria(player.seatId)}>
                {statusText}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="desk-stats" aria-live="polite">
        {uiCopy.playerList.formatStats(aliveCount, thinkingCount)}
      </p>
    </section>
  );
}
