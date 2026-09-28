"use client";

import { useMemo } from "react";
import { Hypothesis, Evidence } from "@/lib/api";

/**
 * Renders the evidence graph (spec section 14): each hypothesis as a
 * central node with its supporting evidence as satellite nodes connected
 * by lines. Plain SVG with a simple radial layout -- no charting library
 * dependency, so this has zero extra install surface.
 */
export function EvidenceGraph({
  hypotheses,
  evidence,
}: {
  hypotheses: Hypothesis[];
  evidence: Evidence[];
}) {
  const layout = useMemo(() => {
    const width = 900;
    const rowHeight = 200;
    const height = Math.max(240, hypotheses.length * rowHeight + 40);

    const nodes = hypotheses.map((h, i) => {
      const evList = evidence.filter((e) => (h.evidence_ids || []).includes(e.id));
      const cy = 60 + i * rowHeight + rowHeight / 2 - 40;
      const cx = 130;
      const evPositions = evList.map((e, j) => {
        const spread = evList.length > 1 ? 140 : 0;
        const y = cy - spread / 2 + (spread / Math.max(evList.length - 1, 1)) * j;
        return { evidence: e, x: 480, y: evList.length === 1 ? cy : y };
      });
      return { hypothesis: h, cx, cy, evPositions };
    });

    return { width, height, nodes };
  }, [hypotheses, evidence]);

  if (hypotheses.length === 0) {
    return <p className="text-sm text-zinc-500">No hypotheses to visualize yet.</p>;
  }

  const statusColor: Record<string, string> = {
    SUPPORTED: "#8fb996",
    PARTIALLY_SUPPORTED: "#d1a15a",
    REJECTED: "#d17b72",
    INSUFFICIENT_EVIDENCE: "#d17b72",
    PROPOSED: "#5a6270",
  };

  return (
    <svg
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      className="w-full"
      style={{ minHeight: 240, fontFamily: "var(--font-data)" }}
    >
      {layout.nodes.map(({ hypothesis, cx, cy, evPositions }) => (
        <g key={hypothesis.id}>
          {evPositions.map(({ evidence: e, x, y }) => (
            <line
              key={e.id}
              x1={cx + 110}
              y1={cy}
              x2={x - 90}
              y2={y}
              stroke="#262d38"
              strokeWidth={1.5}
            />
          ))}

          {/* hypothesis node */}
          <rect
            x={cx - 110}
            y={cy - 30}
            width={220}
            height={60}
            rx={3}
            fill="#171c24"
            stroke={statusColor[hypothesis.status] || "#5a6270"}
            strokeWidth={2}
          />
          <text x={cx} y={cy - 8} textAnchor="middle" fontSize={11} fill="#e4e7ec">
            {truncate(hypothesis.statement, 34)}
          </text>
          <text
            x={cx}
            y={cy + 12}
            textAnchor="middle"
            fontSize={10}
            fill={statusColor[hypothesis.status] || "#8992a3"}
            fontWeight="bold"
          >
            {hypothesis.status}
          </text>

          {/* evidence nodes */}
          {evPositions.map(({ evidence: e, x, y }) => (
            <g key={e.id}>
              <rect
                x={x - 90}
                y={y - 22}
                width={180}
                height={44}
                rx={3}
                fill="#10141a"
                stroke="#262d38"
              />
              <text x={x} y={y - 6} textAnchor="middle" fontSize={9} fill="#8992a3">
                [{e.kind}]
              </text>
              <text x={x} y={y + 10} textAnchor="middle" fontSize={9} fill="#e4e7ec">
                {truncate(e.description, 30)}
              </text>
            </g>
          ))}
        </g>
      ))}
    </svg>
  );
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "\u2026" : s;
}
