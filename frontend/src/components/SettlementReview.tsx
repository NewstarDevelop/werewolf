import {
  formatGameMessage,
  formatSeat,
  formatSeatList,
  gamePhaseCopy,
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

function formatPhase(dayCount: number, phase: string) {
  return `第 ${dayCount} 天 · ${gamePhaseCopy[phase] ?? phase}`;
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

function FinalVote({ vote }: { vote: VoteResultView | null }) {
  if (!vote) {
    return <p className="settlement-empty">{uiCopy.settlement.finalVoteEmpty}</p>;
  }

  const rows = numberEntries(vote.votes)
    .sort((left, right) => right[1] - left[1] || left[0] - right[0]);

  return (
    <div className="settlement-final-vote">
      <p>{formatGameMessage(vote.summary)}</p>
      {rows.length > 0 ? (
        <ol>
          {rows.map(([targetSeat, count]) => (
            <li key={targetSeat}>
              <strong>{formatSeat(targetSeat)}</strong>
              <span>{uiCopy.voteBoard.formatCount(count)}</span>
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

function DayCausality({ days }: { days: SettlementReviewDay[] }) {
  if (days.length === 0) {
    return <p className="settlement-empty">{uiCopy.settlement.dayEmpty}</p>;
  }

  return (
    <ol className="settlement-causality-list">
      {days.map((day) => (
        <li key={day.dayCount}>
          <span>{uiCopy.settlement.formatDayTitle(day.dayCount)}</span>
          {day.speeches.length > 0 ? (
            <div className="settlement-speeches">
              {day.speeches.slice(0, 4).map((speech) => (
                <p key={`${speech.seatId}-${speech.message}`}>
                  <strong>{formatSeat(speech.seatId)}</strong>
                  {speech.message}
                </p>
              ))}
            </div>
          ) : (
            <p>{uiCopy.settlement.noPublicSpeech}</p>
          )}
          <p>
            {uiCopy.settlement.voteCausePrefix}：
            {day.voteExplanation ? formatGameMessage(day.voteExplanation) : uiCopy.settlement.voteCauseEmpty}
          </p>
        </li>
      ))}
    </ol>
  );
}

export function SettlementReview({ review }: SettlementReviewProps) {
  const survivors = review.players
    .filter((player) => player.isAlive)
    .map((player) => player.seatId);
  const wolves = review.players
    .filter((player) => player.side === "WOLF")
    .map((player) => player.seatId);
  const timelineEvents = review.timeline.length > 0 ? review.timeline : review.keyEvents;

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
        <span>{review.roleRevealSummary}</span>
        <span>
          {uiCopy.settlement.survivorsPrefix}：
          {survivors.length > 0 ? formatSeatList(survivors) : uiCopy.settlement.none}
        </span>
        <span>
          {uiCopy.settlement.wolvesPrefix}：
          {wolves.length > 0 ? formatSeatList(wolves) : uiCopy.settlement.none}
        </span>
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

        <section className="settlement-review__block" aria-label={uiCopy.settlement.dayBlockAria}>
          <h3>{uiCopy.settlement.dayBlockAria}</h3>
          <DayCausality days={review.days} />
        </section>

        <section className="settlement-review__block" aria-label={uiCopy.settlement.timelineAria}>
          <h3>{uiCopy.settlement.timelineTitle}</h3>
          {timelineEvents.length > 0 ? (
            <ol className="settlement-timeline">
              {timelineEvents.map((event, index) => (
                <li key={`${event.eventType}-${index}`}>
                  <span>{formatPhase(event.dayCount, event.phase)}</span>
                  <p>{event.eventType === "SPEECH" ? event.message : formatGameMessage(event.message)}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="settlement-empty">{uiCopy.settlement.timelineEmpty}</p>
          )}
        </section>

        <section className="settlement-review__block" aria-label={uiCopy.settlement.finalVoteBlockAria}>
          <h3>{uiCopy.settlement.finalVoteBlockAria}</h3>
          <FinalVote vote={review.finalVote} />
        </section>
      </div>
    </section>
  );
}
