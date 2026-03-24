"use client";

import { useEffect, useRef, useState } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  ShieldAlert, AlertTriangle, FileX, CheckCircle2, Upload,
  LayoutDashboard, ClipboardList, Scale, ScrollText, Menu, X,
  TrendingUp, TrendingDown, ChevronDown,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Colour palette (from screenshot) ──────────────────────────
const C = {
  bg:      "#F0F2F8",
  surface: "#FFFFFF",
  border:  "#E2E8F0",
  text:    "#1E1B4B",
  muted:   "#64748B",
  // KPI gradients
  breach:  ["#EF4444", "#B91C1C"],
  warn:    ["#F97316", "#C2410C"],
  missed:  ["#8B5CF6", "#6D28D9"],
  matched: ["#10B981", "#047857"],
  // Chart colours
  chart:   ["#7C3AED", "#3B82F6", "#F97316", "#10B981", "#EC4899"],
};

// ── Types ───────────────────────────────────────────────────────
interface Run {
  run_id: string; status: string; operator_id: string;
  started_at: string | null; completed_at: string | null;
  parameters?: { summary?: Record<string, number> };
}
interface ReconResult {
  result_id: string; status: string;
  eft_transaction_id: string | null; reported_id: string | null;
  match_method: string | null; variance_amount: number | null;
  detail: Record<string, unknown>;
}
interface Finding {
  finding_id: string; rule_code: string; rule_version: number;
  severity: string; transaction_id: string | null;
  detail: Record<string, unknown>; created_at: string;
}
interface ReperformResult {
  result_id: string; calculation_type: string; status: string;
  reported_value: number | null; reperformed_value: number | null;
  variance_absolute: number | null; variance_pct: number | null;
  detail: Record<string, unknown>;
}
interface AuditEntry {
  log_id: string; event_type: string; severity: string;
  component: string; operator_id: string | null;
  message: string; created_at: string;
}

// ── Helpers ─────────────────────────────────────────────────────
async function apiFetch<T>(path: string): Promise<T> {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}
function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" });
}
function shortId(id: string) { return id.slice(0, 8) + "…"; }

