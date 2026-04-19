"use client";

import Link from "next/link";
import { ArrowDown, ArrowLeft, ArrowUp, Check, DatabaseZap, X } from "lucide-react";
import { use, useCallback, useEffect, useState } from "react";
import { RiskDetail, api } from "@/lib/api";

export default function RiskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [risk, setRisk] = useState<RiskDetail | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRisk(await api.risk(id));
  }, [id]);

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [load]);

  async function action(kind: "approve" | "reject") {
    setBusy(kind);
    setError(null);
    try {
      setRisk(kind === "approve" ? await api.approve(id) : await api.reject(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  if (!risk) {
    return <main className="min-h-screen bg-[#f7f8f4] p-8 text-ink">Loading risk detail...</main>;
  }

  const delta = (risk.proposed_score ?? risk.current_score) - risk.current_score;

  return (
    <main className="min-h-screen bg-[#f7f8f4]">
      <section className="border-b border-[#d9ded2] bg-white">
        <div className="mx-auto max-w-7xl px-6 py-6">
          <Link href="/risk-intelligence" className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-moss hover:text-ink">
            <ArrowLeft size={16} />
            Risk Intelligence Scan
          </Link>
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded border border-moss/25 bg-mint px-3 py-1 text-sm font-semibold text-moss">
                <DatabaseZap size={16} />
                Source: CrustData API
              </div>
              <h1 className="text-3xl font-semibold text-ink">{risk.name}</h1>
              <p className="mt-2 text-[#546259]">{risk.vendor_id}</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => action("approve")}
                disabled={busy !== null || risk.proposed_score === null}
                className="inline-flex h-11 items-center gap-2 rounded bg-moss px-4 text-sm font-semibold text-white hover:bg-ink disabled:bg-[#9da89f]"
              >
                <Check size={17} />
                Approve
              </button>
              <button
                onClick={() => action("reject")}
                disabled={busy !== null || risk.proposed_score === null}
                className="inline-flex h-11 items-center gap-2 rounded border border-coral px-4 text-sm font-semibold text-coral hover:bg-coral hover:text-white disabled:border-[#c7ccc5] disabled:text-[#8f9a92]"
              >
                <X size={17} />
                Reject
              </button>
            </div>
          </div>
          {error ? <div className="mt-4 rounded border border-coral/40 bg-coral/10 p-3 text-sm text-coral">{error}</div> : null}
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[360px_1fr]">
        <div className="space-y-6">
          <div className="rounded border border-[#d9ded2] bg-white p-5">
            <h2 className="mb-4 text-lg font-semibold text-ink">Score Proposal</h2>
            <div className="grid grid-cols-2 gap-3">
              <Metric label="Current" value={risk.current_score.toFixed(1)} />
              <Metric label="Proposed" value={risk.proposed_score?.toFixed(1) ?? "-"} />
            </div>
            <div className={`mt-4 inline-flex items-center gap-2 text-sm font-semibold ${delta > 0 ? "text-coral" : "text-moss"}`}>
              {delta > 0 ? <ArrowUp size={16} /> : <ArrowDown size={16} />}
              {delta > 0 ? "Proposed Risk Increase" : "Proposed Risk Decrease"}
            </div>
          </div>

          <div className="rounded border border-[#d9ded2] bg-white p-5">
            <h2 className="mb-3 text-lg font-semibold text-ink">Explanation</h2>
            <p className="whitespace-pre-line text-sm leading-6 text-[#445149]">{risk.explanation ?? "No AI explanation yet."}</p>
          </div>

          <div className="rounded border border-[#d9ded2] bg-white p-5">
            <h2 className="mb-3 text-lg font-semibold text-ink">Actions To be Taken</h2>
            <div className="min-h-28 rounded border border-dashed border-[#cbd3c7] bg-[#fbfcf8]" />
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded border border-[#d9ded2] bg-white">
            <div className="border-b border-[#d9ded2] px-5 py-4 text-lg font-semibold text-ink">Signals</div>
            <div className="grid grid-cols-[1fr_120px_120px_120px] border-b border-[#e4e8df] bg-[#eef3ea] px-5 py-3 text-sm font-semibold text-[#445149]">
              <span>Type</span>
              <span>Source</span>
              <span>Value</span>
              <span>Confidence</span>
            </div>
            {risk.signals.map((signal) => (
              <div key={signal.id} className="border-b border-[#edf0e9] px-5 py-3 text-sm last:border-b-0">
                <div className="grid grid-cols-[1fr_120px_120px_120px]">
                  <span className="font-semibold text-ink">{signal.signal_type}</span>
                  <span className="text-moss">{signal.source}</span>
                  <span className="font-mono">{signal.value.toFixed(2)}</span>
                  <span className="font-mono">{signal.confidence.toFixed(2)}</span>
                </div>
                <SelectedEvidence metadata={signal.metadata_} />
              </div>
            ))}
          </div>

          <div className="rounded border border-[#d9ded2] bg-white">
            <div className="border-b border-[#d9ded2] px-5 py-4 text-lg font-semibold text-ink">Audit Log</div>
            {risk.audit_logs.map((log) => (
              <div key={log.id} className="border-b border-[#edf0e9] px-5 py-4 text-sm last:border-b-0">
                <div className="font-semibold text-ink">Based on CrustData API signal</div>
                <div className="mt-1 text-[#546259]">
                  {log.previous_score.toFixed(1)} to {log.new_score.toFixed(1)} | {log.source} | {new Date(log.timestamp).toLocaleString()}
                </div>
                <p className="mt-2 line-clamp-3 text-[#445149]">{log.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[#e4e8df] bg-[#fbfcf8] p-4">
      <div className="text-sm text-[#6b766f]">{label}</div>
      <div className="mt-1 font-mono text-3xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function SelectedEvidence({ metadata }: { metadata: Record<string, unknown> }) {
  const fields = metadata.selected_crustdata_fields;
  const reason = metadata.ai_selected_reason;

  if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
    return null;
  }

  return (
    <div className="mt-3 rounded border border-[#e4e8df] bg-[#fbfcf8] p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-[#6b766f]">AI-selected CrustData evidence</div>
      <div className="grid gap-2 md:grid-cols-2">
        {Object.entries(fields as Record<string, unknown>).map(([key, value]) => (
          <div key={key} className="rounded border border-[#edf0e9] bg-white px-3 py-2">
            <div className="text-[11px] uppercase text-[#6b766f]">{key}</div>
            <div className="mt-1 break-words font-mono text-xs text-ink">{formatEvidenceValue(value)}</div>
          </div>
        ))}
      </div>
      {typeof reason === "string" ? <p className="mt-3 text-xs leading-5 text-[#445149]">{reason}</p> : null}
    </div>
  );
}

function formatEvidenceValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "not reported";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
  }
  return String(value);
}
