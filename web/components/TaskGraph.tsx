"use client";

/**
 * Investigation graph (spec section 20): shows how the question decomposed
 * into a plan and which agents ran, distinct from EvidenceGraph (which is
 * conclusion-focused). Built from state.plan + the log's "Entering phase"
 * markers so it reflects what actually ran, not a static diagram.
 */
export interface PhaseNode {
  name: string;
  status: "done" | "active" | "pending";
}

const PHASES: { key: string; label: string }[] = [
  { key: "DATA_INSPECTION", label: "Data Inspection" },
  { key: "RESEARCH", label: "Research" },
  { key: "HYPOTHESIS_GENERATION", label: "Hypothesis Generation" },
  { key: "EXPERIMENTATION", label: "Experimentation" },
  { key: "CRITIQUE", label: "Critique" },
];

export function TaskGraph({ log, finalStatus }: { log?: string[] | null; finalStatus: string }) {
  const activityLog = Array.isArray(log) ? log : [];
  const reached = new Set(
    PHASES.filter((p) => activityLog.some((line) => line.includes(`Entering phase: ${p.key}`))).map(
      (p) => p.key
    )
  );
  const revisionCount = activityLog.filter((l) => l.includes("starting revision cycle")).length;
  const completed = finalStatus === "COMPLETED";

  return (
    <div className="font-data text-xs">
      <div className="flex items-start gap-0">
        <Node label="question" done />
        <Connector done />
        <Node label="plan" done />
        <Connector done />

        <div className="flex flex-col gap-2">
          {PHASES.map((p) => (
            <div key={p.key} className="flex items-center gap-2">
              <Node label={p.label.toLowerCase()} done={reached.has(p.key)} />
            </div>
          ))}
        </div>

        <Connector done={completed} />
        <Node label={`report${revisionCount ? ` (${revisionCount} revision${revisionCount > 1 ? "s" : ""})` : ""}`} done={completed} accent={completed} />
      </div>
    </div>
  );
}

function Node({ label, done, accent }: { label: string; done: boolean; accent?: boolean }) {
  return (
    <div
      className={`px-3 py-2 rounded-sm border whitespace-nowrap ${
        accent
          ? "border-lab-accent text-lab-accent bg-lab-accent/10"
          : done
          ? "border-lab-support text-lab-support bg-lab-support-dim"
          : "border-lab-border-strong text-lab-text-faint"
      }`}
    >
      {label}
    </div>
  );
}

function Connector({ done }: { done: boolean }) {
  return (
    <div
      className={`h-px w-6 mt-4 ${done ? "bg-lab-support" : "bg-lab-border-strong"}`}
    />
  );
}