// ── KPI Card ────────────────────────────────────────────────────
function KpiCard({
  label, value, sub, icon: Icon, gradient, trend,
}: {
  label: string; value: number; sub: string;
  icon: React.ElementType; gradient: string[];
  trend?: number;
}) {
  return (
    <div
      className="rounded-2xl p-5 flex flex-col gap-3 shadow-lg"
      style={{ background: `linear-gradient(135deg, ${gradient[0]}, ${gradient[1]})`, color: "#fff" }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium opacity-80 uppercase tracking-wide">{label}</p>
          <p className="text-4xl font-bold mt-1">{value}</p>
        </div>
        <div className="w-11 h-11 rounded-xl flex items-center justify-center"
          style={{ background: "rgba(255,255,255,0.2)" }}>
          <Icon size={22} />
        </div>
      </div>
      <div className="flex items-center gap-2 text-sm opacity-80">
        {trend !== undefined ? (
          <>
            {trend >= 0
              ? <TrendingUp size={14} />
              : <TrendingDown size={14} />}
            <span>{sub}</span>
          </>
        ) : (
          <span>{sub}</span>
        )}
      </div>
    </div>
  );
}

// ── Panel wrapper ────────────────────────────────────────────────
function Panel({ title, children, className = "" }: {
  title: string; children: React.ReactNode; className?: string;
}) {
  return (
    <div
      className={`rounded-2xl shadow-sm border ${className}`}
      style={{ background: C.surface, borderColor: C.border }}
    >
      <div className="px-6 py-4 border-b" style={{ borderColor: C.border }}>
        <h3 className="font-semibold text-sm" style={{ color: C.text }}>{title}</h3>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

// ── Upload Modal ─────────────────────────────────────────────────
const STEPS = [
  "Uploading files", "Ingesting EFT data",
  "Running reconciliation", "Evaluating FINTRAC rules", "Generating report",
];

function UploadModal({
  onClose, onRunCreated,
}: {
  onClose: () => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onRunCreated: (data: any) => void;
}) {
  const [eftFile, setEftFile] = useState<File | null>(null);
  const [repFile, setRepFile] = useState<File | null>(null);
  const [operatorId, setOperatorId] = useState("");
  const [eftDrag, setEftDrag] = useState(false);
  const [repDrag, setRepDrag] = useState(false);
  const [phase, setPhase] = useState<"form" | "running" | "done" | "error">("form");
  const [stepIndex, setStepIndex] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const stepRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const eftRef = useRef<HTMLInputElement>(null);
  const repRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (phase === "running") {
      stepRef.current = setInterval(() => {
        setStepIndex(i => Math.min(i + 1, STEPS.length - 1));
      }, 3000);
    }
    return () => { if (stepRef.current) clearInterval(stepRef.current); };
  }, [phase]);

  async function handleSubmit() {
    if (!eftFile || !repFile || !operatorId.trim()) return;
    setPhase("running"); setStepIndex(0);
    const fd = new FormData();
    fd.append("eft_file", eftFile);
    fd.append("reported_file", repFile);
    fd.append("operator_id", operatorId.trim());
    try {
      const res = await fetch(`${API}/runs/upload`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (stepRef.current) clearInterval(stepRef.current);
      setStepIndex(STEPS.length);
      if (data.status === "FAILED") {
        setErrorMsg(data.error ?? "Pipeline failed.");
        setPhase("error"); return;
      }
      onRunCreated(data);
      setPhase("done");
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Upload failed");
      setPhase("error");
    } finally {
      if (stepRef.current) clearInterval(stepRef.current);
    }
  }

  const dropZone = (
    label: string, file: File | null,
    setFile: (f: File) => void, drag: boolean,
    setDrag: (v: boolean) => void, ref: React.RefObject<HTMLInputElement>
  ) => (
    <div
      onClick={() => ref.current?.click()}
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
      className="rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-colors"
      style={{
        borderColor: drag ? C.chart[0] : C.border,
        background: drag ? "rgba(124,58,237,0.05)" : "#F8FAFC",
      }}
    >
      <input ref={ref} type="file" accept=".csv,.xlsx" className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f); }} />
      <Upload size={24} className="mx-auto mb-2" style={{ color: file ? C.matched[0] : C.muted }} />
      <p className="text-sm font-medium" style={{ color: C.text }}>{label}</p>
      {file
        ? <p className="text-xs mt-1 font-semibold" style={{ color: C.matched[0] }}>{file.name}</p>
        : <p className="text-xs mt-1" style={{ color: C.muted }}>Drag & drop or click to browse</p>}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(15,10,30,0.6)", backdropFilter: "blur(4px)" }}>
      <div className="w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden"
        style={{ background: C.surface }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: C.border }}>
          <div>
            <h2 className="font-bold text-lg" style={{ color: C.text }}>Upload & Run Analysis</h2>
            <p className="text-xs mt-0.5" style={{ color: C.muted }}>EFT + Reported CSV files required</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 hover:bg-gray-100 transition-colors">
            <X size={18} style={{ color: C.muted }} />
          </button>
        </div>

        <div className="p-6">
          {phase === "form" && (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3">
                {dropZone("EFT Transactions CSV", eftFile, setEftFile, eftDrag, setEftDrag, eftRef)}
                {dropZone("Reported Transactions CSV", repFile, setRepFile, repDrag, setRepDrag, repRef)}
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: C.muted }}>
                  OPERATOR ID
                </label>
                <input
                  value={operatorId} onChange={e => setOperatorId(e.target.value)}
                  placeholder="e.g. john.doe@bank.com"
                  className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2"
                  style={{ borderColor: C.border, color: C.text,
                    focusRingColor: C.chart[0] } as React.CSSProperties}
                />
              </div>
              <button
                onClick={handleSubmit}
                disabled={!eftFile || !repFile || !operatorId.trim()}
                className="w-full rounded-xl py-3 text-sm font-semibold text-white transition-opacity"
                style={{
                  background: `linear-gradient(135deg, ${C.missed[0]}, ${C.missed[1]})`,
                  opacity: (!eftFile || !repFile || !operatorId.trim()) ? 0.5 : 1,
                }}
              >
                Run Compliance Analysis
              </button>
            </div>
          )}

          {phase === "running" && (
            <div className="py-4">
              <p className="text-sm font-semibold mb-6 text-center" style={{ color: C.text }}>
                Pipeline running — please wait…
              </p>
              <div className="flex flex-col gap-3">
                {STEPS.map((s, i) => (
                  <div key={s} className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold"
                      style={{
                        background: i < stepIndex ? C.matched[0]
                          : i === stepIndex ? C.chart[0] : C.border,
                        color: i <= stepIndex ? "#fff" : C.muted,
                      }}>
                      {i < stepIndex ? "✓" : i + 1}
                    </div>
                    <span className="text-sm" style={{
                      color: i <= stepIndex ? C.text : C.muted,
                      fontWeight: i === stepIndex ? 600 : 400,
                    }}>{s}</span>
                    {i === stepIndex && (
                      <div className="ml-auto w-4 h-4 rounded-full border-2 border-t-transparent animate-spin"
                        style={{ borderColor: C.chart[0], borderTopColor: "transparent" }} />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {phase === "done" && (
            <div className="py-6 text-center">
              <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                style={{ background: `linear-gradient(135deg, ${C.matched[0]}, ${C.matched[1]})` }}>
                <CheckCircle2 size={32} className="text-white" />
              </div>
              <h3 className="font-bold text-lg mb-1" style={{ color: C.text }}>Analysis Complete</h3>
              <p className="text-sm mb-6" style={{ color: C.muted }}>Results loaded in the dashboard</p>
              <button onClick={onClose}
                className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{ background: `linear-gradient(135deg, ${C.matched[0]}, ${C.matched[1]})` }}>
                View Results
              </button>
            </div>
          )}

          {phase === "error" && (
            <div className="py-6 text-center">
              <div className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                style={{ background: `linear-gradient(135deg, ${C.breach[0]}, ${C.breach[1]})` }}>
                <AlertTriangle size={32} className="text-white" />
              </div>
              <h3 className="font-bold text-lg mb-1" style={{ color: C.text }}>Analysis Failed</h3>
              <p className="text-sm mb-4 max-w-xs mx-auto" style={{ color: C.muted }}>{errorMsg}</p>
              <button onClick={() => setPhase("form")}
                className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{ background: `linear-gradient(135deg, ${C.breach[0]}, ${C.breach[1]})` }}>
                Try Again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Dashboard ───────────────────────────────────────────────
export default function Dashboard() {
  const [page, setPage] = useState("overview");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [apiOnline, setApiOnline] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState("");
  const [runDetail, setRunDetail] = useState<Run | null>(null);
  const [recon, setRecon] = useState<ReconResult[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [reperform, setReperform] = useState<ReperformResult[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [missedFilter, setMissedFilter] = useState("");
  const [findingSevFilter, setFindingSevFilter] = useState("");
  const skipNextFetch = useRef(false);

  async function loadRuns() {
    try { const d = await apiFetch<Run[]>("/runs"); setRuns(d); return d; }
    catch { return []; }
  }

  useEffect(() => {
    (async () => {
      try { await apiFetch("/health"); setApiOnline(true); } catch { setApiOnline(false); }
      const d = await loadRuns();
      if (d.length) setRunId(d[0].run_id);
      setLoading(false);
    })();
  }, []);

  useEffect(() => {
    if (!runId) return;
    if (skipNextFetch.current) { skipNextFetch.current = false; return; }
    setLoading(true);
    Promise.all([
      apiFetch<Run>(`/runs/${runId}`),
      apiFetch<{ results: ReconResult[] }>(`/runs/${runId}/reconciliation?page_size=500`),
      apiFetch<{ findings: Finding[] }>(`/runs/${runId}/findings?page_size=500`),
      apiFetch<{ results: ReperformResult[] }>(`/runs/${runId}/reperformance`),
      apiFetch<{ entries: AuditEntry[] }>(`/runs/${runId}/audit?page_size=500`).catch(() => ({ entries: [] })),
    ]).then(([run, reconData, findData, reperformData, auditData]) => {
      setRunDetail(run);
      setRecon(reconData.results ?? []);
      setFindings(findData.findings ?? []);
      setReperform(reperformData.results ?? []);
      setAudit(auditData.entries ?? []);
    }).finally(() => setLoading(false));
  }, [runId]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function handleRunCreated(data: any) {
    const entry: Run = data.run ?? { run_id: data.run_id, status: data.status, operator_id: "", started_at: null, completed_at: null };
    setRuns(prev => [entry, ...prev.filter(r => r.run_id !== data.run_id)]);
    skipNextFetch.current = true;
    setRunId(data.run_id);
    setRunDetail(entry);
    setRecon(data.reconciliation ?? []);
    setFindings(data.findings ?? []);
    setAudit(data.audit_log ?? []);
    setReperform([]);
    setLoading(false);
    setPage("overview");
  }

  // ── Derived data for charts ────────────────────────────────────
  const breachCount = findings.filter(f => f.severity === "BREACH").length;
  const warnCount   = findings.filter(f => f.severity === "WARN").length;
  const infoCount   = findings.filter(f => f.severity === "INFO").length;
  const matchedCount = recon.filter(r => r.status === "MATCHED").length;
  const missedCount  = recon.filter(r => r.status === "MISSED").length;
  const phantomCount = recon.filter(r => r.status === "PHANTOM").length;

  const severityPie = [
    { name: "BREACH", value: breachCount, color: C.breach[0] },
    { name: "WARN",   value: warnCount,   color: C.warn[0] },
    { name: "INFO",   value: infoCount,   color: C.chart[1] },
  ].filter(d => d.value > 0);

  const reconPie = [
    { name: "MATCHED", value: matchedCount, color: C.matched[0] },
    { name: "MISSED",  value: missedCount,  color: C.breach[0] },
    { name: "PHANTOM", value: phantomCount, color: C.warn[0] },
  ].filter(d => d.value > 0);

  const ruleBar: Record<string, number> = {};
  findings.forEach(f => {
    const k = f.rule_code.replace("FINTRAC_", "");
    ruleBar[k] = (ruleBar[k] ?? 0) + 1;
  });
  const ruleChartData = Object.entries(ruleBar)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count], i) => ({ name, count, fill: C.chart[i % C.chart.length] }));

  // ── Sidebar nav items ──────────────────────────────────────────
  const navItems = [
    { id: "overview",  icon: LayoutDashboard, label: "Overview" },
    { id: "missed",    icon: FileX,           label: "Missed Reports" },
    { id: "findings",  icon: ShieldAlert,     label: "Rule Findings" },
    { id: "reperform", icon: Scale,           label: "Reperformance" },
    { id: "audit",     icon: ScrollText,      label: "Audit Log" },
  ];

  // ── Filtered data ──────────────────────────────────────────────
  const filteredMissed = recon.filter(r =>
    r.status === "MISSED" &&
    (!missedFilter || (r.eft_transaction_id ?? "").toLowerCase().includes(missedFilter.toLowerCase()))
  );
  const filteredFindings = findings.filter(f =>
    (!findingSevFilter || f.severity === findingSevFilter)
  );

  // ── Tooltip ────────────────────────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-xl px-3 py-2 shadow-lg text-xs"
        style={{ background: C.text, color: "#fff" }}>
        <p className="font-semibold mb-1">{label ?? payload[0]?.name}</p>
        {payload.map((p: { name: string; value: number; color: string }, i: number) => (
          <p key={i} style={{ color: p.color ?? "#fff" }}>{p.name}: <strong>{p.value}</strong></p>
        ))}
      </div>
    );
  };

  // ── Severity badge ─────────────────────────────────────────────
  function SevBadge({ sev }: { sev: string }) {
    const cfg: Record<string, { bg: string; text: string }> = {
      BREACH:  { bg: "#FEE2E2", text: "#B91C1C" },
      WARN:    { bg: "#FFEDD5", text: "#C2410C" },
      INFO:    { bg: "#DBEAFE", text: "#1D4ED8" },
      MATCHED: { bg: "#D1FAE5", text: "#047857" },
      MISSED:  { bg: "#FEE2E2", text: "#B91C1C" },
      PHANTOM: { bg: "#FEF3C7", text: "#B45309" },
      COMPLETED: { bg: "#D1FAE5", text: "#047857" },
      FAILED:  { bg: "#FEE2E2", text: "#B91C1C" },
      RUNNING: { bg: "#DBEAFE", text: "#1D4ED8" },
      PENDING: { bg: "#F1F5F9", text: "#475569" },
    };
    const s = cfg[sev] ?? { bg: "#F1F5F9", text: "#475569" };
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold"
        style={{ background: s.bg, color: s.text }}>
        {sev}
      </span>
    );
  }

  // ── Table wrapper ──────────────────────────────────────────────
  function TablePanel({ title, controls, children }: {
    title: string; controls?: React.ReactNode; children: React.ReactNode;
  }) {
    return (
      <div className="rounded-2xl shadow-sm border overflow-hidden"
        style={{ background: C.surface, borderColor: C.border }}>
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: C.border }}>
          <h3 className="font-semibold text-sm" style={{ color: C.text }}>{title}</h3>
          {controls && <div className="flex gap-2">{controls}</div>}
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="w-full text-sm">
            {children}
          </table>
        </div>
      </div>
    );
  }

  function Th({ children }: { children: React.ReactNode }) {
    return (
      <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide"
        style={{ color: C.muted, background: "#F8FAFC", borderBottom: `1px solid ${C.border}` }}>
        {children}
      </th>
    );
  }
  function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
    return (
      <td className={`px-4 py-3 border-b text-sm ${className}`}
        style={{ color: C.text, borderColor: C.border }}>
        {children}
      </td>
    );
  }
  function EmptyRow({ cols, msg }: { cols: number; msg: string }) {
    return (
      <tr><td colSpan={cols} className="text-center py-10 text-sm" style={{ color: C.muted }}>{msg}</td></tr>
    );
  }

  // ── SIDEBAR ────────────────────────────────────────────────────
  const sidebar = (
    <aside
      className="fixed left-0 top-0 h-screen z-30 flex flex-col transition-all duration-300"
      style={{
        width: sidebarOpen ? 240 : 72,
        background: C.text,
        borderRight: `1px solid rgba(255,255,255,0.1)`,
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b" style={{ borderColor: "rgba(255,255,255,0.1)" }}>
        <div className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm flex-shrink-0"
          style={{ background: `linear-gradient(135deg, ${C.missed[0]}, ${C.missed[1]})`, color: "#fff" }}>
          EF
        </div>
        {sidebarOpen && (
          <div>
            <p className="text-white font-bold text-sm leading-tight">EFTR</p>
            <p className="text-xs leading-tight" style={{ color: "rgba(255,255,255,0.5)" }}>Compliance</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 flex flex-col gap-1 px-2">
        {navItems.map(item => {
          const active = page === item.id;
          return (
            <button key={item.id} onClick={() => setPage(item.id)}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 w-full text-left transition-colors"
              style={{
                background: active ? "rgba(139,92,246,0.2)" : "transparent",
                color: active ? C.missed[0] : "rgba(255,255,255,0.6)",
              }}>
              <item.icon size={18} className="flex-shrink-0" />
              {sidebarOpen && <span className="text-sm font-medium">{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* API status */}
      {sidebarOpen && (
        <div className="px-4 py-4 border-t" style={{ borderColor: "rgba(255,255,255,0.1)" }}>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ background: apiOnline ? C.matched[0] : C.breach[0] }} />
            <span className="text-xs" style={{ color: "rgba(255,255,255,0.5)" }}>
              API {apiOnline ? "Connected" : "Offline"}
            </span>
          </div>
        </div>
      )}
    </aside>
  );

  const contentOffset = sidebarOpen ? 240 : 72;

  // ── HEADER ─────────────────────────────────────────────────────
  const header = (
    <header
      className="fixed top-0 right-0 z-20 h-16 flex items-center justify-between px-6 border-b"
      style={{
        left: contentOffset, background: C.surface,
        borderColor: C.border, transition: "left 300ms",
      }}
    >
      <div className="flex items-center gap-3">
        <button onClick={() => setSidebarOpen(v => !v)}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
          <Menu size={18} style={{ color: C.muted }} />
        </button>
        <div>
          <h1 className="font-bold text-base" style={{ color: C.text }}>
            {navItems.find(n => n.id === page)?.label ?? "Dashboard"}
          </h1>
          <p className="text-xs" style={{ color: C.muted }}>FINTRAC EFT Compliance Platform</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Run selector */}
        {runs.length > 0 && (
          <div className="relative flex items-center gap-2 rounded-xl border px-3 py-2 text-xs"
            style={{ borderColor: C.border, color: C.muted }}>
            <div className="w-2 h-2 rounded-full"
              style={{ background: runDetail?.status === "COMPLETED" ? C.matched[0] : C.breach[0] }} />
            <select
              value={runId}
              onChange={e => setRunId(e.target.value)}
              className="bg-transparent outline-none text-xs pr-1 cursor-pointer"
              style={{ color: C.text, maxWidth: 220 }}
            >
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {shortId(r.run_id)} — {r.status} — {r.operator_id}
                </option>
              ))}
            </select>
            <ChevronDown size={12} />
          </div>
        )}
        <button onClick={() => setShowUpload(true)}
          className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-md transition-opacity hover:opacity-90"
          style={{ background: `linear-gradient(135deg, ${C.missed[0]}, ${C.missed[1]})` }}>
          <Upload size={15} />
          Upload & Run
        </button>
      </div>
    </header>
  );

  // ── PAGE CONTENT ───────────────────────────────────────────────
  const hasData = recon.length > 0 || findings.length > 0;

  const overviewPage = (
    <div className="flex flex-col gap-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Breach Findings" value={breachCount} sub="Regulatory violations" icon={ShieldAlert} gradient={C.breach} />
        <KpiCard label="Warnings" value={warnCount}   sub="Data quality gaps" icon={AlertTriangle} gradient={C.warn} />
        <KpiCard label="Missed Reports" value={missedCount}  sub={`EFTs ≥ CAD $10,000 unreported`} icon={FileX} gradient={C.missed} />
        <KpiCard label="Matched" value={matchedCount} sub="EFTs with confirmed EFTR" icon={CheckCircle2} gradient={C.matched} />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Reconciliation donut */}
        <Panel title="Reconciliation Status">
          {!hasData ? (
            <div className="flex flex-col items-center justify-center py-12" style={{ color: C.muted }}>
              <FileX size={36} className="mb-3 opacity-40" />
              <p className="text-sm">No data — upload files to run analysis</p>
            </div>
          ) : (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={180} height={180}>
                <PieChart>
                  <Pie data={reconPie} cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                    dataKey="value" paddingAngle={3}>
                    {reconPie.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-3">
                {reconPie.map(e => (
                  <div key={e.name} className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: e.color }} />
                    <span className="text-sm" style={{ color: C.muted }}>{e.name}</span>
                    <span className="ml-auto font-bold text-sm" style={{ color: C.text }}>{e.value}</span>
                  </div>
                ))}
                <div className="pt-2 border-t" style={{ borderColor: C.border }}>
                  <span className="text-xs" style={{ color: C.muted }}>Total: {recon.length} transactions</span>
                </div>
              </div>
            </div>
          )}
        </Panel>

        {/* Findings by severity donut */}
        <Panel title="Findings by Severity">
          {!hasData ? (
            <div className="flex flex-col items-center justify-center py-12" style={{ color: C.muted }}>
              <ShieldAlert size={36} className="mb-3 opacity-40" />
              <p className="text-sm">No findings yet — run an analysis to see results</p>
            </div>
          ) : (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={180} height={180}>
                <PieChart>
                  <Pie data={severityPie} cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                    dataKey="value" paddingAngle={3}>
                    {severityPie.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-3">
                {severityPie.map(e => (
                  <div key={e.name} className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: e.color }} />
                    <span className="text-sm" style={{ color: C.muted }}>{e.name}</span>
                    <span className="ml-auto font-bold text-sm" style={{ color: C.text }}>{e.value}</span>
                  </div>
                ))}
                <div className="pt-2 border-t" style={{ borderColor: C.border }}>
                  <span className="text-xs" style={{ color: C.muted }}>Total: {findings.length} findings</span>
                </div>
              </div>
            </div>
          )}
        </Panel>
      </div>

      {/* Rule findings bar chart */}
      {ruleChartData.length > 0 && (
        <Panel title="Findings by Rule Code">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={ruleChartData} margin={{ top: 4, right: 16, left: -16, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: C.muted }}
                angle={-20} textAnchor="end" interval={0} height={50} />
              <YAxis tick={{ fontSize: 11, fill: C.muted }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {ruleChartData.map((e, i) => <Cell key={i} fill={e.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Run History */}
      <TablePanel title="Run History">
        <thead>
          <tr>
            <Th>Run ID</Th><Th>Status</Th><Th>Operator</Th>
            <Th>Started</Th><Th>Completed</Th><Th>Summary</Th>
          </tr>
        </thead>
        <tbody>
          {runs.length === 0
            ? <EmptyRow cols={6} msg="No runs yet — upload data to start" />
            : runs.map(r => {
              const s = r.parameters?.summary ?? {};
              return (
                <tr key={r.run_id} className="hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => setRunId(r.run_id)}>
                  <Td><span className="font-mono text-xs">{shortId(r.run_id)}</span></Td>
                  <Td><SevBadge sev={r.status} /></Td>
                  <Td>{r.operator_id}</Td>
                  <Td>{fmtDate(r.started_at)}</Td>
                  <Td>{fmtDate(r.completed_at)}</Td>
                  <Td>
                    {Object.keys(s).length > 0
                      ? <span className="text-xs" style={{ color: C.muted }}>
                          {s.matched ?? 0} matched · {s.missed ?? 0} missed · {s.breaches ?? 0} breaches
                        </span>
                      : "—"}
                  </Td>
                </tr>
              );
            })}
        </tbody>
      </TablePanel>
    </div>
  );

  const missedPage = (
    <TablePanel
      title={`Missed Transactions (${filteredMissed.length})`}
      controls={
        <input value={missedFilter} onChange={e => setMissedFilter(e.target.value)}
          placeholder="Filter by transaction ID…"
          className="rounded-lg border px-3 py-1.5 text-xs outline-none"
          style={{ borderColor: C.border, color: C.text, width: 220 }} />
      }
    >
      <thead>
        <tr><Th>EFT Transaction ID</Th><Th>Match Method</Th><Th>Variance</Th><Th>Detail</Th></tr>
      </thead>
      <tbody>
        {loading
          ? <tr><td colSpan={4} className="text-center py-10"><div className="inline-block w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: C.chart[0], borderTopColor: "transparent" }} /></td></tr>
          : filteredMissed.length === 0
            ? <EmptyRow cols={4} msg="No missed transactions found" />
            : filteredMissed.map(r => (
              <tr key={r.result_id} className="hover:bg-gray-50 transition-colors">
                <Td><span className="font-mono text-xs">{r.eft_transaction_id ?? "—"}</span></Td>
                <Td>{r.match_method ?? "—"}</Td>
                <Td>{r.variance_amount != null ? `CAD ${r.variance_amount.toFixed(2)}` : "—"}</Td>
                <Td><span className="text-xs" style={{ color: C.muted }}>{JSON.stringify(r.detail)}</span></Td>
              </tr>
            ))}
      </tbody>
    </TablePanel>
  );

  const findingsPage = (
    <TablePanel
      title={`Rule Findings (${filteredFindings.length})`}
      controls={
        <select value={findingSevFilter} onChange={e => setFindingSevFilter(e.target.value)}
          className="rounded-lg border px-3 py-1.5 text-xs outline-none"
          style={{ borderColor: C.border, color: C.text }}>
          <option value="">All severities</option>
          <option value="BREACH">BREACH</option>
          <option value="WARN">WARN</option>
          <option value="INFO">INFO</option>
        </select>
      }
    >
      <thead>
        <tr><Th>Severity</Th><Th>Rule</Th><Th>Transaction</Th><Th>Detail</Th><Th>Time</Th></tr>
      </thead>
      <tbody>
        {loading
          ? <tr><td colSpan={5} className="text-center py-10"><div className="inline-block w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: C.chart[0], borderTopColor: "transparent" }} /></td></tr>
          : filteredFindings.length === 0
            ? <EmptyRow cols={5} msg="No findings for the selected filter" />
            : filteredFindings.map(f => (
              <tr key={f.finding_id} className="hover:bg-gray-50 transition-colors">
                <Td><SevBadge sev={f.severity} /></Td>
                <Td><span className="text-xs font-mono">{f.rule_code}</span></Td>
                <Td><span className="text-xs font-mono">{f.transaction_id ?? "—"}</span></Td>
                <Td>
                  <span className="text-xs" style={{ color: C.muted }}>
                    {(f.detail as { reason?: string })?.reason ?? JSON.stringify(f.detail).slice(0, 80)}
                  </span>
                </Td>
                <Td><span className="text-xs">{fmtDate(f.created_at)}</span></Td>
              </tr>
            ))}
      </tbody>
    </TablePanel>
  );

  const reperformPage = (
    <TablePanel title={`Reperformance Results (${reperform.length})`}>
      <thead>
        <tr><Th>Type</Th><Th>Status</Th><Th>Reported</Th><Th>Reperformed</Th><Th>Variance</Th><Th>Variance %</Th></tr>
      </thead>
      <tbody>
        {reperform.length === 0
          ? <EmptyRow cols={6} msg="No reperformance data for this run" />
          : reperform.map(r => (
            <tr key={r.result_id} className="hover:bg-gray-50 transition-colors">
              <Td>{r.calculation_type}</Td>
              <Td><SevBadge sev={r.status} /></Td>
              <Td>{r.reported_value?.toFixed(2) ?? "—"}</Td>
              <Td>{r.reperformed_value?.toFixed(2) ?? "—"}</Td>
              <Td>{r.variance_absolute?.toFixed(2) ?? "—"}</Td>
              <Td>{r.variance_pct != null ? `${(r.variance_pct * 100).toFixed(1)}%` : "—"}</Td>
            </tr>
          ))}
      </tbody>
    </TablePanel>
  );

  const auditPage = (
    <TablePanel title={`Audit Log (${audit.length} entries)`}>
      <thead>
        <tr><Th>Severity</Th><Th>Component</Th><Th>Event</Th><Th>Message</Th><Th>Time</Th></tr>
      </thead>
      <tbody>
        {audit.length === 0
          ? <EmptyRow cols={5} msg="No audit entries for this run" />
          : audit.map(e => (
            <tr key={e.log_id} className="hover:bg-gray-50 transition-colors">
              <Td><SevBadge sev={e.severity} /></Td>
              <Td><span className="text-xs font-mono">{e.component}</span></Td>
              <Td><span className="text-xs">{e.event_type}</span></Td>
              <Td><span className="text-xs" style={{ color: C.muted }}>{e.message}</span></Td>
              <Td><span className="text-xs">{fmtDate(e.created_at)}</span></Td>
            </tr>
          ))}
      </tbody>
    </TablePanel>
  );

  const pages: Record<string, React.ReactNode> = {
    overview: overviewPage,
    missed:   missedPage,
    findings: findingsPage,
    reperform: reperformPage,
    audit:    auditPage,
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", fontFamily: "Inter, system-ui, sans-serif" }}>
      {sidebar}
      {header}

      <main style={{
        marginLeft: contentOffset, paddingTop: 64,
        transition: "margin-left 300ms", minHeight: "100vh",
      }}>
        <div className="p-6">
          {pages[page] ?? overviewPage}
        </div>
      </main>

      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onRunCreated={handleRunCreated}
        />
      )}
    </div>
  );
}
