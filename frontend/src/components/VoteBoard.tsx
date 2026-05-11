import { formatGameMessage, formatSeat, uiCopy } from "../copy";

export interface VoteBoardResult {
  votes: Record<number, number>;
  ballots: Record<number, number>;
  abstentions: number[];
  banishedSeat: number | null;
  summary: string;
}

interface VoteBoardProps {
  result: VoteBoardResult;
}

function numberEntries(record: Record<number, number>) {
  return Object.entries(record).map(([key, value]) => [Number(key), value] as const);
}

function formatVoteCount(count: number) {
  return uiCopy.voteBoard.formatCount(count);
}

export function VoteBoard({ result }: VoteBoardProps) {
  const voteRows = numberEntries(result.votes)
    .map(([targetSeat, count]) => ({
      targetSeat,
      count,
      voters: numberEntries(result.ballots)
        .filter(([, votedTarget]) => votedTarget === targetSeat)
        .map(([voterSeat]) => voterSeat)
        .sort((left, right) => left - right),
    }))
    .sort((left, right) => right.count - left.count || left.targetSeat - right.targetSeat);
  const maxVotes = Math.max(1, ...voteRows.map((row) => row.count));
  const totalVotes = voteRows.reduce((total, row) => total + row.count, 0);
  const totalParticipants = totalVotes + result.abstentions.length;

  return (
    <section className="vote-board" aria-label={uiCopy.voteBoard.aria}>
      <header className="vote-board__header">
        <div>
          <h2>{uiCopy.voteBoard.title}</h2>
          <p>{formatGameMessage(result.summary)}</p>
        </div>
        <span className="vote-board__count">{uiCopy.voteBoard.formatParticipantCount(totalParticipants)}</span>
      </header>

      <div className="vote-board__rows">
        {voteRows.map((row) => {
          const width = `${Math.max(8, Math.round((row.count / maxVotes) * 100))}%`;
          return (
            <div
              key={row.targetSeat}
              className={[
                "vote-row",
                result.banishedSeat === row.targetSeat ? "is-banished" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <div className="vote-row__label">
                <strong>{formatSeat(row.targetSeat)}</strong>
                <span>{formatVoteCount(row.count)}</span>
              </div>
              <div
                className="vote-meter"
                role="meter"
                aria-label={uiCopy.voteBoard.formatMeterAria(row.targetSeat)}
                aria-valuemin={0}
                aria-valuemax={maxVotes}
                aria-valuenow={row.count}
              >
                <span className="vote-meter__fill" style={{ width }} />
              </div>
              <div className="vote-voters" aria-label={uiCopy.voteBoard.formatSourceAria(row.targetSeat)}>
                {row.voters.map((voterSeat) => (
                  <span key={voterSeat}>{formatSeat(voterSeat)}</span>
                ))}
              </div>
            </div>
          );
        })}

        {result.abstentions.length > 0 ? (
          <div className="vote-row is-muted">
            <div className="vote-row__label">
              <strong>{uiCopy.voteBoard.abstain}</strong>
              <span>{formatVoteCount(result.abstentions.length)}</span>
            </div>
            <div className="vote-voters" aria-label={uiCopy.voteBoard.abstainAria}>
              {result.abstentions.map((seatId) => (
                <span key={seatId}>{formatSeat(seatId)}</span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
