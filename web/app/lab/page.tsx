"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import {
  downloadSalesReport,
  sendReportChat,
  streamInvestigation,
  InvestigationResult,
} from "@/lib/api";
import { Badge } from "@/components/Badge";
import { EvidenceGraph } from "@/components/EvidenceGraph";
import { TaskGraph } from "@/components/TaskGraph";

type ChatMessage = { role: "user" | "assistant"; content: string };

function reportContext(result: InvestigationResult): string {
  const hypotheses = result.hypotheses
    .map((item) => `- ${item.status} (${item.confidence}): ${item.statement}. ${item.rationale}`)
    .join("\n");
  const critiques = result.critic_findings
    .map((item) => `- ${item.severity} ${item.issue}: ${item.detail}`)
    .join("\n");
  return [
    "INVESTIGATION REPORT",
    result.report_markdown,
    "HYPOTHESES",
    hypotheses || "No hypotheses were recorded.",
    "CRITIC REVIEW",
    critiques || "No critic findings were recorded.",
  ].join("\n\n").slice(0, 11500);
}

export default function LabPage() {
  const [question, setQuestion] = useState(
    "Why did revenue decrease, and what should the company do?"
  );
  const [datasets, setDatasets] = useState("sample_data/sales.csv");
  const [documents, setDocuments] = useState("");
  const [running, setRunning] = useState(false);
  const [liveLog, setLiveLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [chatPrompt, setChatPrompt] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatConversationId, setChatConversationId] = useState<string | null>(null);
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const closeStreamRef = useRef<(() => void) | null>(null);

  function handleRun() {
    setRunning(true);
    setError(null);
    setResult(null);
    setLiveLog([]);
    setChatMessages([]);
    setChatConversationId(null);
    setChatError(null);
    setPdfError(null);

    closeStreamRef.current?.();
    closeStreamRef.current = streamInvestigation(
      question,
      datasets.split(",").map((s) => s.trim()).filter(Boolean),
      documents.split(",").map((s) => s.trim()).filter(Boolean),
      {
        onLog: (line) => setLiveLog((prev) => [...prev, line]),
        onResult: (res) => {
          setResult(res);
          setRunning(false);
        },
        onError: (err) => {
          setError(err);
          setRunning(false);
        },
      }
    );
  }

  async function sendChat(prompt = chatPrompt) {
    const cleanPrompt = prompt.trim();
    if (!result || !cleanPrompt || chatSending) return;

    setChatSending(true);
    setChatError(null);
    setChatPrompt("");
    setChatMessages((previous) => [...previous, { role: "user", content: cleanPrompt }]);
    try {
      const reply = await sendReportChat(
        cleanPrompt,
        chatConversationId,
        reportContext(result)
      );
      setChatConversationId(reply.conversation_id);
      setChatMessages((previous) => [...previous, { role: "assistant", content: reply.answer }]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "Ollama chat request failed");
    } finally {
      setChatSending(false);
    }
  }

  async function exportEnhancedReport() {
    if (!result) return;
    const datasetPath = datasets.split(",").map((path) => path.trim()).filter(Boolean)[0];
    if (!datasetPath) {
      setPdfError("Enter a dataset path before exporting the report.");
      return;
    }
    setPdfDownloading(true);
    setPdfError(null);
    try {
      const blob = await downloadSalesReport(datasetPath, reportContext(result));
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `${datasetPath.split(/[\\/]/).pop()?.replace(/\.[^.]+$/, "") || "sales"}-analysis.pdf`;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : "Report export failed");
    } finally {
      setPdfDownloading(false);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-lab-border px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg">AI Research Lab</h1>
          <p className="text-lab-text-muted text-sm font-data">investigation dashboard</p>
        </div>
        <nav className="flex gap-5 text-sm font-data">
          <Link href="/explorer" className="text-lab-text-muted hover:text-lab-text transition-colors">
            explorer
          </Link>
          <Link href="/admin" className="text-lab-text-muted hover:text-lab-text transition-colors">
            observability
          </Link>
        </nav>
      </header>

      <main className="max-w-4xl mx-auto px-8 py-8 space-y-6">
        <section className="border border-lab-border rounded-sm p-6 space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-lab-text-faint font-data block mb-1.5">
                research question
              </label>
              <input
                className="w-full bg-lab-panel border border-lab-border-strong rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-lab-accent"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-lab-text-faint font-data block mb-1.5">
                dataset path(s), comma separated
              </label>
              <input
                className="w-full bg-lab-panel border border-lab-border-strong rounded-sm px-3 py-2 text-sm font-data focus:outline-none focus:border-lab-accent"
                value={datasets}
                onChange={(e) => setDatasets(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-lab-text-faint font-data block mb-1.5">
              document path(s), optional
            </label>
            <input
              className="w-full bg-lab-panel border border-lab-border-strong rounded-sm px-3 py-2 text-sm font-data focus:outline-none focus:border-lab-accent"
              value={documents}
              onChange={(e) => setDocuments(e.target.value)}
            />
          </div>
          <button
            onClick={handleRun}
            disabled={running}
            className="bg-lab-accent disabled:opacity-40 text-lab-bg font-medium px-5 py-2.5 rounded-sm hover:brightness-110 transition-[filter]"
          >
            {running ? "Running investigation…" : "Start investigation"}
          </button>
          {error && <p className="text-lab-danger text-sm font-data">{error}</p>}
        </section>

        {(running || liveLog.length > 0) && (
          <section className="border border-lab-border rounded-sm p-6">
            <h2 className="font-display text-base mb-3 flex items-center gap-2">
              Live activity
              {running && (
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-lab-accent animate-pulse" />
              )}
            </h2>
            <div className="bg-lab-panel rounded-sm p-4 max-h-64 overflow-auto text-xs font-data text-lab-text-muted space-y-1">
              {liveLog.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          </section>
        )}

        {result && (
          <>
            <section className="border border-lab-border rounded-sm p-6 overflow-x-auto">
              <h2 className="font-display text-base mb-4">Investigation graph</h2>
              <TaskGraph log={result.log} finalStatus={result.status} />
            </section>

            <section className="border border-lab-border rounded-sm p-6">
              <h2 className="font-display text-base mb-3">Hypothesis board</h2>
              {result.hypotheses.length === 0 && (
                <p className="text-sm text-lab-text-muted font-data">
                  No hypotheses could be generated — insufficient evidence in the data.
                </p>
              )}
              <div className="space-y-3">
                {result.hypotheses.map((h) => (
                  <div key={h.id} className="border border-lab-border rounded-sm p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge label={h.status} />
                      <Badge label={h.confidence} />
                    </div>
                    <p className="font-display text-[15px] leading-snug">{h.statement}</p>
                    <p className="text-xs text-lab-text-faint font-data mt-1.5">{h.rationale}</p>
                  </div>
                ))}
              </div>
            </section>

            {result.hypotheses.length > 0 && (
              <section className="border border-lab-border rounded-sm p-6">
                <h2 className="font-display text-base mb-3">Evidence graph</h2>
                <EvidenceGraph hypotheses={result.hypotheses} evidence={result.evidence} />
              </section>
            )}

            <section className="border border-lab-border rounded-sm p-6">
              <h2 className="font-display text-base mb-3">Critic review</h2>
              {result.critic_findings.length === 0 ? (
                <p className="text-sm text-lab-text-muted font-data">No issues raised.</p>
              ) : (
                <div className="space-y-2 font-data text-sm">
                  {result.critic_findings.map((f) => (
                    <div key={f.id}>
                      <Badge label={f.severity} /> <span className="text-lab-text ml-1">{f.issue}:</span>{" "}
                      <span className="text-lab-text-muted">{f.detail}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="border border-lab-border rounded-sm p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-display text-base">Report</h2>
                <button
                  type="button"
                  onClick={exportEnhancedReport}
                  disabled={pdfDownloading}
                  className="text-xs font-data text-lab-accent border border-lab-accent-dim rounded-sm px-3 py-1 hover:brightness-110 disabled:opacity-50"
                >
                  {pdfDownloading ? "building report…" : "export insight PDF"}
                </button>
              </div>
              <pre className="text-xs font-data text-lab-text-muted whitespace-pre-wrap max-h-[500px] overflow-auto bg-lab-panel rounded-sm p-4">
                {result.report_markdown}
              </pre>
              {pdfError && <p className="text-lab-danger text-xs font-data mt-3">{pdfError}</p>}
            </section>

            <section className="border border-lab-border rounded-sm p-6 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-display text-base">Discuss this report</h2>
                  <p className="text-xs text-lab-text-faint font-data mt-1">
                    Ollama llama3 · report, hypotheses, and critique stay in context
                  </p>
                </div>
                <span className="lab-tag text-lab-support border-lab-support-dim">LOCAL MODEL</span>
              </div>

              <div className="flex flex-wrap gap-x-5 gap-y-2 border-y border-lab-border py-3 text-xs font-data">
                {[
                  "What are the strongest findings?",
                  "What if we increase marketing spend?",
                  "How would you improve this analysis?",
                  "What competitor data should we collect?",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    disabled={chatSending}
                    onClick={() => sendChat(suggestion)}
                    className="text-lab-accent hover:text-lab-text disabled:opacity-50 text-left"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>

              <div
                aria-live="polite"
                className="min-h-24 max-h-80 overflow-y-auto space-y-3"
              >
                {chatMessages.length === 0 ? (
                  <p className="text-sm text-lab-text-muted py-4">
                    Ask about the report, test a pricing or marketing what-if, or explore the next analysis step.
                  </p>
                ) : chatMessages.map((message, index) => (
                  <div
                    key={`${index}-${message.role}`}
                    className={`border-l-2 pl-3 py-1 ${message.role === "assistant" ? "border-lab-support" : "border-lab-accent-dim"}`}
                  >
                    <p className="text-[10px] font-data uppercase text-lab-text-faint mb-1">
                      {message.role === "assistant" ? "ollama llama3" : "you"}
                    </p>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
                  </div>
                ))}
                {chatSending && <p className="text-xs font-data text-lab-text-faint">llama3 is reading the report…</p>}
              </div>

              {chatError && <p className="text-lab-danger text-xs font-data">{chatError}</p>}
              <form
                className="flex flex-col sm:flex-row gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void sendChat();
                }}
              >
                <input
                  value={chatPrompt}
                  onChange={(event) => setChatPrompt(event.target.value)}
                  placeholder="Ask a follow-up about this report…"
                  aria-label="Ask Ollama llama3 about this report"
                  className="min-w-0 flex-1 bg-lab-panel border border-lab-border-strong rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-lab-accent"
                />
                <button
                  type="submit"
                  disabled={chatSending || !chatPrompt.trim()}
                  className="bg-lab-accent disabled:opacity-40 text-lab-bg font-medium px-4 py-2 rounded-sm hover:brightness-110"
                >
                  {chatSending ? "thinking…" : "ask llama3"}
                </button>
              </form>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
