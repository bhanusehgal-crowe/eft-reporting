const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Run {
  run_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  operator_id: string;
  started_at: string | null;
  completed_at: string | null;
  parameters?: Record<string, unknown>;
}

export interface ReconciliationResult {
  result_id: string;
  status: "MATCHED" | "MISSED" | "PHANTOM";
  eft_transaction_id: string | null;
  reported_id: string | null;
  match_method: string | null;
  variance_amount: number | null;
  detail: Record<string, unknown>;
}

export interface RuleFinding {
  finding_id: string;
  rule_code: string;
  rule_version: number;
  severity: "INFO" | "WARN" | "BREACH";
  transaction_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface ReperformanceResult {
  result_id: string;
  calculation_type: string;
  status: "PASS" | "VARIANCE" | "BREACH";
  reported_value: number | null;
  reperformed_value: number | null;
  variance_absolute: number | null;
  variance_pct: number | null;
  detail: Record<string, unknown>;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  getRuns: () => apiFetch<Run[]>("/runs"),
  getRun: (runId: string) => apiFetch<Run>(`/runs/${runId}`),
  createRun: (eftFile: string, reportedFile: string, operatorId: string) =>
    apiFetch<{ run_id: string; status: string }>("/runs", {
      method: "POST",
      headers: { "X-Operator-ID": operatorId },
      body: JSON.stringify({ eft_file: eftFile, reported_file: reportedFile }),
    }),
  getReconciliation: (runId: string, status?: string, page = 1) =>
    apiFetch<{ total: number; results: ReconciliationResult[] }>(
      `/runs/${runId}/reconciliation?page=${page}${status ? `&status=${status}` : ""}`
    ),
  getFindings: (runId: string, severity?: string, page = 1) =>
    apiFetch<{ total: number; findings: RuleFinding[] }>(
      `/runs/${runId}/findings?page=${page}${severity ? `&severity=${severity}` : ""}`
    ),
  getReperformance: (runId: string) =>
    apiFetch<{ results: ReperformanceResult[] }>(`/runs/${runId}/reperformance`),
  getMissedTransactionsUrl: (runId: string) =>
    `${API_BASE}/reports/${runId}/missed-transactions`,
};
