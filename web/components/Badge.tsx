const STYLES: Record<string, string> = {
  SUPPORTED: "bg-lab-support-dim text-lab-support border-lab-support",
  HIGH: "bg-lab-support-dim text-lab-support border-lab-support",
  PARTIALLY_SUPPORTED: "bg-lab-warn-dim text-lab-warn border-lab-warn",
  MODERATE: "bg-lab-warn-dim text-lab-warn border-lab-warn",
  REJECTED: "bg-lab-danger-dim text-lab-danger border-lab-danger",
  INSUFFICIENT_EVIDENCE: "bg-lab-danger-dim text-lab-danger border-lab-danger",
  LOW: "bg-lab-danger-dim text-lab-danger border-lab-danger",
  blocking: "bg-lab-danger-dim text-lab-danger border-lab-danger",
  warning: "bg-lab-warn-dim text-lab-warn border-lab-warn",
};

export function Badge({ label }: { label: string }) {
  const cls = STYLES[label] || "bg-lab-panel-raised text-lab-text-muted border-lab-border-strong";
  return (
    <span className={`lab-tag ${cls}`}>
      {label.toLowerCase().replace(/_/g, " ")}
    </span>
  );
}
