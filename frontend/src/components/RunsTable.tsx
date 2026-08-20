import { Eye } from "lucide-react";
import type { RunRow } from "../data/demo";
import { formatCost, formatLatency, formatPercent } from "../lib/format";
import { StatusPill } from "./StatusPill";

interface RunsTableProps {
  runs: RunRow[];
  selectedRunId: string;
  onSelectRun: (runId: string) => void;
}

export function RunsTable({ runs, selectedRunId, onSelectRun }: RunsTableProps) {
  return (
    <section className="panel table-panel" aria-label="Recent evaluation runs">
      <div className="panel__header">
        <div>
          <h2>Recent evaluation runs</h2>
          <p>Latest reproducible benchmark executions</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Run</th>
              <th>Version</th>
              <th>Cases</th>
              <th>Pass</th>
              <th>Overlap</th>
              <th>p95</th>
              <th>Cost</th>
              <th>Status</th>
              <th>Open</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr className={run.id === selectedRunId ? "is-selected" : ""} key={run.id}>
                <td>
                  <button className="link-button" type="button" onClick={() => onSelectRun(run.id)}>
                    {run.id}
                  </button>
                  <span className="table-subtext">{run.createdAt}</span>
                </td>
                <td>{run.version}</td>
                <td>{run.cases}</td>
                <td>{formatPercent(run.passRate)}</td>
                <td>{run.semanticSimilarity.toFixed(3)}</td>
                <td>{formatLatency(run.p95LatencyMs)}</td>
                <td>{formatCost(run.costMeanUsd)}</td>
                <td>
                  <StatusPill status={run.status} />
                </td>
                <td>
                  <button
                    className="icon-button icon-button--small"
                    type="button"
                    aria-label={`Open ${run.id}`}
                    onClick={() => onSelectRun(run.id)}
                  >
                    <Eye size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
