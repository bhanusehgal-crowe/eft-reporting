"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ReconciliationResult } from "../../lib/api";

const STATUS_COLOR: Record<string, string> = {
  MISSED: "bg-red-100 text-red-800",
  PHANTOM: "bg-orange-100 text-orange-800",
  MATCHED: "bg-green-100 text-green-800",
};

export default function MissedPage() {
  const params = useSearchParams();
  const runId = params.get("run") ?? "";
  const [results, setResults] = useState<ReconciliationResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    api.getReconciliation(runId, "MISSED")
      .then((r) => { setResults(r.results); setTotal(r.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  if (!runId) return <div className="p-8 text-gray-500">Select a run from the overview.</div>;
  if (loading) return <div className="p-8 text-gray-500">Loading...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Missed Transactions</h1>
          <p className="text-gray-500 text-sm">Run: {runId}</p>
        </div>
        <a
          href={api.getMissedTransactionsUrl(runId)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
        >
          Download Excel
        </a>
      </div>

      <p className="text-sm text-gray-500 mb-4">{total} missed transaction(s)</p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border rounded-lg overflow-hidden">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">EFT Transaction ID</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Match Method</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Variance</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  No missed transactions found.
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
                <td className="px-4 py-3 font-mono text-xs">{r.eft_transaction_id ?? "—"}</td>
                <td className="px-4 py-3 text-xs">{r.match_method ?? "—"}</td>
                <td className="px-4 py-3 text-xs">
                  {r.variance_amount != null ? `CAD ${r.variance_amount.toLocaleString()}` : "—"}
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
