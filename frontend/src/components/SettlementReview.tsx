import {
  formatSeat,
  formatSeatList,
  gamePhaseCopy,
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
    return "好人胜利";
  }
  if (side === "WOLF") {
    return "狼人胜利";
  }
  return "平局暂止";
}

function sideLabel(side: "GOOD" | "WOLF") {
  return side === "WOLF" ? "狼人阵营" : "好人阵营";
}

function formatPhase(dayCount: number, phase: string) {
  return `第 ${dayCount} 日 · ${gamePhaseCopy[phase] ?? phase}`;
}

function resultLabel(result: "GOOD" | "WOLF" | null) {
  if (result === "WOLF") {
    return "狼人";
  }
  if (result === "GOOD") {
    return "好人";
  }
  return "未知";
}

function seatOrNone(seatId: number | null) {
  return seatId === null ? "无" : formatSeat(seatId);
}

function numberEntries(record: Record<number, number>) {
  return Object.entries(record).map(([key, value]) => [Number(key), value] as const);
}

function FinalVote({ vote }: { vote: VoteResultView | null }) {
  if (!vote) {
    return <p className="settlement-empty">终局未经过放逐票。</p>;
  }

  const rows = numberEntries(vote.votes)
    .sort((left, right) => right[1] - left[1] || left[0] - right[0]);

  return (
    <div className="settlement-final-vote">
      <p>{vote.summary}</p>
      {rows.length > 0 ? (
        <ol>
          {rows.map(([targetSeat, count]) => (
            <li key={targetSeat}>
              <strong>{formatSeat(targetSeat)}</strong>
              <span>{count}票</span>
            </li>
          ))}
        </ol>
      ) : null}
      {vote.abstentions.length > 0 ? (
        <span className="settlement-final-vote__abstain">
          弃票：{formatSeatList(vote.abstentions)}
        </span>
      ) : null}
    </div>
  );
}

function NightCausality({ nights }: { nights: SettlementReviewNight[] }) {
  if (nights.length === 0) {
    return <p className="settlement-empty">本局没有进入完整夜晚。</p>;
  }

  return (
    <ol className="settlement-causality-list">
      {nights.map((night) => (
        <li key={night.dayCount}>
          <span>第 {night.dayCount} 夜</span>
          <p>狼人刀向：{seatOrNone(night.wolfTarget)}</p>
          <p>
            预言家：
            {night.seerSeat === null || night.seerTarget === null
              ? "未查验"
              : `${formatSeat(night.seerSeat)} 查验 ${formatSeat(night.seerTarget)}，结果为${resultLabel(night.seerResult)}`}
          </p>
          <p>
            女巫：
            {night.witchSeat === null
              ? "未行动"
              : [
                  night.witchSaveTarget === null
                    ? null
                    : `救起 ${formatSeat(night.witchSaveTarget)}`,
                  night.witchPoisonTarget === null
                    ? null
                    : `毒向 ${formatSeat(night.witchPoisonTarget)}`,
                ].filter(Boolean).join("，") || "未用药"}
          </p>
          <p>夜晚结果：{night.deadSeats.length > 0 ? formatSeatList(night.deadSeats) : "平安夜"}</p>
        </li>
      ))}
    </ol>
  );
}

function DayCausality({ days }: { days: SettlementReviewDay[] }) {
  if (days.length === 0) {
    return <p className="settlement-empty">本局没有进入白天发言与投票。</p>;
  }

  return (
    <ol className="settlement-causality-list">
      {days.map((day) => (
        <li key={day.dayCount}>
          <span>第 {day.dayCount} 日</span>
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
            <p>关键发言：无公开发言</p>
          )}
          <p>投票因果：{day.voteExplanation ?? "未进入放逐投票"}</p>
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

  return (
    <section
      className={`settlement-review is-${review.winningSide.toLowerCase()}`}
      aria-label="结算复盘"
    >
      <header className="settlement-review__header">
        <div>
          <h2>结算复盘</h2>
          <p>{review.summary}</p>
        </div>
        <strong>{outcomeLabel(review.winningSide)}</strong>
      </header>

      <div className="settlement-review__stats">
        <span>{review.dayCount === null ? "终局" : `第 ${review.dayCount} 日终局`}</span>
        <span>原因：{review.outcomeReason}</span>
        <span>存活：{survivors.length > 0 ? formatSeatList(survivors) : "无人"}</span>
        <span>狼队：{wolves.length > 0 ? formatSeatList(wolves) : "无"}</span>
      </div>

      <div className="settlement-review__grid">
        <section className="settlement-review__block" aria-label="阵营翻牌">
          <h3>阵营翻牌</h3>
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
                  {sideLabel(player.side)} · {player.isAlive ? "存活" : "出局"}
                  {player.isHuman ? " · 真人" : ""}
                </em>
              </li>
            ))}
          </ol>
        </section>

        <section className="settlement-review__block" aria-label="夜间因果">
          <h3>夜间因果</h3>
          <NightCausality nights={review.nights} />
        </section>

        <section className="settlement-review__block" aria-label="白天因果">
          <h3>白天因果</h3>
          <DayCausality days={review.days} />
        </section>

        <section className="settlement-review__block" aria-label="关键节点">
          <h3>关键节点</h3>
          {review.keyEvents.length > 0 ? (
            <ol className="settlement-timeline">
              {review.keyEvents.map((event, index) => (
                <li key={`${event.eventType}-${index}`}>
                  <span>{formatPhase(event.dayCount, event.phase)}</span>
                  <p>{event.message}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="settlement-empty">本局没有记录到关键公开节点。</p>
          )}
        </section>

        <section className="settlement-review__block" aria-label="终局票型">
          <h3>终局票型</h3>
          <FinalVote vote={review.finalVote} />
        </section>
      </div>
    </section>
  );
}
