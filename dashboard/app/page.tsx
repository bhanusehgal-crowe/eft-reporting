"use client";

import { useEffect, useRef, useState } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  ShieldAlert, AlertTriangle, FileX, CheckCircle2, Upload,
  LayoutDashboard, ClipboardList, Scale, ScrollText, Menu, X,
  TrendingUp, TrendingDown, ChevronDown, BookOpen, Clock,
  CheckCheck, MessageSquarePlus, ArrowUpRight, Ban, Gavel,
  ChevronRight, Copy, Download, ListChecks, Trash2,
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
interface ComplianceAction {
  action_id: string; finding_id: string; run_id: string;
  status: string; operator_id: string;
  notes: string | null; filed_ref: string | null; decision: string | null;
  deadline: string | null; updated_at: string | null;
}
interface MemoBreachEntry {
  rule: string; count: number; action_required: string;
  earliest_deadline?: string; days_remaining?: number;
}
interface Memo {
  run_id: string; generated_at: string; operator_id: string; period: string;
  executive_summary: string;
  kpi: { total_transactions: number; matched: number; missed: number; phantom: number; breaches: number; warnings: number; actions_taken: number };
  breach_summary: MemoBreachEntry[];
  overdue_filings: Array<{ transaction_id: string | null; rule: string; deadline: string; days_remaining: number; status: string }>;
  travel_rule_exceptions: Array<{ transaction_id: string | null; rule: string; missing_fields: string[]; current_status: string }>;
  recommended_actions: string[];
  disclaimer: string;
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

// ── localStorage persistence ────────────────────────────────────
const STORAGE_KEY = "eftr_dashboard_v1";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function saveToStorage(data: Record<string, any>) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...data, savedAt: new Date().toISOString() })); }
  catch { /* storage unavailable */ }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function loadFromStorage(): Record<string, any> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function clearStorage() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}

const DEADLINE_RULES = new Set([
  "FINTRAC_SINGLE_THRESHOLD", "FINTRAC_24HR_AGGREGATION", "FINTRAC_FILING_DEADLINE",
]);

/** Add n business days (weekdays only — simplified, no holiday calendar on frontend) */
function addBizDays(start: Date, n: number): Date {
  let count = 0; const d = new Date(start);
  while (count < n) { d.setDate(d.getDate() + 1); if (d.getDay() !== 0 && d.getDay() !== 6) count++; }
  return d;
}

function computeDeadline(finding: Finding): Date | null {
  if (!DEADLINE_RULES.has(finding.rule_code)) return null;
  const d = finding.detail as Record<string, string>;
  const vd = d?.value_date || d?.transaction_date;
  if (!vd) return null;
  try { return addBizDays(new Date(vd), 5); } catch { return null; }
}

function deadlineDays(dl: Date): number {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = dl.getTime() - today.getTime();
  return Math.round(diff / (1000 * 60 * 60 * 24));
}

function DeadlinePill({ finding, action }: { finding: Finding; action?: ComplianceAction }) {
  const filed = action?.status === "filed" || action?.status === "resolved";
  const dl = action?.deadline ? new Date(action.deadline) : computeDeadline(finding);
  if (!dl) return <span style={{ color: C.muted }}>—</span>;
  const days = deadlineDays(dl);
  const [bg, text, label] = filed
    ? ["#F1F5F9", "#94A3B8", "Filed"]
    : days < 0
      ? ["#FEE2E2", "#B91C1C", `${Math.abs(days)}d overdue`]
      : days === 0
        ? ["#FEE2E2", "#B91C1C", "Due today"]
        : days <= 2
          ? ["#FFEDD5", "#C2410C", `${days}d left`]
          : ["#D1FAE5", "#047857", `${days}d left`];
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold"
      style={{ background: bg, color: text }}>
      {!filed && <Clock size={10} />}{label}
    </span>
  );
}

const ACTION_STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  open:         { bg: "#F1F5F9", text: "#475569" },
  under_review: { bg: "#DBEAFE", text: "#1D4ED8" },
  filed:        { bg: "#D1FAE5", text: "#047857" },
  resolved:     { bg: "#D1FAE5", text: "#047857" },
  disputed:     { bg: "#FEF3C7", text: "#B45309" },
  escalated:    { bg: "#EDE9FE", text: "#6D28D9" },
};

