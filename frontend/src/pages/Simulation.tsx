import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { api, type Medication } from "../api";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

type LocationState = {
  patientId?: string;
  medicationId?: string;
};

type TherapeuticEval = {
  alerts: string[];
  off_score: number;
  pct_above: number;
  pct_below: number;
  pct_within: number;
  ade_risk_level: string;
  time_within_hr: number;
  time_above_hr: number;
  time_below_hr: number;
};

type SimulationResult = {
  id: string;
  patient_id: string;
  medication_id: string;
  dose_mg: number;
  interval_hr: number;
  duration_hr: number;
  cmax_mg_l: number;
  cmin_mg_l: number;
  auc_mg_h_l: number;
  flag_too_high: boolean;
  flag_too_low: boolean;
  therapeutic_eval: TherapeuticEval;
  times_hr: number[];
  conc_mg_per_L: number[];
};

export default function Simulation() {
  const location = useLocation();
  const { patientId: initialPatientId, medicationId: initialMedId } =
    (location.state as LocationState) || {};

  const [patientId] = useState(initialPatientId || localStorage.getItem("patient_id") || "");

  const [medications, setMedications] = useState<Medication[]>([]);
  const [selectedMedId, setSelectedMedId] = useState<string>("");

  // dosing controls
  const [dose_mg, setDoseMg] = useState(500);
  const [interval_hr, setIntervalHr] = useState(24);
  const [num_doses, setNumDoses] = useState(1);
  const [dt_hr, setDtHr] = useState(0.1);
  const [absorption_rate_hr, setAbsorptionRateHr] = useState<number | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);

  // new-med form
  const [showNewMed, setShowNewMed] = useState(false);
  const [newMedName, setNewMedName] = useState("");
  const [newMedHalfLife, setNewMedHalfLife] = useState("");
  const [newMedClr, setNewMedClr] = useState("");
  const [newMedVd, setNewMedVd] = useState("");
  const [newMedWinLow, setNewMedWinLow] = useState("");
  const [newMedWinHigh, setNewMedWinHigh] = useState("");
  const [savingMed, setSavingMed] = useState(false);
  const [newMedErr, setNewMedErr] = useState<string | null>(null);

  // load medications
  useEffect(() => {
    api
      .listMedications()
      .then((ms) => {
        setMedications(ms);
        if (initialMedId) {
          setSelectedMedId(initialMedId);
        } else if (ms.length > 0) {
          setSelectedMedId(ms[0].id);
        }
      })
      .catch((e: any) => {
        console.error(e);
        setError("Failed to load medications.");
      });
  }, [initialMedId]);

  const handleCreateMedication = async () => {
    setNewMedErr(null);

    if (!newMedName.trim()) {
      setNewMedErr("Medication name is required.");
      return;
    }

    try {
      setSavingMed(true);

      const created = await api.createMedication({
        name: newMedName.trim(),
        half_life_hr: newMedHalfLife ? Number(newMedHalfLife) : undefined,
        clearance_raw_value: newMedClr ? Number(newMedClr) : undefined,
        clearance_raw_unit: newMedClr ? "mL/min/kg" : undefined,
        volume_of_distribution_raw_value: newMedVd ? Number(newMedVd) : undefined,
        volume_of_distribution_raw_unit: newMedVd ? "L/kg" : undefined,
        therapeutic_window_lower_mg_l: newMedWinLow ? Number(newMedWinLow) : undefined,
        therapeutic_window_upper_mg_l: newMedWinHigh ? Number(newMedWinHigh) : undefined,
      });

      setMedications((prev) => [...prev, created]);
      setSelectedMedId(created.id);

      setNewMedName("");
      setNewMedHalfLife("");
      setNewMedClr("");
      setNewMedVd("");
      setNewMedWinLow("");
      setNewMedWinHigh("");
      setShowNewMed(false);
    } catch (e: any) {
      console.error(e);
      setNewMedErr(
        typeof e === "string" ? e : e?.message || "Failed to create medication."
      );
    } finally {
      setSavingMed(false);
    }
  };

  const handleRun = async () => {
    if (!patientId || !selectedMedId) {
      setError("Missing patient or medication.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const payload = {
        patient_id: patientId,
        medication_id: selectedMedId,
        dose_mg,
        interval_hr,
        num_doses,
        dt_hr,
        absorption_rate_hr,
      };

      const data = (await api.runSimulation(payload)) as SimulationResult;
      setResult(data);
    } catch (e: any) {
      setError(typeof e === "string" ? e : e?.message || "Failed to run simulation");
    } finally {
      setLoading(false);
    }
  };

  const chartData =
    result?.times_hr.map((t, i) => ({
      time: t,
      conc: result.conc_mg_per_L[i],
    })) ?? [];

  const selectedMed = medications.find((m) => m.id === selectedMedId);

  return (
    <div style={{ maxWidth: "960px", margin: "0 auto" }}>
      <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.5rem" }}>
        Dosing Simulation
      </h2>
      <p style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
        Patient identifier:{" "}
        <strong>{patientId || "unknown"}</strong>
        {selectedMed && (
          <>
            {" "}– Medication: <strong>{selectedMed.name}</strong>
          </>
        )}
      </p>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          marginBottom: "1rem",
          padding: "1rem",
          borderRadius: "0.75rem",
          border: "1px solid #e5e7eb",
        }}
      >
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <label style={{ fontSize: "0.9rem", display: "flex", flexDirection: "column" }}>
            <span style={{ marginBottom: "0.25rem" }}>Medication</span>
            <select
              value={selectedMedId}
              onChange={(e) => setSelectedMedId(e.target.value)}
              style={{
                padding: "0.3rem 0.6rem",
                borderRadius: "0.5rem",
                border: "1px solid #d1d5db",
                minWidth: "16rem",
              }}
            >
              {medications.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.id})
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={() => setShowNewMed((v) => !v)}
            style={{
              padding: "0.3rem 0.8rem",
              borderRadius: "999px",
              border: "1px solid #111827",
              background: "#fff",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            {showNewMed ? "Cancel" : "＋ Add medication"}
          </button>
        </div>

        {showNewMed && (
          <div
            style={{
              border: "1px dashed #d1d5db",
              borderRadius: "0.75rem",
              padding: "0.75rem",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "0.5rem",
              fontSize: "0.85rem",
            }}
          >
            <FieldText
              label="Name"
              value={newMedName}
              onChange={setNewMedName}
              required
            />
            <FieldText
              label="Half-life (hr)"
              value={newMedHalfLife}
              onChange={setNewMedHalfLife}
            />
            <FieldText
              label="Clearance raw value (mL/min/kg)"
              value={newMedClr}
              onChange={setNewMedClr}
            />
            <FieldText
              label="Vd raw value (L/kg)"
              value={newMedVd}
              onChange={setNewMedVd}
            />
            <FieldText
              label="Therapeutic lower (mg/L)"
              value={newMedWinLow}
              onChange={setNewMedWinLow}
            />
            <FieldText
              label="Therapeutic upper (mg/L)"
              value={newMedWinHigh}
              onChange={setNewMedWinHigh}
            />

            <div style={{ gridColumn: "1 / -1", display: "flex", gap: "0.5rem" }}>
              <button
                type="button"
                onClick={handleCreateMedication}
                disabled={savingMed}
                style={{
                  padding: "0.4rem 0.9rem",
                  borderRadius: "999px",
                  border: "1px solid #111827",
                  background: "#111827",
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: "0.85rem",
                }}
              >
                {savingMed ? "Saving..." : "Save medication"}
              </button>
              {newMedErr && (
                <span style={{ color: "#b91c1c", alignSelf: "center" }}>{newMedErr}</span>
              )}
            </div>
          </div>
        )}

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "1rem",
            alignItems: "flex-end",
          }}
        >
          <FieldNumber
            label="Dose (mg)"
            value={dose_mg}
            onChange={(v) => setDoseMg(Number(v))}
          />
          <FieldNumber
            label="Interval (hr)"
            value={interval_hr}
            onChange={(v) => setIntervalHr(Number(v))}
          />
          <FieldNumber
            label="# of doses"
            value={num_doses}
            onChange={(v) => setNumDoses(Number(v))}
          />
          <FieldNumber
            label="dt (hr)"
            value={dt_hr}
            step={0.01}
            onChange={(v) => setDtHr(Number(v))}
          />
          <FieldNumber
            label="Absorption rate (hr⁻¹, optional)"
            value={absorption_rate_hr ?? ""}
            step={0.01}
            onChange={(v) =>
              setAbsorptionRateHr(v === "" ? null : Number(v))
            }
          />

          <button
            onClick={handleRun}
            disabled={loading}
            style={{
              padding: "0.5rem 1.2rem",
              borderRadius: "999px",
              border: "1px solid #111827",
              background: "#111827",
              color: "white",
              cursor: "pointer",
              marginLeft: "auto",
            }}
          >
            {loading ? "Running..." : "Run Simulation"}
          </button>
        </div>
      </div>

      {error && (
        <p style={{ color: "#b91c1c", marginBottom: "1rem" }}>{error}</p>
      )}

      {result && (
        <>
          <div
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: "0.75rem",
              padding: "1rem",
              marginBottom: "1rem",
            }}
          >
            <h3 style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Summary</h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: "0.5rem",
                fontSize: "0.9rem",
              }}
            >
              <div>Cmax: {result.cmax_mg_l.toFixed(2)} mg/L</div>
              <div>Cmin: {result.cmin_mg_l.toFixed(2)} mg/L</div>
              <div>AUC: {result.auc_mg_h_l.toFixed(1)} mg·h/L</div>
              <div>Duration: {result.duration_hr} h</div>
              <div>Within target: {result.therapeutic_eval.pct_within}%</div>
              <div>Risk: {result.therapeutic_eval.ade_risk_level}</div>
            </div>
            {result.therapeutic_eval.alerts.length > 0 && (
              <ul
                style={{
                  marginTop: "0.5rem",
                  fontSize: "0.9rem",
                  color: "#991b1b",
                }}
              >
                {result.therapeutic_eval.alerts.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            )}
          </div>

          {/* Curve */}
          <div
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: "0.75rem",
              padding: "1rem",
              height: 320,
            }}
          >
            <h3 style={{ fontWeight: 600, marginBottom: "0.5rem" }}>
              Concentration–Time Curve
            </h3>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="time"
                  label={{
                    value: "Time (hr)",
                    position: "insideBottom",
                    offset: -5,
                  }}
                  tick={{ fontSize: 10 }}
                />
                <YAxis
                  label={{
                    value: "Concentration (mg/L)",
                    angle: -90,
                    position: "insideLeft",
                  }}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="conc"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

type FieldNumberProps = {
  label: string;
  value: string | number;
  step?: number;
  onChange: (value: string) => void;
};

function FieldNumber({ label, value, step, onChange }: FieldNumberProps) {
  return (
    <label style={{ display: "flex", flexDirection: "column", fontSize: "0.9rem" }}>
      <span style={{ marginBottom: "0.25rem" }}>{label}</span>
      <input
        type="number"
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: "0.3rem 0.6rem",
          borderRadius: "0.5rem",
          border: "1px solid #d1d5db",
          minWidth: "8rem",
        }}
      />
    </label>
  );
}

type FieldTextProps = {
  label: string;
  value: string;
  required?: boolean;
  onChange: (value: string) => void;
};

function FieldText({ label, value, required, onChange }: FieldTextProps) {
  return (
    <label style={{ display: "flex", flexDirection: "column" }}>
      <span style={{ marginBottom: "0.25rem", fontSize: "0.85rem" }}>
        {label} {required && <span style={{ color: "#b91c1c" }}>*</span>}
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: "0.25rem 0.5rem",
          borderRadius: "0.5rem",
          border: "1px solid #d1d5db",
        }}
      />
    </label>
  );
}
