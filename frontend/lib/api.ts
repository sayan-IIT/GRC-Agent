export type Risk = {
  id: string;
  name: string;
  vendor_id: string;
  current_score: number;
  proposed_score: number | null;
  confidence: number | null;
  status: string;
  explanation: string | null;
  updated_at: string;
};

export type Signal = {
  id: string;
  risk_id: string;
  signal_type: string;
  source: string;
  value: number;
  confidence: number;
  freshness: number;
  timestamp: string;
  metadata_: Record<string, unknown>;
};

export type AuditLog = {
  id: string;
  risk_id: string;
  previous_score: number;
  new_score: number;
  explanation: string;
  source: string;
  signals_used: Record<string, unknown>[];
  model_version: string;
  timestamp: string;
};

export type RiskDetail = Risk & {
  signals: Signal[];
  audit_logs: AuditLog[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

export const api = {
  risks: () => request<Risk[]>("/risks"),
  risk: (id: string) => request<RiskDetail>(`/risks/${id}`),
  fetchSignals: (id: string) => request<RiskDetail>(`/risks/${id}/fetch-external-signals`, { method: "POST" }),
  approve: (id: string) => request<RiskDetail>(`/risks/${id}/approve`, { method: "POST" }),
  reject: (id: string) => request<RiskDetail>(`/risks/${id}/reject`, { method: "POST" })
};

