import {
  formatGameMessage,
  formatSeat,
  formatSeatList,
  identityStateCopy,
  uiCopy,
} from "../copy";
import type {
  SettlementReviewData,
  SettlementReviewDay,
  SettlementReviewNight,
  VoteResultView,
} from "../state/gameState";

interface SettlementReviewProps {
  review: SettlementReviewData;
}

function outcomeLabel(side: SettlementReviewData["winningSide"]) {
  if (side === "GOOD") {
    return uiCopy.settlement.outcomeGood;
  }
  if (side === "WOLF") {
    return uiCopy.settlement.outcomeWolf;
  }
  return uiCopy.settlement.outcomeDraw;
}

function sideLabel(side: "GOOD" | "WOLF") {
  return side === "WOLF" ? uiCopy.settlement.sideWolf : uiCopy.settlement.sideGood;
}

function resultLabel(result: "GOOD" | "WOLF" | null) {
  if (result === "WOLF") {
    return uiCopy.settlement.resultWolf;
  }
  if (result === "GOOD") {
    return uiCopy.settlement.resultGood;
  }
  return uiCopy.settlement.resultUnknown;
}

function seatOrNone(seatId: number | null) {
  return seatId === null ? uiCopy.settlement.none : formatSeat(seatId);
}

function numberEntries(record: Record<number, number>) {
  return Object.entries(record).map(([key, value]) => [Number(key), value] as const);
}

