"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, RuleFinding } from "../../lib/api";

const SEVERITY_COLOR: Record<string, string> = {
  BREACH: "bg-red-100 text-red-800",
  WARN: "bg-yellow-100 text-yellow-800",
  INFO: "bg-blue-100 text-blue-800",
};

const SEVERITIES = ["", "BREACH", "WARN", "INFO"] as const;

export default function FindingsPage() {
  const params = useSearchParams();
  const runId = params.get("run") ?? "";
  const [findings, setFindings] = useState<RuleFinding[]>([]);
  const [total, setTotal] = useState(0);
  const [severity, setSeverity] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    api.getFindings(runId, severity || undefined)
      .then((r) => { setFindings(r.findings); setTotal(r.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId, severity]);

  if (!runId) return <div className="p-8 text-gray-500">Select a run from the overview.</div>;

  return (
    <main className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Rule Findings</h1>
          <p className="text-gray-500 text-sm">Run: {runId}</p>
        </div>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All Severities</option>
          {SEVERITIES.filter(Boolean).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-600">Error: {error}</div>}
      {!loading && !error && (
        <>
          <p className="text-sm text-gray-500 mb-4">{total} finding(s)</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border rounded-lg overflow-hidden">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Severity</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Rule</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Version</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Transaction ID</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Detail</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {findings.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                      No findings for this filter.
                    </td>
                  </tr>
                )}
                {findings.map((f) => (
                  <tr key={f.finding_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${SEVERITY_COLOR[f.severity] ?? ""}`}>
                        {f.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{f.rule_code}</td>
                    <td className="px-4 py-3 text-xs">v{f.rule_version}</td>
                    <td className="px-4 py-3 font-mono text-xs">{f.transaction_id ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                      {(f.detail as Record<string, unknown>)?.reason as string ?? JSON.stringify(f.detail)}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {new Date(f.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
