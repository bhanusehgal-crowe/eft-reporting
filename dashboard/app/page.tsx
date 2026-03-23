"use client";

import { useEffect, useRef, useState } from "react";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from "chart.js";
import { Doughnut, Bar } from "react-chartjs-2";

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────
interface Run {
  run_id: string;
  status: string;
  operator_id: string;
  started_at: string | null;
  completed_at: string | null;
  parameters?: { summary?: Record<string, number> };
}

interface ReconResult {
  result_id: string;
  status: string;
  eft_transaction_id: string | null;
  reported_id: string | null;
  match_method: string | null;
  variance_amount: number | null;
  detail: Record<string, unknown>;
}

interface Finding {
  finding_id: string;
  rule_code: string;
  rule_version: number;
  severity: string;
  transaction_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

interface ReperformResult {
  result_id: string;
  calculation_type: string;
  status: string;
  reported_value: number | null;
  reperformed_value: number | null;
  variance_absolute: number | null;
  variance_pct: number | null;
  detail: Record<string, unknown>;
}

interface AuditEntry {
  log_id: string;
  event_type: string;
  severity: string;
  component: string;
  operator_id: string | null;
  message: string;
  created_at: string;
}

// ── Helpers ────────────────────────────────────────────────────
async function apiFetch<T>(path: string): Promise<T> {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" });
}

function fmtCad(n: number | null) {
  if (n == null) return "—";
  return "CAD " + Number(n).toLocaleString("en-CA", { minimumFractionDigits: 2 });
}

function SeverityBadge({ sev }: { sev: string }) {
  const map: Record<string, string> = {
    BREACH: "danger", WARN: "warning", INFO: "primary",
    MATCHED: "success", MISSED: "danger", PHANTOM: "warning",
    COMPLETED: "success", RUNNING: "info", FAILED: "danger", PENDING: "secondary",
    PASS: "success", VARIANCE: "warning",
  };
  return (
    <span
      className={`badge bg-${map[sev] ?? "secondary"} bg-opacity-15 text-${map[sev] ?? "secondary"} border border-${map[sev] ?? "secondary"} border-opacity-25`}
      style={{ fontWeight: 600, fontSize: "0.72rem" }}
    >
      {sev}
    </span>
  );
}

function MetricCard({ label, value, icon, color, sub }: {
  label: string; value: string | number; icon: string; color: string; sub: string;
}) {
  return (
    <div className="col">
      <div className="card border-0 shadow-sm h-100" style={{ borderRadius: 12 }}>
        <div className="card-body p-4">
          <div className="d-flex align-items-center gap-2 mb-2">
            <i className={`bi bi-${icon} text-${color}`} style={{ fontSize: "1rem" }} />
            <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {label}
            </span>
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: color === "danger" ? "#dc2626" : color === "warning" ? "#d97706" : color === "success" ? "#16a34a" : "#2563eb" }}>
            {value}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: 2 }}>{sub}</div>
        </div>
      </div>
    </div>
  );
}

function TableCard({ title, controls, children }: {
  title: string; controls?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: 12, overflow: "hidden" }}>
      <div className="card-header bg-white border-bottom d-flex align-items-center justify-content-between py-3 px-4">
        <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "#334155" }}>{title}</span>
        {controls && <div className="d-flex gap-2">{controls}</div>}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="table table-hover mb-0" style={{ fontSize: "0.82rem" }}>
          {children}
        </table>
      </div>
    </div>
  );
}

function EmptyRow({ cols, message }: { cols: number; message: string }) {
  return (
    <tr><td colSpan={cols} className="text-center py-5 text-muted">{message}</td></tr>
  );
}

function LoadingRow({ cols }: { cols: number }) {
  return (
    <tr><td colSpan={cols} className="text-center py-5">
      <div className="spinner-border spinner-border-sm text-primary" />
    </td></tr>
  );
}

// ── Upload Modal ─────────────────────────────────────────────
const PIPELINE_STEPS = [
  { label: "Uploading files", icon: "cloud-upload" },
  { label: "Ingesting EFT transactions", icon: "table" },
  { label: "Running reconciliation", icon: "arrow-left-right" },
  { label: "Evaluating FINTRAC rules", icon: "shield-check" },
  { label: "Generating compliance report", icon: "file-earmark-text" },
];