function VoteDetails({ vote }: { vote: VoteResultView }) {
  const rows = numberEntries(vote.votes)
    .map(([targetSeat, count]) => ({
      targetSeat,
      count,
      voters: numberEntries(vote.ballots)
        .filter(([, votedTarget]) => votedTarget === targetSeat)
        .map(([voterSeat]) => voterSeat)
        .sort((left, right) => left - right),
    }))
    .sort((left, right) => right.count - left.count || left.targetSeat - right.targetSeat);

  return (
    <div className="settlement-final-vote">
      <p>{formatGameMessage(vote.summary)}</p>
      {rows.length > 0 ? (
        <ol>
          {rows.map(({ targetSeat, count, voters }) => (
            <li key={targetSeat}>
              <span className="settlement-final-vote__target">
                <strong>{formatSeat(targetSeat)}</strong>
                <span>{uiCopy.voteBoard.formatCount(count)}</span>
              </span>
              {voters.length > 0 ? (
                <span
                  className="settlement-final-vote__sources"
                  aria-label={uiCopy.voteBoard.formatSourceAria(targetSeat)}
                >
                  <span className="settlement-final-vote__sources-label">{uiCopy.voteBoard.sourcesLabel}</span>
                  {voters.map((voterSeat) => (
                    <span key={voterSeat}>{formatSeat(voterSeat)}</span>
                  ))}
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
      {vote.abstentions.length > 0 ? (
        <span className="settlement-final-vote__abstain">
          {uiCopy.settlement.voteAbstainPrefix}：{formatSeatList(vote.abstentions)}
        </span>
      ) : null}
    </div>
  );
}

function GlobalVotes({
  days,
  finalVote,
}: {
  days: SettlementReviewDay[];
  finalVote: VoteResultView | null;
}) {
  const dayVoteSections = days
    .filter((day): day is SettlementReviewDay & { vote: VoteResultView } => day.vote !== null)
    .map((day) => ({
      key: `day-${day.dayCount}`,
      title: uiCopy.settlement.formatDayVoteTitle(day.dayCount),
      vote: day.vote,
    }));

  const voteSections = dayVoteSections.length > 0
    ? dayVoteSections
    : finalVote
      ? [{
          key: "final",
          title: uiCopy.settlement.finalVoteFallbackTitle,
          vote: finalVote,
        }]
      : [];

  if (voteSections.length === 0) {
    return <p className="settlement-empty">{uiCopy.settlement.globalVoteEmpty}</p>;
  }

  return (
    <div className="settlement-global-votes">
      {voteSections.map((section) => (
        <section
          key={section.key}
          className="settlement-global-vote"
          aria-label={section.title}
        >
          <h4>{section.title}</h4>
          <VoteDetails vote={section.vote} />
        </section>
      ))}
    </div>
  );
}

function NightCausality({ nights }: { nights: SettlementReviewNight[] }) {
  if (nights.length === 0) {
    return <p className="settlement-empty">{uiCopy.settlement.nightEmpty}</p>;
  }

  return (
    <ol className="settlement-causality-list">
      {nights.map((night) => (
        <li key={night.dayCount}>
          <span>{uiCopy.settlement.formatNightTitle(night.dayCount)}</span>
          <p>{uiCopy.settlement.wolfTargetPrefix}：{seatOrNone(night.wolfTarget)}</p>
          <p>
            {uiCopy.settlement.seerPrefix}：
            {night.seerSeat === null || night.seerTarget === null
              ? uiCopy.settlement.seerEmpty
              : `${formatSeat(night.seerSeat)} 查验 ${formatSeat(night.seerTarget)}，结果为${resultLabel(night.seerResult)}`}
          </p>
          <p>
            {uiCopy.settlement.witchPrefix}：
            {night.witchSeat === null
              ? uiCopy.settlement.witchEmpty
              : [
                  night.witchSaveTarget === null
                    ? null
                    : uiCopy.settlement.formatWitchSave(night.witchSaveTarget),
                  night.witchPoisonTarget === null
                    ? null
                    : uiCopy.settlement.formatWitchPoison(night.witchPoisonTarget),
                ].filter(Boolean).join("，") || uiCopy.settlement.witchNoUse}
          </p>
          <p>
            {uiCopy.settlement.nightResultPrefix}：
            {night.deadSeats.length > 0 ? formatSeatList(night.deadSeats) : uiCopy.settlement.peacefulNight}
          </p>
        </li>
      ))}
    </ol>
  );
}

export function SettlementReview({ review }: SettlementReviewProps) {
  return (
    <section
      className={`settlement-review is-${review.winningSide.toLowerCase()}`}
      aria-label={uiCopy.settlement.aria}
    >
      <header className="settlement-review__header">
        <div>
          <h2>{uiCopy.settlement.title}</h2>
          <p>{formatGameMessage(review.summary)}</p>
        </div>
        <strong>{outcomeLabel(review.winningSide)}</strong>
      </header>

      <div className="settlement-review__stats">
        <span>{uiCopy.settlement.formatFinalDay(review.dayCount)}</span>
        <span>{uiCopy.settlement.reasonPrefix}：{formatGameMessage(review.outcomeReason)}</span>
      </div>

      <div className="settlement-review__grid">
        <section className="settlement-review__block" aria-label={uiCopy.settlement.rosterAria}>
          <h3>{uiCopy.settlement.rosterTitle}</h3>
          <ol className="settlement-roster">
            {review.players.map((player) => (
              <li
                key={player.seatId}
                className={[
                  "settlement-roster__player",
                  player.side === "WOLF" ? "is-wolf" : "is-good",
                  player.isAlive ? "is-alive" : "is-dead",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span>{formatSeat(player.seatId)}</span>
                <strong>{player.roleLabel}</strong>
                <em>
                  {sideLabel(player.side)} · {player.isAlive ? identityStateCopy.alive : identityStateCopy.dead}
                  {player.isHuman ? ` · ${uiCopy.playerList.humanPrefix}` : ""}
                </em>
              </li>
            ))}
          </ol>
        </section>

        <section className="settlement-review__block" aria-label={uiCopy.settlement.nightBlockAria}>
          <h3>{uiCopy.settlement.nightBlockAria}</h3>
          <NightCausality nights={review.nights} />
        </section>

        <section className="settlement-review__block" aria-label={uiCopy.settlement.globalVoteBlockAria}>
          <h3>{uiCopy.settlement.globalVoteBlockAria}</h3>
          <GlobalVotes days={review.days} finalVote={review.finalVote} />
        </section>
      </div>
    </section>
  );
}
