interface StatusPillProps {
  status: "pass" | "warn" | "fail" | "completed" | "partial" | "running";
  label?: string;
}

export function StatusPill({ status, label }: StatusPillProps) {
  return <span className={`status-pill status-pill--${status}`}>{label ?? status}</span>;
}
