interface StatusPillProps {
  status:
    | "pass"
    | "warn"
    | "fail"
    | "completed"
    | "partial"
    | "running"
    | "failed"
    | "cancelled"
    | "timed_out"
    | "not_evaluated";
  label?: string;
}

export function StatusPill({ status, label }: StatusPillProps) {
  return <span className={`status-pill status-pill--${status}`}>{label ?? status}</span>;
}
