export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface Hypothesis {
  id: string;
  statement: string;
  rationale: string;
  evidence_ids: string[];
  status: string;
  confidence: string;
}

export interface CriticFinding {
  id: string;
  severity: string;
  issue: string;
  detail: string;
}

export interface Evidence {
  id: string;
  kind: string;
  description: string;
  source: string;
  payload: Record<string, unknown>;
  strength: number;
}

export interface InvestigationResult {
  id: string;
  status: string;
  plan: string[];
  log: string[];
  hypotheses: Hypothesis[];
  evidence: Evidence[];
  critic_findings: CriticFinding[];
  report_markdown: string;
}

export interface ChatReply {
  conversation_id: string;
  answer: string;
  history: { role: "user" | "assistant"; content: string }[];
}

export async function sendReportChat(
  prompt: string,
  conversationId: string | null,
  reportContext: string
): Promise<ChatReply> {
  const res = await fetch(`${API_URL}/chatbot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      conversation_id: conversationId,
      report_context: reportContext,
    }),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const payload = await res.json();
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Keep the HTTP status message if the server did not return JSON.
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function downloadSalesReport(datasetPath: string, reportContext: string): Promise<Blob> {
  const res = await fetch(`${API_URL}/generate-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_path: datasetPath, report_context: reportContext }),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const payload = await res.json();
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Keep the HTTP status message if the server did not return JSON.
    }
    throw new Error(detail);
  }
  return res.blob();
}

export interface InvestigationSummary {
  id: string;
  question: string;
  status: string;
  created_at: string;
}

export async function startInvestigation(
  question: string,
  datasetPaths: string[],
  documentPaths: string[] = []
): Promise<InvestigationResult> {
  const res = await fetch(`${API_URL}/investigations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      dataset_paths: datasetPaths,
      document_paths: documentPaths,
    }),
  });
  if (!res.ok) {
    throw new Error(`Investigation failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function listInvestigations(token?: string): Promise<InvestigationSummary[]> {
  const res = await fetch(`${API_URL}/investigations`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Failed to list investigations");
  return res.json();
}

export interface DatasetProfile {
  path: string;
  n_rows: number;
  n_cols: number;
  columns: string[];
  dtypes: Record<string, string>;
  numeric_cols: string[];
  categorical_cols: string[];
  missing_values: Record<string, number>;
  missing_pct: Record<string, number>;
  duplicate_rows: number;
  outliers_iqr: Record<string, number>;
  summary_stats: Record<string, Record<string, number>>;
  notable_correlations: Record<string, number>;
}

export async function getDatasetProfile(path: string): Promise<DatasetProfile> {
  const res = await fetch(`${API_URL}/datasets/profile?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`Failed to profile dataset: ${res.status}`);
  return res.json();
}

export interface AdminStats {
  total_investigations: number;
  status_breakdown: Record<string, number>;
  avg_runtime_s: number | null;
  avg_agent_timings_s: Record<string, number>;
  avg_revision_cycles: number | null;
  investigations_with_critic_findings_pct: number | null;
}

export async function getAdminStats(): Promise<AdminStats> {
  const res = await fetch(`${API_URL}/admin/stats`);
  if (!res.ok) throw new Error("Failed to load admin stats");
  return res.json();
}

export interface StreamCallbacks {
  onLog: (line: string) => void;
  onResult: (result: InvestigationResult) => void;
  onError: (err: string) => void;
}

/** Live investigation run via SSE (spec section 19 -- "live investigation activity"). */
export function streamInvestigation(
  question: string,
  datasetPaths: string[],
  documentPaths: string[],
  callbacks: StreamCallbacks
): () => void {
  const params = new URLSearchParams({
    question,
    dataset_paths: datasetPaths.join(","),
    document_paths: documentPaths.join(","),
  });
  const source = new EventSource(`${API_URL}/investigations/stream?${params.toString()}`);

  source.addEventListener("log", (e) => callbacks.onLog((e as MessageEvent).data));
  source.addEventListener("result", (e) => {
    callbacks.onResult(JSON.parse((e as MessageEvent).data));
    source.close();
  });
  source.addEventListener("failure", (e) => {
    callbacks.onError((e as MessageEvent).data || "Investigation failed on the server");
    source.close();
  });
  source.onerror = () => {
    callbacks.onError("Connection to the API was interrupted before the investigation completed");
    source.close();
  };

  return () => source.close();
}
