import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1 grid lg:grid-cols-2 gap-0">
        {/* Left: editorial intro */}
        <div className="flex flex-col justify-center px-8 sm:px-16 py-20 border-b lg:border-b-0 lg:border-r border-lab-border">
          <div className="max-w-md">
            <p className="font-data text-xs text-lab-text-faint mb-6">
              ai-research-lab
            </p>
            <h1 className="font-display text-4xl sm:text-5xl leading-[1.1] mb-6">
              An investigation engine that shows its work.
            </h1>
            <p className="text-lab-text-muted leading-relaxed mb-10">
              Give it a question and a dataset. It profiles the data, tests
              competing hypotheses, argues with its own conclusions, and
              hands you a report you can audit line by line — every number
              traces back to a computation, not a guess.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <Link
                href="/lab"
                className="text-center bg-lab-accent text-lab-bg font-medium px-6 py-3 rounded-sm hover:brightness-110 transition-[filter]"
              >
                Start an investigation
              </Link>
              <Link
                href="/explorer"
                className="text-center border border-lab-border-strong px-6 py-3 rounded-sm text-lab-text hover:border-lab-text-muted transition-colors"
              >
                Explore a dataset
              </Link>
            </div>
          </div>
        </div>

        {/* Right: a real specimen card, not a stock illustration */}
        <div className="flex items-center justify-center px-8 py-20 bg-lab-panel">
          <div className="w-full max-w-sm border border-lab-border-strong rounded-sm bg-lab-panel-raised">
            <div className="flex items-center justify-between px-5 py-3 border-b border-lab-border">
              <span className="font-data text-xs text-lab-text-faint">hypothesis · 04</span>
              <span className="lab-tag bg-lab-support-dim text-lab-support border-lab-support">
                supported
              </span>
            </div>
            <div className="px-5 py-5">
              <p className="font-display text-lg leading-snug mb-4">
                Revenue declined 27% over the observed period.
              </p>
              <dl className="font-data text-xs space-y-1.5 text-lab-text-muted">
                <Row label="p-value" value="4.7e-46" />
                <Row label="r\u00b2" value="0.697" />
                <Row label="n" value="172" />
                <Row label="confidence" value="high" accent />
              </dl>
            </div>
            <div className="px-5 py-3 border-t border-lab-border font-data text-[11px] text-lab-text-faint">
              evidence: dataset_stat, statistical_test
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex justify-between">
      <dt>{label}</dt>
      <dd className={accent ? "text-lab-accent" : "text-lab-text"}>{value}</dd>
    </div>
  );
}
