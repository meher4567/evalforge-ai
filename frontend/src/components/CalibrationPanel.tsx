import type { CalibrationSignal, ScatterPoint } from "../data/demo";
import { StatusPill } from "./StatusPill";

function x(score: number) {
  return 36 + score * 220;
}

function y(label: number) {
  return 190 - ((label - 1) / 4) * 150;
}

export function CalibrationPanel({
  signals,
  points,
}: {
  signals: CalibrationSignal[];
  points: ScatterPoint[];
}) {
  return (
    <section className="panel calibration-panel" aria-label="Calibration analysis">
      <div className="panel__header">
        <div>
          <h2>Calibration preview</h2>
          <p>Synthetic preview until the hand-labeled gold set is complete</p>
        </div>
        <StatusPill status="warn" label="methodology pending" />
      </div>

      <div className="calibration-grid">
        <div className="scatter-card">
          <svg viewBox="0 0 300 220" role="img" aria-label="Evaluator score versus human label scatter plot">
            <line x1="36" x2="270" y1="190" y2="190" className="axis" />
            <line x1="36" x2="36" y1="24" y2="190" className="axis" />
            <line x1="36" x2="256" y1="190" y2="40" className="trend-line" />
            {[0, 0.5, 1].map((tick) => (
              <g key={tick}>
                <line x1={x(tick)} x2={x(tick)} y1="188" y2="194" className="axis" />
                <text x={x(tick)} y="210" textAnchor="middle">
                  {tick.toFixed(1)}
                </text>
              </g>
            ))}
            {[1, 3, 5].map((tick) => (
              <g key={tick}>
                <line x1="32" x2="39" y1={y(tick)} y2={y(tick)} className="axis" />
                <text x="20" y={y(tick) + 4} textAnchor="middle">
                  {tick}
                </text>
              </g>
            ))}
            {points.map((point) => (
              <circle
                className={`scatter-point scatter-point--${point.tag}`}
                cx={x(point.evaluatorScore)}
                cy={y(point.humanLabel)}
                r="5"
                key={point.id}
              />
            ))}
          </svg>
          <div className="scatter-card__labels">
            <span>Evaluator score</span>
            <span>Human label</span>
          </div>
        </div>

        <div className="signal-list">
          {signals.map((signal) => (
            <article className="signal-row" key={signal.evaluator}>
              <div>
                <h3>{signal.evaluator}</h3>
                <p>{signal.finding}</p>
              </div>
              <div className="signal-row__metrics">
                <span>
                  Pearson <strong>{signal.pearson.toFixed(2)}</strong>
                </span>
                <span>
                  Spearman <strong>{signal.spearman.toFixed(2)}</strong>
                </span>
                <span>
                  Agree <strong>{Math.round(signal.agreementRate * 100)}%</strong>
                </span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
