"use client";

import { useEffect, useState } from "react";
import { api, Run } from "../lib/api";

const STATUS_COLOR: Record<string, string> = {
  COMPLETED: "bg-green-100 text-green-800",
  RUNNING: "bg-blue-100 text-blue-800",
  PENDING: "bg-yellow-100 text-yellow-800",
  FAILED: "bg-red-100 text-red-800",
};

export default function OverviewPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-gray-500">Loading runs...</div>;
  if (error) return <div className="p-8 text-red-600">Error: {error}</div>;

  return (
    <main className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">EFTR Regulatory Assurance</h1>
      <p className="text-gray-500 mb-6">FINTRAC compliance run history</p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border rounded-lg overflow-hidden">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Run ID</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Operator</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Started</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Completed</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No runs found. Run the pipeline to see results.
                </td>
              </tr>
            )}
            {runs.map((run) => (
              <tr key={run.run_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs">{run.run_id.slice(0, 8)}…</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLOR[run.status] ?? ""}`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-3">{run.operator_id}</td>
                <td className="px-4 py-3 text-xs">
                  {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3 text-xs">
                  {run.completed_at ? new Date(run.completed_at).toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3 space-x-2 text-xs">
                  <a href={`/missed?run=${run.run_id}`} className="text-blue-600 hover:underline">
                    Missed
                  </a>
                  <a href={`/findings?run=${run.run_id}`} className="text-blue-600 hover:underline">
                    Findings
                  </a>
                  <a href={`/reperformance?run=${run.run_id}`} className="text-blue-600 hover:underline">
                    Reperformance
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
