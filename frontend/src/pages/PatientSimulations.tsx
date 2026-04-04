import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type SharedSimulationDetail, type SharedSimulationSummary } from "../api";
import Navbar from "./Navbar";
import { downloadSimulationPDF } from "./SimulationPDFExport";

export default function PatientSimulations() {
  const nav = useNavigate();
  const [rows, setRows] = useState<SharedSimulationSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [detail, setDetail] = useState<SharedSimulationDetail | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [pdfLoading, setPdfLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const token = localStorage.getItem("patient_token") || "";

  useEffect(() => {
    if (!token) {
      nav("/patient-login");
      return;
    }
    setLoading(true);
    api
      .listMySharedSimulations(token)
      .then((data) => {
        setRows(data);
        if (data.length > 0) setSelectedId(data[0].id);
      })
      .catch((e: any) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [nav, token]);

  useEffect(() => {
    if (!token || !selectedId) {
      setDetail(null);
      return;
    }
    api
      .getMySharedSimulation(token, selectedId)
      .then(setDetail)
      .catch((e: any) => setErr(String(e)));
  }, [selectedId, token]);

  const chartData = useMemo(
    () =>
      (detail?.times_hr || []).map((t, i) => ({
        time: t,
        conc: detail?.conc_mg_per_L?.[i] ?? null,
      })),
    [detail]
  );

  const evalData = (detail?.therapeutic_eval || {}) as Record<string, unknown>;
  const pctWithin = typeof evalData.pct_within === "number" ? evalData.pct_within : null;
  const pctAbove  = typeof evalData.pct_above  === "number" ? evalData.pct_above  : null;
  const pctBelow  = typeof evalData.pct_below  === "number" ? evalData.pct_below  : null;
  const riskLevel = typeof evalData.ade_risk_level === "string" ? evalData.ade_risk_level : null;
  const alerts    = Array.isArray(evalData.alerts) ? (evalData.alerts as string[]) : [];

  // ── PDF handler ────────────────────────────────────────────────────────────
  const handleDownloadPDF = async () => {
    if (!detail) return;
    setPdfLoading(true);
    try {
      await downloadSimulationPDF(detail, chartRef);
    } finally {
      setPdfLoading(false);
    }
  };

  function onSignOut() {
    localStorage.removeItem("patient_token");
    localStorage.removeItem("patient_email");
    nav("/patient-login");
  }

  return (
    <>
      <Navbar />
      <div style={{ maxWidth: "960px", margin: "0 auto" }}>
        <h2>Received Simulations</h2>
        <p style={{ fontSize: "0.9rem", color: "#555" }}>
          Email: <strong>{localStorage.getItem("patient_email") || "unknown"}</strong>
        </p>
        <button onClick={onSignOut} style={{ marginBottom: "1rem" }}>
          Sign Out
        </button>

        {loading && <p>Loading...</p>}
        {err && <p style={{ color: "red" }}>{err}</p>}
        {!loading && rows.length === 0 && <p>No simulations have been shared with you yet.</p>}

        {rows.length > 0 && (
          <div
            style={{
              border: "1px solid #ddd",
              borderRadius: "0.75rem",
              padding: "0.75rem",
              marginBottom: "1rem",
            }}
          >
            <label>
              Choose simulation
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                style={{ marginLeft: "0.5rem" }}
              >
                {rows.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.medication_name || "Medication"} | {r.shared_at || r.created_at}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        {detail && (
          <>
            <div
              style={{
                border: "1px solid #ddd",
                borderRadius: "0.75rem",
                padding: "1rem",
                marginBottom: "1rem",
              }}
            >
              <h3 style={{ marginTop: 0 }}>{detail.medication_name || "Simulation"}</h3>
              <div style={{ fontSize: "0.9rem" }}>
                <div>Shared by: {detail.shared_by || "Unknown clinician"}</div>
                <div>Shared at: {detail.shared_at || "Unknown"}</div>
                <div style={{ marginTop: "0.5rem" }}>
                  Your current plan: <strong>{detail.dose_mg ?? "n/a"} mg</strong> every{" "}
                  <strong>{detail.interval_hr ?? "n/a"} hours</strong>
                </div>
                <div style={{ marginTop: "0.5rem" }}>
                  Time in target range:{" "}
                  <strong>{pctWithin != null ? `${pctWithin}%` : "n/a"}</strong>
                </div>
                <div>
                  Time above safe range:{" "}
                  <strong>{pctAbove != null ? `${pctAbove}%` : "n/a"}</strong>
                </div>
                <div>
                  Time below effective range:{" "}
                  <strong>{pctBelow != null ? `${pctBelow}%` : "n/a"}</strong>
                </div>
                {riskLevel && (
                  <div style={{ marginTop: "0.5rem" }}>
                    Overall risk level: <strong>{riskLevel.toUpperCase()}</strong>
                  </div>
                )}
                {alerts.length > 0 && (
                  <div style={{ marginTop: "0.5rem" }}>
                    <div style={{ fontWeight: 600 }}>What this means for you:</div>
                    <ul style={{ marginTop: "0.2rem" }}>
                      {alerts.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div style={{ marginTop: "0.5rem", color: "#555" }}>
                  This chart shows how medicine levels may rise and fall between doses.
                </div>
              </div>
            </div>

          {/* ── Chart (ref attached here for PDF screenshot) ── */}
          <div
            ref={chartRef}
            style={{ border: "1px solid #ddd", borderRadius: "0.75rem", padding: "1rem", height: 320 }}
          >
            <h3 style={{ marginTop: 0 }}>Concentration-Time Curve</h3>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="conc" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* ── Download button ── */}
          <button
            onClick={handleDownloadPDF}
            disabled={pdfLoading}
            style={{ marginTop: "1rem" }}
          >
            {pdfLoading ? "Generating PDF..." : "⬇ Download PDF Report"}
          </button>
        </>
      )}
    </div>
    </>
  );
}
