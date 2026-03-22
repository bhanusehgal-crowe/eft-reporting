"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ReperformanceResult } from "../../lib/api";

const STATUS_COLOR: Record<string, string> = {
  PASS: "bg-green-100 text-green-800",
  VARIANCE: "bg-yellow-100 text-yellow-800",
  BREACH: "bg-red-100 text-red-800",
};

export default function ReperformancePage() {
  const params = useSearchParams();
  const runId = params.get("run") ?? "";
  const [results, setResults] = useState<ReperformanceResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    api.getReperformance(runId)
      .then((r) => setResults(r.results))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  if (!runId) return <div className="p-8 text-gray-500">Select a run from the overview.</div>;
  if (loading) return <div className="p-8 text-gray-500">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Reperformance Results</h1>
      <p className="text-gray-500 text-sm mb-6">Run: {runId}</p>

      <p className="text-sm text-gray-500 mb-4">{results.length} result(s)</p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border rounded-lg overflow-hidden">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Reported</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Reperformed</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Variance ($)</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Variance (%)</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No reperformance results found. Run Phase 2 to generate them.
                </td>
              </tr>
            )}
            {results.map((r) => (
              <tr key={r.result_id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLOR[r.status] ?? ""}`}>
                    {r.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs">{r.calculation_type}</td>
                <td className="px-4 py-3 text-xs">
                  {r.reported_value != null ? r.reported_value.toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3 text-xs">
                  {r.reperformed_value != null ? r.reperformed_value.toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3 text-xs">
                  {r.variance_absolute != null ? r.variance_absolute.toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3 text-xs">
                  {r.variance_pct != null ? `${(r.variance_pct * 100).toFixed(2)}%` : "—"}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                  {JSON.stringify(r.detail)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
