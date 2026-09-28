"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAdminStats, AdminStats } from "@/lib/api";

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminStats().then(setStats).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="min-h-screen">
      <header className="border-b border-lab-border px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg">Observability</h1>
          <p className="text-lab-text-muted text-sm font-data">
            aggregate metrics across all investigations
          </p>
        </div>
        <Link href="/lab" className="text-sm text-lab-accent hover:brightness-110 font-data">
          back to lab
        </Link>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-8 space-y-6">
        {error && <p className="text-lab-danger text-sm font-data">{error}</p>}
        {!stats && !error && (
          <p className="text-lab-text-muted font-data text-sm">loading…</p>
        )}

        {stats && stats.total_investigations === 0 && (
          <div className="border border-lab-border rounded-sm p-6 text-lab-text-muted font-data text-sm">
            No investigations recorded yet. Run one from the Lab to populate this view.
          </div>
        )}

        {stats && stats.total_investigations > 0 && (
          <>
            <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <Stat label="total investigations" value={stats.total_investigations} />
              <Stat
                label="avg runtime"
                value={stats.avg_runtime_s !== null ? `${stats.avg_runtime_s}s` : "—"}
              />
              <Stat
                label="avg revision cycles"
                value={stats.avg_revision_cycles ?? "—"}
              />
              <Stat
                label="runs w/ critic findings"
                value={
                  stats.investigations_with_critic_findings_pct !== null
                    ? `${stats.investigations_with_critic_findings_pct}%`
                    : "—"
                }
              />
            </section>

            <section className="border border-lab-border rounded-sm">
              <div className="px-5 py-3 border-b border-lab-border">
                <h2 className="font-display text-base">Status breakdown</h2>
              </div>
              <div className="px-5 py-4 space-y-2 font-data text-sm">
                {Object.entries(stats.status_breakdown).map(([status, count]) => (
                  <Bar
                    key={status}
                    label={status.toLowerCase()}
                    value={count}
                    max={stats.total_investigations}
                  />
                ))}
              </div>
            </section>

            <section className="border border-lab-border rounded-sm">
              <div className="px-5 py-3 border-b border-lab-border">
                <h2 className="font-display text-base">Average time per agent</h2>
              </div>
              <div className="px-5 py-4 space-y-2 font-data text-sm">
                {Object.entries(stats.avg_agent_timings_s)
                  .sort((a, b) => b[1] - a[1])
                  .map(([agent, seconds]) => (
                    <Bar
                      key={agent}
                      label={agent}
                      value={seconds}
                      max={Math.max(...Object.values(stats.avg_agent_timings_s))}
                      formatValue={(v) => `${(v * 1000).toFixed(1)}ms`}
                    />
                  ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-lab-border rounded-sm p-4">
      <div className="font-display text-2xl">{value}</div>
      <div className="text-lab-text-faint text-xs font-data mt-1">{label}</div>
    </div>
  );
}

function Bar({
  label,
  value,
  max,
  formatValue,
}: {
  label: string;
  value: number;
  max: number;
  formatValue?: (v: number) => string;
}) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-lab-text-muted mb-1">
        <span>{label}</span>
        <span>{formatValue ? formatValue(value) : value}</span>
      </div>
      <div className="h-1.5 bg-lab-panel-raised rounded-sm overflow-hidden">
        <div className="h-full bg-lab-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