function UploadModal({
  onClose,
  onRunCreated,
}: {
  onClose: () => void;
  onRunCreated: (runId: string) => void;
}) {
  const [eftFile, setEftFile] = useState<File | null>(null);
  const [repFile, setRepFile] = useState<File | null>(null);
  const [operatorId, setOperatorId] = useState("");
  const [eftDrag, setEftDrag] = useState(false);
  const [repDrag, setRepDrag] = useState(false);
  const [phase, setPhase] = useState<"form" | "running" | "done" | "error">("form");
  const [stepIndex, setStepIndex] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const [runId, setRunId] = useState("");
  const stepRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const eftInputRef = useRef<HTMLInputElement>(null);
  const repInputRef = useRef<HTMLInputElement>(null);

  // Advance step animation while running
  useEffect(() => {
    if (phase === "running") {
      stepRef.current = setInterval(() => {
        setStepIndex(i => Math.min(i + 1, PIPELINE_STEPS.length - 1));
      }, 3500);
    }
    return () => { if (stepRef.current) clearInterval(stepRef.current); };
  }, [phase]);

  async function handleSubmit() {
    if (!eftFile || !repFile || !operatorId.trim()) return;
    setPhase("running");
    setStepIndex(0);
    const fd = new FormData();
    fd.append("eft_file", eftFile);
    fd.append("reported_file", repFile);
    fd.append("operator_id", operatorId.trim());
    try {
      // Pipeline runs synchronously on the server — this fetch blocks until complete
      const res = await fetch(`${API}/runs/upload`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setStepIndex(PIPELINE_STEPS.length);
      setRunId(data.run_id);
      setPhase("done");
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Upload failed");
      setPhase("error");
    } finally {
      if (stepRef.current) clearInterval(stepRef.current);
    }
  }

  function handleDone() {
    onRunCreated(runId);
    onClose();
  }

  const dropZone = (
    label: string,
    sublabel: string,
    file: File | null,
    setFile: (f: File) => void,
    drag: boolean,
    setDrag: (v: boolean) => void,
    inputRef: React.RefObject<HTMLInputElement>
  ) => (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => {
        e.preventDefault(); setDrag(false);
        const f = e.dataTransfer.files[0];
        if (f) setFile(f);
      }}
      style={{
        border: `2px dashed ${drag ? "#2563eb" : file ? "#16a34a" : "#cbd5e1"}`,
        borderRadius: 12,
        padding: "28px 20px",
        cursor: "pointer",
        background: drag ? "#eff6ff" : file ? "#f0fdf4" : "#f8fafc",
        transition: "all 0.2s",
        textAlign: "center",
        flex: 1,
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx"
        style={{ display: "none" }}
        onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f); }}
      />
      <i
        className={`bi bi-${file ? "check-circle-fill" : "cloud-upload"}`}
        style={{ fontSize: "2rem", color: file ? "#16a34a" : drag ? "#2563eb" : "#94a3b8" }}
      />
      <div style={{ fontWeight: 600, fontSize: "0.875rem", marginTop: 10, color: file ? "#16a34a" : "#334155" }}>
        {file ? file.name : label}
      </div>
      <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: 4 }}>
        {file ? `${(file.size / 1024).toFixed(1)} KB` : sublabel}
      </div>
    </div>
  );

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      {/* Backdrop */}
      <div
        onClick={phase === "form" ? onClose : undefined}
        style={{ position: "absolute", inset: 0, background: "rgba(15,23,42,0.55)", backdropFilter: "blur(4px)" }}
      />

      {/* Modal */}
      <div style={{
        position: "relative", width: "100%", maxWidth: 680,
        background: "#fff", borderRadius: 16, boxShadow: "0 24px 64px rgba(0,0,0,0.18)",
        overflow: "hidden", margin: "0 16px",
      }}>
        {/* Header */}
        <div style={{ background: "linear-gradient(135deg, #1a3a5c 0%, #2563eb 100%)", padding: "24px 28px", color: "#fff" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: "1.125rem", fontWeight: 700 }}>
                <i className="bi bi-play-circle me-2" />New Compliance Analysis Run
              </div>
              <div style={{ fontSize: "0.8rem", opacity: 0.75, marginTop: 4 }}>
                Upload your EFT and EFTR datasets — the full FINTRAC validation pipeline will run automatically
              </div>
            </div>
            {phase === "form" && (
              <button onClick={onClose} style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 8, color: "#fff", width: 32, height: 32, cursor: "pointer", fontSize: "1rem" }}>
                <i className="bi bi-x" />
              </button>
            )}
          </div>
        </div>

        <div style={{ padding: "28px" }}>
          {/* ── FORM ── */}
          {phase === "form" && (
            <>
              <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
                {dropZone(
                  "Drop EFT Transactions CSV",
                  "Click or drag & drop (.csv or .xlsx)",
                  eftFile, setEftFile, eftDrag, setEftDrag, eftInputRef
                )}
                {dropZone(
                  "Drop Filed Reports (EFTR) CSV",
                  "Click or drag & drop (.csv or .xlsx)",
                  repFile, setRepFile, repDrag, setRepDrag, repInputRef
                )}
              </div>

              <div style={{ marginBottom: 24 }}>
                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#475569", display: "block", marginBottom: 6 }}>
                  Operator ID <span style={{ color: "#dc2626" }}>*</span>
                </label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. john.doe"
                  value={operatorId}
                  onChange={e => setOperatorId(e.target.value)}
                  style={{ borderRadius: 8, fontSize: "0.875rem" }}
                />
              </div>

              <button
                onClick={handleSubmit}
                disabled={!eftFile || !repFile || !operatorId.trim()}
                style={{
                  width: "100%", padding: "14px", borderRadius: 10, border: "none",
                  background: (!eftFile || !repFile || !operatorId.trim()) ? "#e2e8f0" : "linear-gradient(135deg, #1a3a5c 0%, #2563eb 100%)",
                  color: (!eftFile || !repFile || !operatorId.trim()) ? "#94a3b8" : "#fff",
                  fontWeight: 700, fontSize: "0.95rem", cursor: (!eftFile || !repFile || !operatorId.trim()) ? "not-allowed" : "pointer",
                  transition: "all 0.2s",
                }}
              >
                <i className="bi bi-play-fill me-2" />Run FINTRAC Compliance Analysis
              </button>

              <p style={{ fontSize: "0.72rem", color: "#94a3b8", textAlign: "center", marginTop: 12, marginBottom: 0 }}>
                Pipeline runs in background — ingest → reconcile → rule checks → Excel report
              </p>
            </>
          )}

          {/* ── RUNNING ── */}
          {(phase === "running" || phase === "done") && (
            <>
              <div style={{ marginBottom: 24 }}>
                {PIPELINE_STEPS.map((step, i) => {
                  const done = i < stepIndex;
                  const active = i === stepIndex && phase === "running";
                  const pending = i > stepIndex;
                  return (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 0", borderBottom: i < PIPELINE_STEPS.length - 1 ? "1px solid #f1f5f9" : "none" }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: "50%", flexShrink: 0,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        background: done ? "#dcfce7" : active ? "#dbeafe" : "#f1f5f9",
                        border: `2px solid ${done ? "#16a34a" : active ? "#2563eb" : "#e2e8f0"}`,
                        transition: "all 0.4s",
                      }}>
                        {done
                          ? <i className="bi bi-check-lg" style={{ color: "#16a34a", fontSize: "0.9rem" }} />
                          : active
                          ? <div className="spinner-border spinner-border-sm" style={{ color: "#2563eb", width: 16, height: 16, borderWidth: 2 }} />
                          : <i className={`bi bi-${step.icon}`} style={{ color: "#94a3b8", fontSize: "0.85rem" }} />
                        }
                      </div>
                      <div>
                        <div style={{ fontSize: "0.875rem", fontWeight: active ? 600 : done ? 500 : 400, color: active ? "#1e40af" : done ? "#16a34a" : "#94a3b8" }}>
                          {step.label}
                          {done && <span style={{ marginLeft: 8, fontSize: "0.72rem", color: "#86efac" }}>complete</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {phase === "done" && (
                <div>
                  <div className="alert alert-success d-flex align-items-center gap-3 mb-4" style={{ borderRadius: 10 }}>
                    <i className="bi bi-check-circle-fill fs-5" />
                    <div>
                      <strong>Analysis complete!</strong>
                      <div style={{ fontSize: "0.8rem" }}>Run ID: <code>{runId}</code></div>
                    </div>
                  </div>
                  <button
                    onClick={handleDone}
                    style={{ width: "100%", padding: "12px", borderRadius: 10, border: "none", background: "linear-gradient(135deg, #1a3a5c 0%, #2563eb 100%)", color: "#fff", fontWeight: 700, cursor: "pointer" }}
                  >
                    <i className="bi bi-bar-chart-line me-2" />View Results
                  </button>
                </div>
              )}

              {phase === "running" && (
                <div style={{ fontSize: "0.78rem", color: "#94a3b8", textAlign: "center" }}>
                  Processing in background — this may take a few seconds…
                </div>
              )}
            </>
          )}

          {/* ── ERROR ── */}
          {phase === "error" && (
            <>
              <div className="alert alert-danger d-flex align-items-center gap-3 mb-4" style={{ borderRadius: 10 }}>
                <i className="bi bi-exclamation-triangle-fill fs-5" />
                <div>
                  <strong>Pipeline failed</strong>
                  <div style={{ fontSize: "0.8rem" }}>{errorMsg}</div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 12 }}>
                <button onClick={() => { setPhase("form"); setErrorMsg(""); }} style={{ flex: 1, padding: "12px", borderRadius: 10, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", fontWeight: 600 }}>
                  Try Again
                </button>
                <button onClick={onClose} style={{ flex: 1, padding: "12px", borderRadius: 10, border: "none", background: "#f1f5f9", cursor: "pointer", fontWeight: 600 }}>
                  Close
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────
export default function Dashboard() {
  const [page, setPage] = useState("overview");
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

  // Filters
  const [missedFilter, setMissedFilter] = useState("");
  const [findingSevFilter, setFindingSevFilter] = useState("");
  const [findingRuleFilter, setFindingRuleFilter] = useState("");
  const [reperformTypeFilter, setReperformTypeFilter] = useState("");
  const [reperformStatusFilter, setReperformStatusFilter] = useState("");
  const [auditSevFilter, setAuditSevFilter] = useState("");

  async function loadRuns() {
    try {
      const data = await apiFetch<Run[]>("/runs");
      setRuns(data);
      return data;
    } catch { return []; }
  }

  // Init
  useEffect(() => {
    (async () => {
      try { await apiFetch("/health"); setApiOnline(true); } catch { setApiOnline(false); }
      const data = await loadRuns();
      if (data.length) setRunId(data[0].run_id);
    })();
  }, []);

  // Load run data when runId changes
  useEffect(() => {
    if (!runId) return;
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

  function handleRunCreated(newRunId: string) {
    loadRuns().then(data => {
      setRuns(data);
      setRunId(newRunId);
    });
  }

  // Derived counts
  const breachCount = findings.filter(f => f.severity === "BREACH").length;
  const warnCount = findings.filter(f => f.severity === "WARN").length;
  const infoCount = findings.filter(f => f.severity === "INFO").length;
  const matchedCount = recon.filter(r => r.status === "MATCHED").length;
  const missedCount = recon.filter(r => r.status === "MISSED").length;
  const phantomCount = recon.filter(r => r.status === "PHANTOM").length;

  // Chart data
  const severityChartData = {
    labels: ["BREACH", "WARN", "INFO"],
    datasets: [{ data: [breachCount, warnCount, infoCount], backgroundColor: ["#dc2626", "#d97706", "#2563eb"], borderWidth: 2, borderColor: "#fff" }],
  };

  const ruleGroups: Record<string, { count: number; color: string }> = {};
  findings.forEach(f => {
    const key = f.rule_code.replace("FINTRAC_", "");
    if (!ruleGroups[key]) ruleGroups[key] = { count: 0, color: f.severity === "BREACH" ? "#dc2626" : f.severity === "WARN" ? "#d97706" : "#2563eb" };
    ruleGroups[key].count++;
  });
  const rulesChartData = {
    labels: Object.keys(ruleGroups),
    datasets: [{ label: "Findings", data: Object.values(ruleGroups).map(v => v.count), backgroundColor: Object.values(ruleGroups).map(v => v.color), borderRadius: 6, borderSkipped: false as const }],
  };

  // Filtered data
  const filteredMissed = recon.filter(r => r.status !== "MATCHED" && (!missedFilter || r.status === missedFilter));
  const filteredFindings = findings.filter(f => (!findingSevFilter || f.severity === findingSevFilter) && (!findingRuleFilter || f.rule_code === findingRuleFilter));
  const filteredReperform = reperform.filter(r => (!reperformTypeFilter || r.calculation_type === reperformTypeFilter) && (!reperformStatusFilter || r.status === reperformStatusFilter));
  const filteredAudit = audit.filter(e => !auditSevFilter || e.severity === auditSevFilter);
  const uniqueRuleCodes = Array.from(new Set(findings.map(f => f.rule_code))).sort();

  const sidebarItems = [
    { id: "overview", icon: "grid-1x2", label: "Overview" },
    { id: "missed", icon: "exclamation-triangle", label: "Missed Transactions" },
    { id: "findings", icon: "flag", label: "Rule Findings" },
    { id: "reperformance", icon: "calculator", label: "Reperformance" },
    { id: "audit", icon: "journal-text", label: "Audit Log" },
  ];

  const pageTitles: Record<string, string> = {
    overview: "Overview", missed: "Missed Transactions", findings: "Rule Findings",
    reperformance: "Reperformance Results", audit: "Audit Log",
  };

  const filterSelect = (value: string, onChange: (v: string) => void, options: { value: string; label: string }[]) => (
    <select className="form-select form-select-sm" style={{ fontSize: "0.78rem" }} value={value} onChange={e => onChange(e.target.value)}>
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>

      {/* Upload Modal */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onRunCreated={handleRunCreated}
        />
      )}

      {/* ── Sidebar ── */}
      <div style={{ width: 260, background: "#1a3a5c", color: "#fff", display: "flex", flexDirection: "column", position: "fixed", top: 0, left: 0, bottom: 0, zIndex: 100 }}>
        <div style={{ padding: "24px 20px 16px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
          <div style={{ fontWeight: 700, fontSize: "1rem" }}>
            <i className="bi bi-shield-check me-2" />EFTR Platform
          </div>
          <div style={{ fontSize: "0.72rem", opacity: 0.6, marginTop: 4 }}>FINTRAC Regulatory Assurance</div>
        </div>
        <nav style={{ flex: 1, padding: "12px 0" }}>
          {sidebarItems.map(item => (
            <button key={item.id} onClick={() => setPage(item.id)}
              style={{
                display: "flex", alignItems: "center", gap: 10, width: "100%",
                padding: "10px 20px", border: "none",
                borderLeft: `3px solid ${page === item.id ? "#60a5fa" : "transparent"}`,
                color: page === item.id ? "#fff" : "rgba(255,255,255,0.7)",
                background: page === item.id ? "rgba(255,255,255,0.1)" : "transparent",
                fontSize: "0.875rem", cursor: "pointer", textAlign: "left",
              }}>
              <i className={`bi bi-${item.icon}`} style={{ width: 18, textAlign: "center" }} />
              {item.label}
            </button>
          ))}
        </nav>

        {/* Sidebar upload button */}
        <div style={{ padding: "16px 20px", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
          <button
            onClick={() => setShowUpload(true)}
            style={{
              width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(96,165,250,0.15)", color: "#93c5fd", fontWeight: 600, fontSize: "0.8rem",
              cursor: "pointer", display: "flex", alignItems: "center", gap: 8,
            }}
          >
            <i className="bi bi-cloud-upload" />New Analysis Run
          </button>
          <div style={{ padding: "10px 0 0", fontSize: "0.7rem", opacity: 0.4 }}>
            EFTR AI Use Case &mdash; v1.0.0
          </div>
        </div>
      </div>

      {/* ── Main ── */}
      <div style={{ marginLeft: 260, flex: 1 }}>

        {/* Topbar */}
        <div className="bg-white border-bottom d-flex align-items-center justify-content-between px-4 py-3" style={{ position: "sticky", top: 0, zIndex: 50 }}>
          <h2 style={{ fontSize: "1.125rem", fontWeight: 600, margin: 0 }}>{pageTitles[page]}</h2>
          <div className="d-flex align-items-center gap-3">
            <button
              onClick={() => setShowUpload(true)}
              style={{
                padding: "8px 18px", borderRadius: 8, border: "none",
                background: "linear-gradient(135deg, #1a3a5c 0%, #2563eb 100%)",
                color: "#fff", fontWeight: 600, fontSize: "0.82rem", cursor: "pointer",
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              <i className="bi bi-cloud-upload" />Upload & Run Analysis
            </button>

            <select className="form-select form-select-sm" style={{ fontSize: "0.8rem", maxWidth: 340 }}
              value={runId} onChange={e => setRunId(e.target.value)}>
              {!runs.length && <option value="">No runs — upload data to start</option>}
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id.slice(0, 8)}… — {r.status} — {r.operator_id} — {fmtDate(r.started_at)}
                </option>
              ))}
            </select>

            <div className="d-flex align-items-center gap-2" style={{ fontSize: "0.75rem", whiteSpace: "nowrap" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: apiOnline ? "#22c55e" : "#94a3b8", display: "inline-block" }} />
              {apiOnline ? "API Connected" : "API Offline"}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">

          {/* ── OVERVIEW ── */}
          {page === "overview" && (
            <>
              {breachCount > 0 && (
                <div className="alert border-danger bg-danger bg-opacity-10 d-flex gap-3 mb-4" style={{ borderRadius: 10 }}>
                  <i className="bi bi-shield-exclamation text-danger fs-5 mt-1" />
                  <div>
                    <strong className="text-danger">FINTRAC Compliance Alert — {breachCount} Breach Finding{breachCount > 1 ? "s" : ""} Detected</strong>
                    <p className="mb-0 small text-danger-emphasis">Immediate remediation required. Review Rule Findings and Missed Transactions for details.</p>
                  </div>
                </div>
              )}

              {!runs.length && (
                <div
                  style={{ border: "2px dashed #cbd5e1", borderRadius: 16, padding: "60px 40px", textAlign: "center", marginBottom: 24, cursor: "pointer" }}
                  onClick={() => setShowUpload(true)}
                >
                  <i className="bi bi-cloud-upload" style={{ fontSize: "3rem", color: "#94a3b8" }} />
                  <h5 style={{ marginTop: 16, fontWeight: 600, color: "#334155" }}>No analysis runs yet</h5>
                  <p style={{ color: "#94a3b8", marginBottom: 20 }}>Upload your EFT and EFTR datasets to run a compliance analysis</p>
                  <button style={{ padding: "10px 28px", borderRadius: 8, border: "none", background: "linear-gradient(135deg, #1a3a5c 0%, #2563eb 100%)", color: "#fff", fontWeight: 600, cursor: "pointer" }}>
                    <i className="bi bi-play-fill me-2" />Start First Run
                  </button>
                </div>
              )}

              {runDetail && (
                <div className="mb-4 p-4 rounded-3 text-white d-flex align-items-center justify-content-between"
                  style={{ background: "linear-gradient(135deg, #1a3a5c 0%, #2563eb 100%)" }}>
                  <div>
                    <div style={{ fontSize: "0.78rem", opacity: 0.8, fontFamily: "monospace" }}>Run ID: {runId}</div>
                    <div style={{ fontSize: "0.85rem", opacity: 0.9, marginTop: 6 }}>
                      Operator: {runDetail.operator_id} &nbsp;|&nbsp; Started: {fmtDate(runDetail.started_at)} &nbsp;|&nbsp; Completed: {fmtDate(runDetail.completed_at)}
                    </div>
                  </div>
                  <SeverityBadge sev={runDetail.status} />
                </div>
              )}

              <div className="row row-cols-4 g-3 mb-4">
                <MetricCard label="BREACH Findings" value={breachCount} icon="shield-x" color="danger" sub="Regulatory violations requiring action" />
                <MetricCard label="Warnings" value={warnCount} icon="exclamation-circle" color="warning" sub="Data quality & compliance gaps" />
                <MetricCard label="Missed Reports" value={missedCount} icon="file-earmark-x" color="danger" sub="EFTs ≥ CAD $10,000 — unreported" />
                <MetricCard label="Matched" value={matchedCount} icon="check-circle" color="success" sub="EFTs with confirmed EFTR on file" />
              </div>

              <div className="row g-3 mb-4">
                <div className="col-4">
                  <div className="card border-0 shadow-sm h-100" style={{ borderRadius: 12 }}>
                    <div className="card-body p-4">
                      <h6 className="fw-semibold text-secondary mb-3" style={{ fontSize: "0.875rem" }}>Findings by Severity</h6>
                      <Doughnut data={severityChartData} options={{ plugins: { legend: { position: "bottom" } }, cutout: "62%" }} />
                    </div>
                  </div>
                </div>
                <div className="col-8">
                  <div className="card border-0 shadow-sm h-100" style={{ borderRadius: 12 }}>
                    <div className="card-body p-4">
                      <h6 className="fw-semibold text-secondary mb-3" style={{ fontSize: "0.875rem" }}>Findings by Rule Code</h6>
                      {Object.keys(ruleGroups).length > 0
                        ? <Bar data={rulesChartData} options={{ plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } }, x: { grid: { display: false } } } }} />
                        : <div className="d-flex flex-column align-items-center justify-content-center h-100 text-muted py-5" style={{ cursor: "pointer" }} onClick={() => setShowUpload(true)}>
                            <i className="bi bi-bar-chart" style={{ fontSize: "2.5rem", opacity: 0.3 }} />
                            <div style={{ marginTop: 10, fontSize: "0.875rem" }}>No findings yet — run an analysis to see results</div>
                          </div>
                      }
                    </div>
                  </div>
                </div>
              </div>

              <TableCard title="Run History">
                <thead className="table-light">
                  <tr>
                    <th>Run ID</th><th>Status</th><th>Operator</th>
                    <th>Started</th><th>Completed</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0
                    ? <EmptyRow cols={5} message="No runs found — click 'Upload & Run Analysis' to start" />
                    : runs.map(r => (
                      <tr key={r.run_id} style={{ cursor: "pointer" }} onClick={() => setRunId(r.run_id)}>
                        <td className="font-monospace" style={{ fontSize: "0.78rem" }}>{r.run_id.slice(0, 8)}…</td>
                        <td><SeverityBadge sev={r.status} /></td>
                        <td>{r.operator_id}</td>
                        <td style={{ color: "#64748b", fontSize: "0.78rem" }}>{fmtDate(r.started_at)}</td>
                        <td style={{ color: "#64748b", fontSize: "0.78rem" }}>{fmtDate(r.completed_at)}</td>
                      </tr>
                    ))}
                </tbody>
              </TableCard>
            </>
          )}

          {/* ── MISSED TRANSACTIONS ── */}
          {page === "missed" && (
            <>
              <div className="d-flex justify-content-between align-items-start mb-4">
                <p className="text-muted mb-0" style={{ fontSize: "0.875rem" }}>EFTs with no corresponding EFTR filed with FINTRAC</p>
                <a className="btn btn-primary btn-sm" href={`${API}/reports/${runId}/missed-transactions`} target="_blank">
                  <i className="bi bi-download me-1" />Download Excel Report
                </a>
              </div>
              <div className="row row-cols-3 g-3 mb-4">
                <MetricCard label="Missed (Unreported)" value={missedCount} icon="file-earmark-x" color="danger" sub="EFTs with no EFTR filed" />
                <MetricCard label="Phantom (Unmatched)" value={phantomCount} icon="question-circle" color="warning" sub="EFTRs with no underlying EFT" />
                <MetricCard label="Matched" value={matchedCount} icon="check-circle" color="success" sub="Successfully reconciled" />
              </div>
              <TableCard title="Unmatched EFT Transactions"
                controls={filterSelect(missedFilter, setMissedFilter, [
                  { value: "", label: "All Statuses" },
                  { value: "MISSED", label: "MISSED" },
                  { value: "PHANTOM", label: "PHANTOM" },
                ])}>
                <thead className="table-light">
                  <tr><th>Status</th><th>EFT Transaction ID</th><th>Match Method</th><th>Variance (CAD)</th><th>Detail</th></tr>
                </thead>
                <tbody>
                  {loading ? <LoadingRow cols={5} />
                    : filteredMissed.length === 0 ? <EmptyRow cols={5} message="No unmatched transactions" />
                    : filteredMissed.map(r => (
                      <tr key={r.result_id}>
                        <td><SeverityBadge sev={r.status} /></td>
                        <td className="font-monospace" style={{ fontSize: "0.78rem" }}>{r.eft_transaction_id ?? "—"}</td>
                        <td style={{ color: "#64748b" }}>{r.match_method ?? "—"}</td>
                        <td>{r.variance_amount != null ? fmtCad(r.variance_amount) : "—"}</td>
                        <td title={JSON.stringify(r.detail)} style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#64748b", fontSize: "0.75rem" }}>
                          {String((r.detail as Record<string, unknown>)?.reason ?? JSON.stringify(r.detail))}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </TableCard>
            </>
          )}

          {/* ── RULE FINDINGS ── */}
          {page === "findings" && (
            <>
              <p className="text-muted mb-4" style={{ fontSize: "0.875rem" }}>FINTRAC compliance rule evaluation results for this run</p>
              <div className="row row-cols-4 g-3 mb-4">
                <MetricCard label="BREACH" value={breachCount} icon="shield-x" color="danger" sub="Regulatory violations" />
                <MetricCard label="WARN" value={warnCount} icon="exclamation-triangle" color="warning" sub="Compliance gaps" />
                <MetricCard label="INFO" value={infoCount} icon="info-circle" color="primary" sub="Informational flags" />
                <MetricCard label="Total" value={findings.length} icon="list-check" color="success" sub="All findings this run" />
              </div>
              <TableCard title="All Findings"
                controls={<>
                  {filterSelect(findingSevFilter, setFindingSevFilter, [
                    { value: "", label: "All Severities" },
                    { value: "BREACH", label: "BREACH" },
                    { value: "WARN", label: "WARN" },
                    { value: "INFO", label: "INFO" },
                  ])}
                  {filterSelect(findingRuleFilter, setFindingRuleFilter, [
                    { value: "", label: "All Rules" },
                    ...uniqueRuleCodes.map(c => ({ value: c, label: c })),
                  ])}
                </>}>
                <thead className="table-light">
                  <tr><th>Severity</th><th>Rule Code</th><th>Ver.</th><th>Transaction ID</th><th>Finding Detail</th><th>Detected At</th></tr>
                </thead>
                <tbody>
                  {loading ? <LoadingRow cols={6} />
                    : filteredFindings.length === 0 ? <EmptyRow cols={6} message="No findings match this filter" />
                    : filteredFindings.map(f => (
                      <tr key={f.finding_id}>
                        <td><SeverityBadge sev={f.severity} /></td>
                        <td style={{ fontWeight: 500, fontSize: "0.78rem" }}>{f.rule_code}</td>
                        <td style={{ color: "#94a3b8", fontSize: "0.78rem" }}>v{f.rule_version}</td>
                        <td className="font-monospace" style={{ fontSize: "0.78rem" }}>{f.transaction_id ?? "—"}</td>
                        <td title={JSON.stringify(f.detail)} style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#64748b", fontSize: "0.75rem" }}>
                          {String((f.detail as Record<string, unknown>)?.reason ?? JSON.stringify(f.detail))}
                        </td>
                        <td style={{ color: "#64748b", fontSize: "0.75rem" }}>{fmtDate(f.created_at)}</td>
                      </tr>
                    ))}
                </tbody>
              </TableCard>
            </>
          )}

          {/* ── REPERFORMANCE ── */}
          {page === "reperformance" && (
            <>
              <p className="text-muted mb-4" style={{ fontSize: "0.875rem" }}>Independent recalculation of reported amounts using Bank of Canada rates</p>
              <div className="row row-cols-3 g-3 mb-4">
                <MetricCard label="BREACH Variances" value={reperform.filter(r => r.status === "BREACH").length} icon="exclamation-octagon" color="danger" sub="Material differences >1%" />
                <MetricCard label="Minor Variances" value={reperform.filter(r => r.status === "VARIANCE").length} icon="dash-circle" color="warning" sub="Small differences detected" />
                <MetricCard label="Pass" value={reperform.filter(r => r.status === "PASS").length} icon="check-circle" color="success" sub="Amounts confirmed correct" />
              </div>
              <TableCard title="Calculation Comparison"
                controls={<>
                  {filterSelect(reperformTypeFilter, setReperformTypeFilter, [
                    { value: "", label: "All Types" },
                    { value: "THRESHOLD", label: "Threshold" },
                    { value: "AGGREGATION", label: "Aggregation" },
                    { value: "FX", label: "FX Conversion" },
                  ])}
                  {filterSelect(reperformStatusFilter, setReperformStatusFilter, [
                    { value: "", label: "All Statuses" },
                    { value: "BREACH", label: "BREACH" },
                    { value: "VARIANCE", label: "VARIANCE" },
                    { value: "PASS", label: "PASS" },
                  ])}
                </>}>
                <thead className="table-light">
                  <tr><th>Status</th><th>Type</th><th>Reported Value</th><th>Reperformed Value</th><th>Variance $</th><th>Variance %</th><th>Detail</th></tr>
                </thead>
                <tbody>
                  {loading ? <LoadingRow cols={7} />
                    : filteredReperform.length === 0
                    ? <EmptyRow cols={7} message="No reperformance results. Run Phase 2 to generate them: python scripts/run_phase2.py --run-id <id>" />
                    : filteredReperform.map(r => (
                      <tr key={r.result_id}>
                        <td><SeverityBadge sev={r.status} /></td>
                        <td style={{ fontSize: "0.78rem" }}>{r.calculation_type}</td>
                        <td>{fmtCad(r.reported_value)}</td>
                        <td>{fmtCad(r.reperformed_value)}</td>
                        <td style={{ color: (r.variance_absolute ?? 0) > 0 ? "#dc2626" : "#16a34a" }}>{fmtCad(r.variance_absolute)}</td>
                        <td style={{ color: (r.variance_pct ?? 0) > 0.01 ? "#dc2626" : "#16a34a" }}>
                          {r.variance_pct != null ? `${(r.variance_pct * 100).toFixed(2)}%` : "—"}
                        </td>
                        <td title={JSON.stringify(r.detail)} style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#64748b", fontSize: "0.75rem" }}>
                          {JSON.stringify(r.detail)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </TableCard>
            </>
          )}

          {/* ── AUDIT LOG ── */}
          {page === "audit" && (
            <>
              <p className="text-muted mb-4" style={{ fontSize: "0.875rem" }}>Append-only audit trail — every pipeline event recorded for this run</p>
              <TableCard title="Pipeline Events"
                controls={filterSelect(auditSevFilter, setAuditSevFilter, [
                  { value: "", label: "All Severities" },
                  { value: "INFO", label: "INFO" },
                  { value: "WARN", label: "WARN" },
                  { value: "ERROR", label: "ERROR" },
                ])}>
                <thead className="table-light">
                  <tr><th>Time (UTC)</th><th>Severity</th><th>Component</th><th>Event Type</th><th>Message</th></tr>
                </thead>
                <tbody>
                  {loading ? <LoadingRow cols={5} />
                    : filteredAudit.length === 0 ? <EmptyRow cols={5} message="No audit entries found" />
                    : filteredAudit.map(e => (
                      <tr key={e.log_id}>
                        <td style={{ color: "#64748b", fontSize: "0.75rem", whiteSpace: "nowrap" }}>{fmtDate(e.created_at)}</td>
                        <td><SeverityBadge sev={e.severity} /></td>
                        <td style={{ color: "#64748b", fontSize: "0.78rem" }}>{e.component}</td>
                        <td style={{ fontWeight: 500, fontSize: "0.78rem" }}>{e.event_type}</td>
                        <td style={{ fontSize: "0.78rem" }}>{e.message}</td>
                      </tr>
                    ))}
                </tbody>
              </TableCard>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