function ActionStatusBadge({ status }: { status: string }) {
  const s = ACTION_STATUS_STYLES[status] ?? { bg: "#F1F5F9", text: "#475569" };
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold capitalize"
      style={{ background: s.bg, color: s.text }}>
      {status.replace("_", " ")}
    </span>
  );
}

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
  const [actions, setActions] = useState<Record<string, ComplianceAction>>({});
  const [memo, setMemo] = useState<Memo | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [actionForm, setActionForm] = useState<string | null>(null); // which form is open
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [actionSaving, setActionSaving] = useState(false);
  const [queueTab, setQueueTab] = useState("all");
  const skipNextFetch = useRef(false);

  function actionsToMap(list: ComplianceAction[]): Record<string, ComplianceAction> {
    return Object.fromEntries(list.map(a => [a.finding_id, a]));
  }

  async function loadRuns() {
    try { const d = await apiFetch<Run[]>("/runs"); setRuns(d); return d; }
    catch { return []; }
  }

  useEffect(() => {
    // 1. Try localStorage first — instant load, no API dependency
    const cached = loadFromStorage();
    if (cached?.run_id) {
      const entry: Run = cached.run ?? { run_id: cached.run_id, status: "COMPLETED", operator_id: "", started_at: null, completed_at: null };
      setRuns([entry]);
      skipNextFetch.current = true;
      setRunId(cached.run_id);
      setRunDetail(entry);
      setRecon(cached.reconciliation ?? []);
      setFindings(cached.findings ?? []);
      setAudit(cached.audit_log ?? []);
      setReperform(cached.reperform ?? []);
      setActions(cached.actions ?? {});
      if (cached.memo) setMemo(cached.memo as Memo);
      setLoading(false);
    }

    // 2. Ping health in background (doesn't block display)
    apiFetch("/health").then(() => setApiOnline(true)).catch(() => setApiOnline(false));

    // 3. If nothing in storage, fall back to live API
    if (!cached?.run_id) {
      (async () => {
        try { await apiFetch("/health"); setApiOnline(true); } catch { setApiOnline(false); }
        const d = await loadRuns();
        if (d.length) setRunId(d[0].run_id);
        setLoading(false);
      })();
    }
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
      apiFetch<ComplianceAction[]>(`/actions?run_id=${runId}`).catch(() => []),
      apiFetch<Memo>(`/memo/${runId}`).catch(() => null),
    ]).then(([run, reconData, findData, reperformData, auditData, actionsData, memoData]) => {
      setRunDetail(run);
      setRecon(reconData.results ?? []);
      setFindings(findData.findings ?? []);
      setReperform(reperformData.results ?? []);
      setAudit(auditData.entries ?? []);
      setActions(actionsToMap(actionsData ?? []));
      if (memoData) setMemo(memoData as Memo);
    }).finally(() => setLoading(false));
  }, [runId]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function handleRunCreated(data: any) {
    const entry: Run = data.run ?? { run_id: data.run_id, status: data.status, operator_id: "", started_at: null, completed_at: null };
    const actionMap = actionsToMap(data.actions ?? []);

    setRuns(prev => [entry, ...prev.filter(r => r.run_id !== data.run_id)]);
    skipNextFetch.current = true;
    setRunId(data.run_id);
    setRunDetail(entry);
    setRecon(data.reconciliation ?? []);
    setFindings(data.findings ?? []);
    setAudit(data.audit_log ?? []);
    setReperform([]);
    setActions(actionMap);
    if (data.memo) setMemo(data.memo as Memo);
    setLoading(false);
    setPage("overview");

    // Persist to localStorage so results survive page refresh and future visits
    saveToStorage({
      run_id: data.run_id,
      run: entry,
      reconciliation: data.reconciliation ?? [],
      findings: data.findings ?? [],
      audit_log: data.audit_log ?? [],
      reperform: [],
      actions: actionMap,
      memo: data.memo ?? null,
    });
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
  // Badge count for Action Queue — findings without a filed/resolved action
  const openActionCount = findings.filter(f =>
    ["BREACH", "WARN"].includes(f.severity) &&
    !["filed", "resolved"].includes(actions[f.finding_id]?.status ?? "open")
  ).length;

  const navItems = [
    { id: "overview",  icon: LayoutDashboard, label: "Overview",       badge: 0 },
    { id: "queue",     icon: ListChecks,      label: "Action Queue",   badge: openActionCount },
    { id: "missed",    icon: FileX,           label: "Missed Reports", badge: 0 },
    { id: "findings",  icon: ShieldAlert,     label: "Rule Findings",  badge: 0 },
    { id: "reperform", icon: Scale,           label: "Reperformance",  badge: 0 },
    { id: "audit",     icon: ScrollText,      label: "Audit Log",      badge: 0 },
    { id: "memo",      icon: BookOpen,        label: "Manager Memo",   badge: 0 },
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
              <div className="relative flex-shrink-0">
                <item.icon size={18} />
                {item.badge > 0 && !sidebarOpen && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full text-white flex items-center justify-center"
                    style={{ fontSize: 9, background: C.breach[0] }}>
                    {item.badge > 9 ? "9+" : item.badge}
                  </span>
                )}
              </div>
              {sidebarOpen && (
                <span className="text-sm font-medium flex-1">{item.label}</span>
              )}
              {sidebarOpen && item.badge > 0 && (
                <span className="rounded-full px-1.5 py-0.5 text-white font-bold"
                  style={{ fontSize: 10, background: C.breach[0], lineHeight: 1.4 }}>
                  {item.badge}
                </span>
              )}
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
        {/* Clear data button — only shown when data exists */}
        {(recon.length > 0 || findings.length > 0) && (
          <button
            onClick={() => {
              if (!confirm("Clear all current data and start fresh? This cannot be undone.")) return;
              clearStorage();
              setRunId(""); setRunDetail(null); setRuns([]);
              setRecon([]); setFindings([]); setAudit([]); setReperform([]);
              setActions({}); setMemo(null); setSelectedFinding(null);
              setPage("overview");
            }}
            title="Clear data and re-upload"
            className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold border transition-colors hover:bg-red-50"
            style={{ borderColor: "#FECACA", color: C.breach[0] }}>
            <Trash2 size={13} />
            Clear Data
          </button>
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

  // ── Action save helper ─────────────────────────────────────────
  async function saveAction(finding: Finding, patch: Partial<ComplianceAction>) {
    const existing = actions[finding.finding_id];
    setActionSaving(true);
    try {
      let result: ComplianceAction;
      if (existing) {
        result = await fetch(`${API}/actions/${existing.action_id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        }).then(r => r.json());
      } else {
        result = await fetch(`${API}/actions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            finding_id: finding.finding_id,
            run_id: runId,
            operator_id: runDetail?.operator_id ?? "unknown",
            ...patch,
          }),
        }).then(r => r.json());
      }
      const newActions = { ...actions, [finding.finding_id]: result };
      setActions(newActions);
      setActionForm(null);
      setFormData({});

      // Mirror to localStorage so action state survives refresh
      const cached = loadFromStorage();
      if (cached) saveToStorage({ ...cached, actions: newActions });
    } finally {
      setActionSaving(false);
    }
  }

  // ── Finding Drawer ─────────────────────────────────────────────
  const drawer = selectedFinding && (() => {
    const f = selectedFinding;
    const a = actions[f.finding_id];
    const detail = f.detail as Record<string, string | number | string[]>;
    const isBreach = f.severity === "BREACH";
    const isWarn = f.severity === "WARN";
    const isTravelRule = ["FINTRAC_TRAVEL_RULE", "FINTRAC_MANDATORY_FIELDS"].includes(f.rule_code);

    const ActionBtn = ({ icon: Icon, label, color, onClick }: {
      icon: React.ElementType; label: string; color: string; onClick: () => void;
    }) => (
      <button onClick={onClick}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-opacity hover:opacity-80"
        style={{ background: color, color: "#fff" }}>
        <Icon size={13} />{label}
      </button>
    );

    return (
      <>
        {/* Backdrop */}
        <div className="fixed inset-0 z-40" style={{ background: "rgba(0,0,0,0.2)" }}
          onClick={() => { setSelectedFinding(null); setActionForm(null); setFormData({}); }} />
        {/* Drawer */}
        <div className="fixed right-0 top-0 h-screen z-50 flex flex-col shadow-2xl overflow-y-auto"
          style={{ width: 460, background: C.surface, borderLeft: `1px solid ${C.border}` }}>
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b sticky top-0"
            style={{ borderColor: C.border, background: C.surface }}>
            <div className="flex items-center gap-2">
              <SevBadge sev={f.severity} />
              <span className="font-mono text-xs" style={{ color: C.muted }}>{f.rule_code}</span>
            </div>
            <button onClick={() => { setSelectedFinding(null); setActionForm(null); setFormData({}); }}
              className="p-1.5 rounded-lg hover:bg-gray-100">
              <X size={16} style={{ color: C.muted }} />
            </button>
          </div>

          <div className="p-5 flex flex-col gap-5">
            {/* Transaction details */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: C.muted }}>Transaction Details</p>
              <div className="rounded-xl p-4 grid grid-cols-2 gap-2 text-xs"
                style={{ background: "#F8FAFC", border: `1px solid ${C.border}` }}>
                {f.transaction_id && <><span style={{ color: C.muted }}>Transaction ID</span><span className="font-mono font-semibold">{f.transaction_id}</span></>}
                {detail.value_date && <><span style={{ color: C.muted }}>Value Date</span><span>{String(detail.value_date)}</span></>}
                {detail.cad_amount && <><span style={{ color: C.muted }}>CAD Amount</span><span className="font-semibold">${Number(detail.cad_amount).toLocaleString("en-CA", { minimumFractionDigits: 2 })}</span></>}
                {detail.direction && <><span style={{ color: C.muted }}>Direction</span><span>{String(detail.direction)}</span></>}
                {detail.transaction_date && <><span style={{ color: C.muted }}>Txn Date</span><span>{String(detail.transaction_date)}</span></>}
                {detail.filing_date && <><span style={{ color: C.muted }}>Filed Date</span><span>{String(detail.filing_date)}</span></>}
                {detail.reason && <><span style={{ color: C.muted }} className="col-span-2 pt-1 border-t" style={{ borderColor: C.border }}>Finding Reason</span><span className="col-span-2" style={{ color: C.text }}>{String(detail.reason)}</span></>}
              </div>
            </div>

            {/* Deadline (BREACH only) */}
            {isBreach && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: C.muted }}>EFTR Filing Deadline</p>
                <div className="flex items-center gap-3">
                  <DeadlinePill finding={f} action={a} />
                  {a?.deadline && <span className="text-xs" style={{ color: C.muted }}>Due {a.deadline}</span>}
                </div>
              </div>
            )}

            {/* Current action status */}
            {a && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: C.muted }}>Current Status</p>
                <div className="rounded-xl p-3 flex flex-col gap-1.5"
                  style={{ background: "#F8FAFC", border: `1px solid ${C.border}` }}>
                  <div className="flex items-center gap-2">
                    <ActionStatusBadge status={a.status} />
                    <span className="text-xs" style={{ color: C.muted }}>by {a.operator_id}</span>
                  </div>
                  {a.filed_ref && <p className="text-xs"><span style={{ color: C.muted }}>FINTRAC Ref: </span><span className="font-mono font-semibold">{a.filed_ref}</span></p>}
                  {a.decision && <p className="text-xs"><span style={{ color: C.muted }}>Decision: </span><span className="font-semibold capitalize">{a.decision}</span></p>}
                  {a.notes && <p className="text-xs p-2 rounded-lg mt-1" style={{ background: "#EEF2FF", color: "#3730A3" }}>💬 {a.notes}</p>}
                  {a.updated_at && <p className="text-xs" style={{ color: C.muted }}>Last updated {fmtDate(a.updated_at)}</p>}
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: C.muted }}>Actions</p>
              <div className="flex flex-wrap gap-2">
                {isBreach && <ActionBtn icon={CheckCheck} label="File EFTR" color={C.matched[0]} onClick={() => setActionForm("file")} />}
                {isWarn && isTravelRule && <ActionBtn icon={Gavel} label="Log Decision" color={C.chart[0]} onClick={() => setActionForm("decision")} />}
                {isWarn && !isTravelRule && <ActionBtn icon={CheckCheck} label="Mark Resolved" color={C.matched[0]} onClick={() => saveAction(f, { status: "resolved", operator_id: runDetail?.operator_id ?? "unknown" })} />}
                <ActionBtn icon={Ban} label="Dispute" color={C.warn[0]} onClick={() => setActionForm("dispute")} />
                <ActionBtn icon={ArrowUpRight} label="Escalate" color={C.missed[0]} onClick={() => setActionForm("escalate")} />
                <ActionBtn icon={MessageSquarePlus} label="Add Note" color={C.muted} onClick={() => setActionForm("note")} />
              </div>
            </div>

            {/* Inline forms */}
            {actionForm === "file" && (
              <div className="rounded-xl p-4 flex flex-col gap-3 border" style={{ borderColor: C.matched[0], background: "#F0FDF4" }}>
                <p className="text-xs font-semibold" style={{ color: C.matched[0] }}>File EFTR — Enter FINTRAC Reference</p>
                <input value={formData.filed_ref ?? ""} onChange={e => setFormData(d => ({ ...d, filed_ref: e.target.value }))}
                  placeholder="e.g. EFTR-2026-001234"
                  className="rounded-lg border px-3 py-2 text-sm outline-none"
                  style={{ borderColor: C.border }} />
                <input value={formData.notes ?? ""} onChange={e => setFormData(d => ({ ...d, notes: e.target.value }))}
                  placeholder="Notes (optional)" className="rounded-lg border px-3 py-2 text-sm outline-none"
                  style={{ borderColor: C.border }} />
                <div className="flex gap-2">
                  <button disabled={!formData.filed_ref || actionSaving}
                    onClick={() => saveAction(f, { status: "filed", filed_ref: formData.filed_ref, notes: formData.notes || null, operator_id: runDetail?.operator_id ?? "unknown" })}
                    className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50"
                    style={{ background: C.matched[0] }}>
                    {actionSaving ? "Saving…" : "Confirm Filing"}
                  </button>
                  <button onClick={() => { setActionForm(null); setFormData({}); }}
                    className="px-4 py-2 rounded-lg text-xs font-semibold" style={{ background: C.border }}>Cancel</button>
                </div>
              </div>
            )}

            {actionForm === "decision" && (
              <div className="rounded-xl p-4 flex flex-col gap-3 border" style={{ borderColor: C.chart[0], background: "#F5F3FF" }}>
                <p className="text-xs font-semibold" style={{ color: C.chart[0] }}>Travel Rule Exception — Log Decision</p>
                <div className="flex gap-2">
                  {["allow", "suspend", "reject"].map(d => (
                    <button key={d} onClick={() => setFormData(fd => ({ ...fd, decision: d }))}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors capitalize"
                      style={{
                        background: formData.decision === d ? C.chart[0] : "#fff",
                        color: formData.decision === d ? "#fff" : C.muted,
                        borderColor: formData.decision === d ? C.chart[0] : C.border,
                      }}>{d}</button>
                  ))}
                </div>
                <textarea value={formData.notes ?? ""} onChange={e => setFormData(d => ({ ...d, notes: e.target.value }))}
                  placeholder="Written rationale (required)" rows={3}
                  className="rounded-lg border px-3 py-2 text-sm outline-none resize-none"
                  style={{ borderColor: C.border }} />
                <div className="flex gap-2">
                  <button disabled={!formData.decision || !formData.notes?.trim() || actionSaving}
                    onClick={() => saveAction(f, { status: "under_review", decision: formData.decision, notes: formData.notes, operator_id: runDetail?.operator_id ?? "unknown" })}
                    className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50"
                    style={{ background: C.chart[0] }}>
                    {actionSaving ? "Saving…" : "Log Decision"}
                  </button>
                  <button onClick={() => { setActionForm(null); setFormData({}); }}
                    className="px-4 py-2 rounded-lg text-xs font-semibold" style={{ background: C.border }}>Cancel</button>
                </div>
              </div>
            )}

            {(actionForm === "dispute" || actionForm === "escalate" || actionForm === "note") && (
              <div className="rounded-xl p-4 flex flex-col gap-3 border"
                style={{
                  borderColor: actionForm === "note" ? C.border : actionForm === "dispute" ? C.warn[0] : C.missed[0],
                  background: actionForm === "note" ? "#F8FAFC" : actionForm === "dispute" ? "#FFFBEB" : "#F5F3FF",
                }}>
                <p className="text-xs font-semibold" style={{ color: actionForm === "note" ? C.muted : actionForm === "dispute" ? C.warn[0] : C.missed[0] }}>
                  {actionForm === "dispute" ? "Dispute Finding" : actionForm === "escalate" ? "Escalate" : "Add Case Note"}
                </p>
                <textarea value={formData.notes ?? ""} onChange={e => setFormData(d => ({ ...d, notes: e.target.value }))}
                  placeholder={actionForm === "dispute" ? "Reason this finding is incorrect…" : actionForm === "escalate" ? "Escalation message / assign to…" : "Case note…"}
                  rows={3} className="rounded-lg border px-3 py-2 text-sm outline-none resize-none"
                  style={{ borderColor: C.border }} />
                <div className="flex gap-2">
                  <button disabled={!formData.notes?.trim() || actionSaving}
                    onClick={() => saveAction(f, {
                      status: actionForm === "note" ? (a?.status ?? "open") : actionForm as ComplianceAction["status"],
                      notes: formData.notes, operator_id: runDetail?.operator_id ?? "unknown",
                    })}
                    className="px-4 py-2 rounded-lg text-xs font-semibold text-white disabled:opacity-50"
                    style={{ background: actionForm === "note" ? C.muted : actionForm === "dispute" ? C.warn[0] : C.missed[0] }}>
                    {actionSaving ? "Saving…" : "Save"}
                  </button>
                  <button onClick={() => { setActionForm(null); setFormData({}); }}
                    className="px-4 py-2 rounded-lg text-xs font-semibold" style={{ background: C.border }}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </>
    );
  })();

  const findingsPage = (
    <>
      {drawer}
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
          <tr>
            <Th>Severity</Th><Th>Rule</Th><Th>Transaction</Th>
            <Th>Deadline</Th><Th>Status</Th><Th>Detail</Th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? <tr><td colSpan={6} className="text-center py-10"><div className="inline-block w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: C.chart[0], borderTopColor: "transparent" }} /></td></tr>
            : filteredFindings.length === 0
              ? <EmptyRow cols={6} msg="No findings for the selected filter" />
              : filteredFindings.map(f => {
                const a = actions[f.finding_id];
                return (
                  <tr key={f.finding_id}
                    className="hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => { setSelectedFinding(f); setActionForm(null); setFormData({}); }}>
                    <Td><SevBadge sev={f.severity} /></Td>
                    <Td><span className="text-xs font-mono">{f.rule_code.replace("FINTRAC_", "")}</span></Td>
                    <Td><span className="text-xs font-mono">{f.transaction_id ?? "—"}</span></Td>
                    <Td><DeadlinePill finding={f} action={a} /></Td>
                    <Td><ActionStatusBadge status={a?.status ?? "open"} /></Td>
                    <Td>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs" style={{ color: C.muted }}>
                          {(f.detail as { reason?: string })?.reason?.slice(0, 60) ?? "—"}
                        </span>
                        <ChevronRight size={14} style={{ color: C.muted, flexShrink: 0 }} />
                      </div>
                    </Td>
                  </tr>
                );
              })}
        </tbody>
      </TablePanel>
    </>
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

  // ── Action Queue page ──────────────────────────────────────────
  const QUEUE_TABS = [
    { id: "all",         label: "All" },
    { id: "open",        label: "Open" },
    { id: "escalated",   label: "Escalated" },
    { id: "under_review",label: "Under Review" },
    { id: "disputed",    label: "Disputed" },
    { id: "filed",       label: "Filed" },
    { id: "resolved",    label: "Resolved" },
  ];

  // Build queue rows — every BREACH/WARN finding, joined with its action
  const queueRows = findings
    .filter(f => ["BREACH", "WARN"].includes(f.severity))
    .map(f => ({ finding: f, action: actions[f.finding_id] ?? null }))
    .filter(({ action }) =>
      queueTab === "all" ||
      (action ? action.status === queueTab : queueTab === "open")
    )
    .sort((a, b) => {
      // Priority sort: BREACH before WARN, then by deadline (soonest first)
      if (a.finding.severity !== b.finding.severity)
        return a.finding.severity === "BREACH" ? -1 : 1;
      const dlA = computeDeadline(a.finding);
      const dlB = computeDeadline(b.finding);
      if (dlA && dlB) return dlA.getTime() - dlB.getTime();
      if (dlA) return -1;
      if (dlB) return 1;
      return 0;
    });

  // Tab counts
  const tabCounts: Record<string, number> = { all: 0 };
  findings.filter(f => ["BREACH", "WARN"].includes(f.severity)).forEach(f => {
    tabCounts.all = (tabCounts.all ?? 0) + 1;
    const st = actions[f.finding_id]?.status ?? "open";
    tabCounts[st] = (tabCounts[st] ?? 0) + 1;
  });

  const actionQueuePage = (
    <div className="flex flex-col gap-4">
      {/* Header KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: "Total Items",  value: tabCounts.all ?? 0,         color: C.text },
          { label: "Open",         value: tabCounts.open ?? 0,        color: C.breach[0] },
          { label: "Escalated",    value: tabCounts.escalated ?? 0,   color: C.missed[0] },
          { label: "Filed / Done", value: (tabCounts.filed ?? 0) + (tabCounts.resolved ?? 0), color: C.matched[0] },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-2xl p-4 border flex flex-col gap-1"
            style={{ background: C.surface, borderColor: C.border }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: C.muted }}>{label}</p>
            <p className="text-3xl font-bold" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      {/* Tabs + table */}
      <div className="rounded-2xl border overflow-hidden" style={{ background: C.surface, borderColor: C.border }}>
        {/* Tab bar */}
        <div className="flex items-center gap-1 px-4 pt-3 pb-0 border-b overflow-x-auto"
          style={{ borderColor: C.border }}>
          {QUEUE_TABS.map(t => {
            const count = t.id === "all" ? (tabCounts.all ?? 0)
              : t.id === "open" ? (tabCounts.open ?? 0)
              : (tabCounts[t.id] ?? 0);
            if (t.id !== "all" && count === 0) return null;
            const active = queueTab === t.id;
            return (
              <button key={t.id} onClick={() => setQueueTab(t.id)}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-t-lg border-b-2 whitespace-nowrap transition-colors"
                style={{
                  borderBottomColor: active ? C.missed[0] : "transparent",
                  color: active ? C.missed[0] : C.muted,
                  background: "transparent",
                }}>
                {t.label}
                <span className="rounded-full px-1.5 py-0.5 text-white"
                  style={{ fontSize: 10, background: active ? C.missed[0] : C.border, color: active ? "#fff" : C.muted, lineHeight: 1.6 }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Table */}
        <div style={{ overflowX: "auto" }}>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <Th>Severity</Th>
                <Th>Rule</Th>
                <Th>Transaction</Th>
                <Th>Deadline</Th>
                <Th>Status</Th>
                <Th>Notes / Ref</Th>
                <Th>Operator</Th>
                <Th>Action</Th>
              </tr>
            </thead>
            <tbody>
              {queueRows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12" style={{ color: C.muted }}>
                    <ListChecks size={32} className="mx-auto mb-2 opacity-30" />
                    <p className="text-sm">No items in this tab</p>
                  </td>
                </tr>
              ) : queueRows.map(({ finding: f, action: a }) => (
                <tr key={f.finding_id}
                  className="hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => { setSelectedFinding(f); setActionForm(null); setFormData({}); setPage("findings"); }}>
                  <Td><SevBadge sev={f.severity} /></Td>
                  <Td><span className="font-mono text-xs">{f.rule_code.replace("FINTRAC_", "")}</span></Td>
                  <Td><span className="font-mono text-xs">{f.transaction_id ?? "—"}</span></Td>
                  <Td><DeadlinePill finding={f} action={a ?? undefined} /></Td>
                  <Td><ActionStatusBadge status={a?.status ?? "open"} /></Td>
                  <Td>
                    <span className="text-xs" style={{ color: C.muted }}>
                      {a?.filed_ref
                        ? <><span className="font-semibold text-xs" style={{ color: C.matched[0] }}>Ref: </span>{a.filed_ref}</>
                        : a?.notes
                          ? a.notes.slice(0, 50) + (a.notes.length > 50 ? "…" : "")
                          : a?.decision
                            ? <span className="capitalize font-semibold">{a.decision}</span>
                            : "—"}
                    </span>
                  </Td>
                  <Td><span className="text-xs">{a?.operator_id || "—"}</span></Td>
                  <Td>
                    <button
                      onClick={e => { e.stopPropagation(); setSelectedFinding(f); setActionForm(null); setFormData({}); setPage("findings"); }}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-white"
                      style={{ background: `linear-gradient(135deg, ${C.missed[0]}, ${C.missed[1]})` }}>
                      Review <ChevronRight size={12} />
                    </button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  // ── Manager Memo page ──────────────────────────────────────────
  const memoPage = !memo ? (
    <div className="rounded-2xl border p-12 text-center" style={{ background: C.surface, borderColor: C.border }}>
      <BookOpen size={40} className="mx-auto mb-3" style={{ color: C.muted, opacity: 0.4 }} />
      <p className="text-sm" style={{ color: C.muted }}>
        No memo available — upload data to generate a compliance summary.
      </p>
    </div>
  ) : (
    <div className="flex flex-col gap-4">
      {/* Memo header */}
      <div className="rounded-2xl p-6 border" style={{ background: C.surface, borderColor: C.border }}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest mb-1" style={{ color: C.muted }}>Compliance Analysis Memo</p>
            <h2 className="text-xl font-bold" style={{ color: C.text }}>FINTRAC EFT Regulatory Review</h2>
            <p className="text-sm mt-1" style={{ color: C.muted }}>{memo.period}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => {
              const text = [
                "COMPLIANCE ANALYSIS MEMO",
                `Period: ${memo.period}`,
                `Operator: ${memo.operator_id}`,
                `Generated: ${fmtDate(memo.generated_at)}`,
                "",
                "EXECUTIVE SUMMARY",
                memo.executive_summary,
                "",
                "KPIs:",
                `  Total Transactions: ${memo.kpi.total_transactions}`,
                `  Matched: ${memo.kpi.matched} | Missed: ${memo.kpi.missed} | Breaches: ${memo.kpi.breaches} | Warnings: ${memo.kpi.warnings}`,
                "",
                "RECOMMENDED ACTIONS:",
                ...memo.recommended_actions.map((a, i) => `  ${i + 1}. ${a}`),
                "",
                memo.disclaimer,
              ].join("\n");
              navigator.clipboard.writeText(text);
            }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors hover:bg-gray-50"
              style={{ borderColor: C.border, color: C.muted }}>
              <Copy size={13} /> Copy
            </button>
            <button onClick={() => {
              const blob = new Blob([JSON.stringify(memo, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url; a.download = `compliance-memo-${memo.run_id.slice(0, 8)}.json`; a.click();
              URL.revokeObjectURL(url);
            }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white"
              style={{ background: `linear-gradient(135deg, ${C.missed[0]}, ${C.missed[1]})` }}>
              <Download size={13} /> Download JSON
            </button>
          </div>
        </div>
        {/* To / From / Re block */}
        <div className="grid grid-cols-3 gap-4 p-4 rounded-xl text-xs"
          style={{ background: "#F8FAFC", border: `1px solid ${C.border}` }}>
          <div><span style={{ color: C.muted }}>TO: </span><strong>Compliance Management</strong></div>
          <div><span style={{ color: C.muted }}>FROM: </span><strong>{memo.operator_id}</strong></div>
          <div><span style={{ color: C.muted }}>REF: </span><span className="font-mono">{shortId(memo.run_id)}</span></div>
        </div>
      </div>

      {/* Overdue alert */}
      {memo.overdue_filings.length > 0 && (
        <div className="rounded-2xl p-4 flex items-start gap-3 border"
          style={{ background: "#FEF2F2", borderColor: "#FECACA" }}>
          <AlertTriangle size={18} style={{ color: C.breach[0], flexShrink: 0, marginTop: 2 }} />
          <div>
            <p className="font-semibold text-sm" style={{ color: C.breach[0] }}>
              URGENT: {memo.overdue_filings.length} overdue or near-deadline filing{memo.overdue_filings.length > 1 ? "s" : ""}
            </p>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {memo.overdue_filings.map((o, i) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded-full font-semibold"
                  style={{ background: "#FEE2E2", color: "#B91C1C" }}>
                  {o.transaction_id} — {o.status} ({o.days_remaining < 0 ? `${Math.abs(o.days_remaining)}d overdue` : `${o.days_remaining}d left`})
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Executive summary + KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-2xl p-5 border" style={{ background: C.surface, borderColor: C.border }}>
          <p className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: C.muted }}>Executive Summary</p>
          <p className="text-sm leading-relaxed" style={{ color: C.text }}>{memo.executive_summary}</p>
        </div>
        <div className="rounded-2xl p-5 border" style={{ background: C.surface, borderColor: C.border }}>
          <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: C.muted }}>Key Metrics</p>
          <div className="flex flex-col gap-2">
            {[
              { label: "Total Transactions", value: memo.kpi.total_transactions, color: C.text },
              { label: "Matched EFTRs", value: memo.kpi.matched, color: C.matched[0] },
              { label: "Missed Reports", value: memo.kpi.missed, color: C.breach[0] },
              { label: "BREACH Findings", value: memo.kpi.breaches, color: C.breach[0] },
              { label: "Warnings", value: memo.kpi.warnings, color: C.warn[0] },
              { label: "Actions Taken", value: memo.kpi.actions_taken, color: C.missed[0] },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex justify-between items-center text-xs">
                <span style={{ color: C.muted }}>{label}</span>
                <span className="font-bold" style={{ color }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recommended actions */}
      <div className="rounded-2xl p-5 border" style={{ background: C.surface, borderColor: C.border }}>
        <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: C.muted }}>Recommended Actions</p>
        <ol className="flex flex-col gap-2">
          {memo.recommended_actions.map((action, i) => (
            <li key={i} className="flex items-start gap-3 text-sm">
              <span className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
                style={{ background: `linear-gradient(135deg, ${C.missed[0]}, ${C.missed[1]})`, color: "#fff" }}>
                {i + 1}
              </span>
              <span style={{ color: C.text }}>{action}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Breach breakdown */}
      {memo.breach_summary.length > 0 && (
        <div className="rounded-2xl border overflow-hidden" style={{ background: C.surface, borderColor: C.border }}>
          <div className="px-5 py-3 border-b" style={{ borderColor: C.border }}>
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: C.muted }}>Breach Summary</p>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <Th>Rule</Th><Th>Count</Th><Th>Earliest Deadline</Th><Th>Days Remaining</Th><Th>Action Required</Th>
              </tr>
            </thead>
            <tbody>
              {memo.breach_summary.map(b => (
                <tr key={b.rule} className="hover:bg-gray-50">
                  <Td><span className="font-mono text-xs">{b.rule}</span></Td>
                  <Td><span className="font-bold">{b.count}</span></Td>
                  <Td>{b.earliest_deadline ?? "—"}</Td>
                  <Td>
                    {b.days_remaining !== undefined ? (
                      <span className="font-semibold" style={{ color: (b.days_remaining ?? 99) <= 0 ? C.breach[0] : (b.days_remaining ?? 99) <= 2 ? C.warn[0] : C.matched[0] }}>
                        {b.days_remaining <= 0 ? `${Math.abs(b.days_remaining)}d overdue` : `${b.days_remaining}d`}
                      </span>
                    ) : "—"}
                  </Td>
                  <Td><span className="text-xs" style={{ color: C.muted }}>{b.action_required}</span></Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Disclaimer */}
      <div className="rounded-xl p-4 text-xs" style={{ background: "#F8FAFC", color: C.muted, border: `1px solid ${C.border}` }}>
        <strong>Disclaimer:</strong> {memo.disclaimer}
      </div>
    </div>
  );

  const pages: Record<string, React.ReactNode> = {
    overview:  overviewPage,
    queue:     actionQueuePage,
    missed:    missedPage,
    findings:  findingsPage,
    reperform: reperformPage,
    audit:     auditPage,
    memo:      memoPage,
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
