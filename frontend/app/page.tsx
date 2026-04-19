"use client";

import Link from "next/link";
import { Activity, ArrowDown, ArrowUp, DatabaseZap, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Risk, api } from "@/lib/api";

export default function Dashboard() {
  const [risks, setRisks] = useState<Risk[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setRisks(await api.risks());
    setLoading(false);
  }

  useEffect(() => {
    load().catch((err) => {
      setError(err.message);
      setLoading(false);
    });
  }, []);

  async function fetchSignals(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await api.fetchSignals(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signal fetch failed");
    } finally {
      setBusyId(null);
    }
  }

  const activity = useMemo(
    () =>
      risks
        .filter((risk) => risk.status !== "current")
        .map((risk) => `AI suggested update based on CrustData signal for ${risk.name}`),
    [risks]
  );

  return (
    <main className="min-h-screen bg-[#f7f8f4]">
      <section className="border-b border-[#d9ded2] bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-6 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded border border-moss/25 bg-mint px-3 py-1 text-sm font-semibold text-moss">
              <DatabaseZap size={16} />
              Source: CrustData API
            </div>
            <h1 className="text-3xl font-semibold tracking-normal text-ink md:text-5xl">GRC Risk Intelligence</h1>
            <p className="mt-3 max-w-2xl text-base text-[#546259]">
              Human-reviewed AI proposals for vendor risk changes, backed by live external signal ingestion.
            </p>
          </div>
          <button
            onClick={() => load()}
            className="inline-flex h-11 items-center justify-center gap-2 rounded border border-[#b7c1b4] bg-white px-4 text-sm font-semibold text-ink hover:bg-[#eef4ec]"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[1fr_360px]">
        <div className="overflow-hidden rounded border border-[#d9ded2] bg-white">
          <div className="grid grid-cols-[1.4fr_120px_120px_120px_160px] border-b border-[#d9ded2] bg-[#eef3ea] px-4 py-3 text-sm font-semibold text-[#445149]">
            <span>Risk</span>
            <span>Current</span>
            <span>Proposed</span>
            <span>Status</span>
            <span>Action</span>
          </div>
          {loading ? (
            <div className="p-6 text-[#546259]">Loading risks...</div>
          ) : (
            risks.map((risk) => {
              const delta = (risk.proposed_score ?? risk.current_score) - risk.current_score;
              const increase = delta > 0;
              return (
                <div
                  key={risk.id}
                  className="grid grid-cols-[1.4fr_120px_120px_120px_160px] items-center border-b border-[#edf0e9] px-4 py-4 last:border-b-0"
                >
                  <Link href={`/risks/${risk.id}`} className="font-semibold text-ink hover:text-moss">
                    {risk.name}
                    <span className="block text-sm font-normal text-[#6b766f]">{risk.vendor_id}</span>
                  </Link>
                  <span className="font-mono text-sm">{risk.current_score.toFixed(1)}</span>
                  <span className={`inline-flex items-center gap-1 font-mono text-sm ${increase ? "text-coral" : "text-moss"}`}>
                    {delta === 0 ? null : increase ? <ArrowUp size={16} /> : <ArrowDown size={16} />}
                    {risk.proposed_score?.toFixed(1) ?? "-"}
                  </span>
                  <span className="text-sm capitalize text-[#546259]">{risk.status}</span>
                  <button
                    onClick={() => fetchSignals(risk.id)}
                    disabled={busyId === risk.id}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded bg-ink px-3 text-sm font-semibold text-white hover:bg-moss disabled:cursor-wait disabled:bg-[#8f9a92]"
                  >
                    <Activity size={16} />
                    {busyId === risk.id ? "Fetching" : "Fetch External Signals"}
                  </button>
                </div>
              );
            })
          )}
        </div>

        <aside className="rounded border border-[#d9ded2] bg-white p-5">
          <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-ink">
            <ShieldCheck size={20} />
            Activity Feed
          </div>
          {error ? <div className="mb-3 rounded border border-coral/40 bg-coral/10 p-3 text-sm text-coral">{error}</div> : null}
          <div className="space-y-3">
            {activity.length ? (
              activity.map((item) => (
                <div key={item} className="rounded border border-[#e4e8df] bg-[#fbfcf8] p-3 text-sm text-[#445149]">
                  {item}
                </div>
              ))
            ) : (
              <p className="text-sm text-[#6b766f]">Click Fetch External Signals to start the investor demo flow.</p>
            )}
          </div>
        </aside>
      </section>
    </main>
  );
}

