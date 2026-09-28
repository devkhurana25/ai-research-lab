"use client";

import { useState } from "react";
import Link from "next/link";
import { getDatasetProfile, DatasetProfile } from "@/lib/api";

export default function ExplorerPage() {
  const [path, setPath] = useState("sample_data/sales.csv");
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadProfile() {
    setLoading(true);
    setError(null);
    try {
      setProfile(await getDatasetProfile(path));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-lab-border px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg">Dataset Explorer</h1>
          <p className="text-lab-text-muted text-sm font-data">
            inspect a dataset before investigating it
          </p>
        </div>
        <nav className="flex gap-5 text-sm font-data">
          <Link href="/lab" className="text-lab-text-muted hover:text-lab-text transition-colors">
            lab
          </Link>
          <Link href="/admin" className="text-lab-text-muted hover:text-lab-text transition-colors">
            observability
          </Link>
        </nav>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-8 space-y-6">
        <section className="border border-lab-border rounded-sm p-6 flex gap-3">
          <input
            className="flex-1 bg-lab-panel border border-lab-border-strong rounded-sm px-3 py-2 text-sm font-data focus:outline-none focus:border-lab-accent"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="sample_data/sales.csv"
          />
          <button
            onClick={loadProfile}
            disabled={loading}
            className="bg-lab-accent disabled:opacity-40 text-lab-bg font-medium px-5 py-2 rounded-sm hover:brightness-110 transition-[filter]"
          >
            {loading ? "loading…" : "profile dataset"}
          </button>
        </section>

        {error && <p className="text-lab-danger text-sm font-data">{error}</p>}

        {profile && (
          <>
            <section className="border border-lab-border rounded-sm p-6">
              <h2 className="font-display text-base mb-4">Overview</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Stat label="rows" value={profile.n_rows} />
                <Stat label="columns" value={profile.n_cols} />
                <Stat label="duplicate rows" value={profile.duplicate_rows} />
                <Stat label="columns w/ missing" value={Object.keys(profile.missing_values).length} />
              </div>
            </section>

            <section className="border border-lab-border rounded-sm p-6 overflow-x-auto">
              <h2 className="font-display text-base mb-4">Columns</h2>
              <table className="w-full text-sm font-data">
                <thead>
                  <tr className="text-left text-lab-text-faint border-b border-lab-border">
                    <th className="py-2 pr-4 font-normal">column</th>
                    <th className="py-2 pr-4 font-normal">type</th>
                    <th className="py-2 pr-4 font-normal">missing</th>
                    <th className="py-2 pr-4 font-normal">outliers (iqr)</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.columns.map((col) => (
                    <tr key={col} className="border-b border-lab-border/60">
                      <td className="py-2 pr-4 text-lab-text">{col}</td>
                      <td className="py-2 pr-4 text-lab-text-muted">{profile.dtypes[col]}</td>
                      <td className="py-2 pr-4 text-lab-text-muted">
                        {profile.missing_values[col]
                          ? `${profile.missing_values[col]} (${profile.missing_pct[col]}%)`
                          : "\u2014"}
                      </td>
                      <td className="py-2 pr-4 text-lab-text-muted">
                        {profile.outliers_iqr[col] ?? "\u2014"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            {Object.keys(profile.notable_correlations).length > 0 && (
              <section className="border border-lab-border rounded-sm p-6">
                <h2 className="font-display text-base mb-4">
                  Notable correlations (|r| &ge; 0.3)
                </h2>
                <div className="space-y-2 text-sm font-data">
                  {Object.entries(profile.notable_correlations).map(([pair, r]) => (
                    <div key={pair} className="flex justify-between text-lab-text-muted">
                      <span>{pair.replace("~", " \u2194 ")}</span>
                      <span className={r > 0 ? "text-lab-support" : "text-lab-danger"}>{r}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="font-display text-2xl">{value}</div>
      <div className="text-lab-text-faint text-xs font-data mt-1">{label}</div>
    </div>
  );
}
