import { ChevronLeft, ChevronRight, Copy, Database, Route } from "lucide-react";
import type { TraceCase } from "../data/demo";
import { formatCost, formatLatency } from "../lib/format";
import { StatusPill } from "./StatusPill";

interface TraceInspectorProps {
  cases: TraceCase[];
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
}

export function TraceInspector({ cases, selectedIndex, onSelectIndex }: TraceInspectorProps) {
  const selected = cases[selectedIndex];

  function move(direction: -1 | 1) {
    const next = (selectedIndex + direction + cases.length) % cases.length;
    onSelectIndex(next);
  }

  return (
    <aside className="trace-inspector" aria-label="Trace inspector">
      <div className="trace-inspector__header">
        <div>
          <h2>Trace inspector</h2>
          <p>
            {selected.id} | {selected.tag}
          </p>
        </div>
        <StatusPill status="fail" label="failed" />
      </div>

      <div className="trace-controls">
        <button className="icon-button" type="button" aria-label="Previous failed case" onClick={() => move(-1)}>
          <ChevronLeft size={16} />
        </button>
        <span>
          Case {selectedIndex + 1} of {cases.length}
        </span>
        <button className="icon-button" type="button" aria-label="Next failed case" onClick={() => move(1)}>
          <ChevronRight size={16} />
        </button>
      </div>

      <div className="trace-block">
        <h3>Question</h3>
        <p>{selected.question}</p>
      </div>

      <div className="trace-block">
        <h3>Candidate answer</h3>
        <p>{selected.candidateAnswer}</p>
      </div>

      <div className="trace-block trace-block--muted">
        <h3>Ground truth</h3>
        <p>{selected.expected}</p>
      </div>

      <div className="trace-score-grid">
        <span>
          Token overlap <strong>{selected.semanticScore.toFixed(2)}</strong>
        </span>
        <span>
          Keywords <strong>{selected.keywordScore.toFixed(2)}</strong>
        </span>
        <span>
          Retrieval <strong>{selected.retrievalHit ? "hit" : "miss"}</strong>
        </span>
        <span>
          Latency <strong>{formatLatency(selected.latencyMs)}</strong>
        </span>
      </div>

      <div className="trace-block">
        <div className="trace-block__title">
          <Database size={15} />
          <h3>Retrieved context</h3>
        </div>
        <ol className="chunk-list">
          {selected.chunks.map((chunk) => (
            <li key={chunk.docId}>
              <span>{chunk.docId}</span>
              <strong>{chunk.score.toFixed(2)}</strong>
              <p>{chunk.text}</p>
            </li>
          ))}
        </ol>
      </div>

      <div className="trace-block">
        <div className="trace-block__title">
          <Route size={15} />
          <h3>Execution metadata</h3>
        </div>
        <dl className="metadata-grid">
          <div>
            <dt>Adapter</dt>
            <dd>demo_rag</dd>
          </div>
          <div>
            <dt>Evaluator</dt>
            <dd>{selected.evaluator}</dd>
          </div>
          <div>
            <dt>Cost</dt>
            <dd>{formatCost(selected.costUsd)}</dd>
          </div>
          <div>
            <dt>Failure</dt>
            <dd>{selected.reason}</dd>
          </div>
        </dl>
      </div>

      <button className="secondary-action" type="button">
        <Copy size={15} />
        Copy trace id
      </button>
    </aside>
  );
}
