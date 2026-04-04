import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { api, type Medication, type PkFetchResponse, type WindowReview } from "../api";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import Navbar from "../pages/Navbar";

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

type PatientContext = {
  patient_id: string;
  age?: number | null;
  sex?: string | null;
  weight_kg?: number | null;
  serum_creatinine_mg_dl?: number | null;
  creatinine_clearance_ml_min?: number | null;
  ckd_stage?: string | null;
  height_cm?: number | null;
  is_pregnant?: boolean | null;
  pregnancy_trimester?: string | null;
  is_breastfeeding?: boolean | null;
  liver_disease_status?: string | null;
  albumin_g_dl?: number | null;
  systolic_bp_mm_hg?: number | null;
  diastolic_bp_mm_hg?: number | null;
  heart_rate_bpm?: number | null;
  conditions?: string[] | null;
  current_medications?: string[] | null;
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
  patient_context?: PatientContext;
  ade_screening?: {
    medication: string;
    matched_rule: boolean;
    risk_level: string;
    alerts: string[];
    findings: Array<{
      category: string;
      severity: string;
      matched: string;
      message: string;
    }>;
  };
  therapeutic_window?: {
    lower_mg_l?: number;
    upper_mg_l?: number;
    source?: string;
  };
  therapeutic_eval: TherapeuticEval;
  params_used?: {
    suggested_input_dose_mg_for_mid_window?: number | null;
    dose_input_mg?: number;
    dose_modeled_mg?: number;
    active_moiety_fraction?: number;
    recommended_regimens?: Array<{
      dose_mg: number;
      interval_hr: number;
      num_doses: number;
      pct_within: number;
      pct_below: number;
      pct_above: number;
      risk: string;
      meets_goal_96pct: boolean;
    }>;
  };
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
  const [fetchingPk, setFetchingPk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  //const [result, setResult] = useState<SimulationResult | null>(null);
  const [results, setResults] = useState<SimulationResult[]>([]);
  const result = results.length > 0 ? results[results.length - 1] : null;
  const [pkFetchResult, setPkFetchResult] = useState<PkFetchResponse | null>(null);
  const [fetchMedName, setFetchMedName] = useState("");
  const [fetchUpsert, setFetchUpsert] = useState(true);
  const [windowReview, setWindowReview] = useState<WindowReview | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectNotes, setRejectNotes] = useState("");
  const [manualLow, setManualLow] = useState("");
  const [manualHigh, setManualHigh] = useState("");
  const [queueCount, setQueueCount] = useState<number>(0);

  // new-med form
  const [showNewMed, setShowNewMed] = useState(false);
  const [newMedName, setNewMedName] = useState("");
  const [newMedGenericName, setNewMedGenericName] = useState("");
  const [newMedHalfLife, setNewMedHalfLife] = useState("");
  const [newMedBioavailability, setNewMedBioavailability] = useState("");
  const [newMedClr, setNewMedClr] = useState("");
  const [newMedClrUnit, setNewMedClrUnit] = useState("mL/min/kg");
  const [newMedVd, setNewMedVd] = useState("");
  const [newMedVdUnit, setNewMedVdUnit] = useState("L/kg");
  const [newMedWinLow, setNewMedWinLow] = useState("");
  const [newMedWinHigh, setNewMedWinHigh] = useState("");
  const [newMedSourceUrl, setNewMedSourceUrl] = useState("");
  const [savingMed, setSavingMed] = useState(false);
  const [newMedErr, setNewMedErr] = useState<string | null>(null);
  const [showEditMed, setShowEditMed] = useState(false);
  const [editMedGenericName, setEditMedGenericName] = useState("");
  const [editMedHalfLife, setEditMedHalfLife] = useState("");
  const [editMedBioavailability, setEditMedBioavailability] = useState("");
  const [editMedClrRawValue, setEditMedClrRawValue] = useState("");
  const [editMedClrRawUnit, setEditMedClrRawUnit] = useState("");
  const [editMedVdRawValue, setEditMedVdRawValue] = useState("");
  const [editMedVdRawUnit, setEditMedVdRawUnit] = useState("");
  const [editMedWinLow, setEditMedWinLow] = useState("");
  const [editMedWinHigh, setEditMedWinHigh] = useState("");
  const [editMedSourceUrl, setEditMedSourceUrl] = useState("");
  const [updatingMed, setUpdatingMed] = useState(false);
  const [deletingMed, setDeletingMed] = useState(false);
  const [editMedErr, setEditMedErr] = useState<string | null>(null);
  const [shareEmail, setShareEmail] = useState(localStorage.getItem("patient_email") || "");
  const [shareBusy, setShareBusy] = useState(false);
  const [shareMsg, setShareMsg] = useState<string | null>(null);

  // load medications
  useEffect(() => {
    api
      .listSimulationMedications()
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

  useEffect(() => {
    if (!selectedMedId) return;
    setReviewLoading(true);
    api
      .getMedicationWindowReview(selectedMedId)
      .then((r) => setWindowReview(r))
      .catch(() => setWindowReview(null))
      .finally(() => setReviewLoading(false));
  }, [selectedMedId]);

  useEffect(() => {
    api
      .listWindowReviewQueue()
      .then((rows) => setQueueCount(rows.length))
      .catch(() => setQueueCount(0));
  }, [windowReview]);

  useEffect(() => {
    const med = medications.find((m) => m.id === selectedMedId);
    if (!med) return;
    setEditMedGenericName(med.generic_name ?? "");
    setEditMedHalfLife(med.half_life_hr != null ? String(med.half_life_hr) : "");
    setEditMedBioavailability(med.bioavailability_f != null ? String(med.bioavailability_f) : "");
    setEditMedClrRawValue(med.clearance_raw_value != null ? String(med.clearance_raw_value) : "");
    setEditMedClrRawUnit(med.clearance_raw_unit ?? "");
    setEditMedVdRawValue(
      med.volume_of_distribution_raw_value != null
        ? String(med.volume_of_distribution_raw_value)
        : ""
    );
    setEditMedVdRawUnit(med.volume_of_distribution_raw_unit ?? "");
    setEditMedWinLow(
      med.therapeutic_window_lower_mg_l != null
        ? String(med.therapeutic_window_lower_mg_l)
        : ""
    );
    setEditMedWinHigh(
      med.therapeutic_window_upper_mg_l != null
        ? String(med.therapeutic_window_upper_mg_l)
        : ""
    );
    setEditMedSourceUrl(med.source_url ?? "");
    setEditMedErr(null);
  }, [selectedMedId, medications]);

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
        generic_name: newMedGenericName.trim() || undefined,
        half_life_hr: newMedHalfLife ? Number(newMedHalfLife) : undefined,
        bioavailability_f: newMedBioavailability ? Number(newMedBioavailability) : undefined,
        clearance_raw_value: newMedClr ? Number(newMedClr) : undefined,
        clearance_raw_unit: newMedClr ? (newMedClrUnit.trim() || "mL/min/kg") : undefined,
        volume_of_distribution_raw_value: newMedVd ? Number(newMedVd) : undefined,
        volume_of_distribution_raw_unit: newMedVd ? (newMedVdUnit.trim() || "L/kg") : undefined,
        therapeutic_window_lower_mg_l: newMedWinLow ? Number(newMedWinLow) : undefined,
        therapeutic_window_upper_mg_l: newMedWinHigh ? Number(newMedWinHigh) : undefined,
        source_url: newMedSourceUrl.trim() || undefined,
      });
      const refreshed = await api.listSimulationMedications();
      setMedications(refreshed);
      const matched = refreshed.find((m) => m.id === created.id);
      setSelectedMedId(matched?.id || created.id);

      setNewMedName("");
      setNewMedGenericName("");
      setNewMedHalfLife("");
      setNewMedBioavailability("");
      setNewMedClr("");
      setNewMedClrUnit("mL/min/kg");
      setNewMedVd("");
      setNewMedVdUnit("L/kg");
      setNewMedWinLow("");
      setNewMedWinHigh("");
      setNewMedSourceUrl("");
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
      setResults((prev) => [...prev, data]);
    } catch (e: any) {
      setError(typeof e === "string" ? e : e?.message || "Failed to run simulation");
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (sim: SimulationResult) => {
    try {
      await fetch(
        `/api/sims/accept?patient_id=${sim.patient_id}&medication_id=${sim.medication_id}&simulation_id=${sim.id}`,
       {
          method: "POST",
        }
      );

      alert("Simulation accepted!");
    } catch (error) {
      console.error(error);
      alert("Failed to accept simulation");
    }
  };

  const handleShare = async () => {
    if (results.length === 0) {
      setShareMsg("Run a simulation before sharing.");
      return;
    }
    const clinicianEmail = (localStorage.getItem("clinician_email") || "").trim().toLowerCase();
    if (!clinicianEmail) {
      setShareMsg("Missing clinician identity. Sign in again.");
      return;
    }
    if (!shareEmail.trim()) {
      setShareMsg("Enter patient email.");
      return;
    }

    try {
      setShareBusy(true);
      setShareMsg(null);
      const latest = results[results.length - 1];
      await api.shareSimulation(latest.id, {
        patient_email: shareEmail.trim().toLowerCase(),
        clinician_email: clinicianEmail,
      });
      setShareMsg("Simulation shared successfully.");
    } catch (e: any) {
      setShareMsg(typeof e === "string" ? e : e?.message || "Failed to share simulation.");
    } finally {
      setShareBusy(false);
    }
  };

  const handleUpdateMedication = async () => {
    setEditMedErr(null);
    if (!selectedMed) {
      setEditMedErr("Select a medication first.");
      return;
    }
    try {
      setUpdatingMed(true);
      await api.updateMedication(selectedMed.name, {
        generic_name: editMedGenericName.trim() || undefined,
        half_life_hr: editMedHalfLife.trim() ? Number(editMedHalfLife) : undefined,
        bioavailability_f: editMedBioavailability.trim()
          ? Number(editMedBioavailability)
          : undefined,
        clearance_raw_value: editMedClrRawValue.trim()
          ? Number(editMedClrRawValue)
          : undefined,
        clearance_raw_unit: editMedClrRawUnit.trim() || undefined,
        volume_of_distribution_raw_value: editMedVdRawValue.trim()
          ? Number(editMedVdRawValue)
          : undefined,
        volume_of_distribution_raw_unit: editMedVdRawUnit.trim() || undefined,
        therapeutic_window_lower_mg_l: editMedWinLow.trim() ? Number(editMedWinLow) : undefined,
        therapeutic_window_upper_mg_l: editMedWinHigh.trim()
          ? Number(editMedWinHigh)
          : undefined,
        source_url: editMedSourceUrl.trim() || undefined,
      });
      const refreshed = await api.listSimulationMedications();
      setMedications(refreshed);
      const stillSelected = refreshed.find((m) => m.id === selectedMedId);
      if (!stillSelected && refreshed.length > 0) {
        setSelectedMedId(refreshed[0].id);
      }
    } catch (e: any) {
      setEditMedErr(typeof e === "string" ? e : e?.message || "Failed to update medication.");
    } finally {
      setUpdatingMed(false);
    }
  };

  const handleDeleteMedication = async () => {
    setEditMedErr(null);
    if (!selectedMed) {
      setEditMedErr("Select a medication first.");
      return;
    }
    const ok = window.confirm(
      `Delete medication "${selectedMed.name}"? This also removes related simulation and patient-medication link rows.`
    );
    if (!ok) return;

    try {
      setDeletingMed(true);
      await api.deleteMedication(selectedMed.name);
      const refreshed = await api.listSimulationMedications();
      setMedications(refreshed);
      setResults([]);
      setWindowReview(null);
      if (refreshed.length > 0) {
        setSelectedMedId(refreshed[0].id);
      } else {
        setSelectedMedId("");
      }
      setShowEditMed(false);
    } catch (e: any) {
      setEditMedErr(typeof e === "string" ? e : e?.message || "Failed to delete medication.");
    } finally {
      setDeletingMed(false);
    }
  };

  const handleFetchPk = async () => {
    setError(null);
    setPkFetchResult(null);

    const targetName = fetchMedName.trim();
    if (!targetName) {
      setError("Enter a medication name in 'Fetch PK For'.");
      return;
    }

    try {
      setFetchingPk(true);
      const fetched = await api.fetchMedicationPk(targetName, fetchUpsert);
      setPkFetchResult(fetched);

      if (fetchUpsert) {
        const refreshed = await api.listSimulationMedications();
        setMedications(refreshed);
        const matched = refreshed.find(
          (m) => m.name.toLowerCase() === targetName.toLowerCase()
        );
        if (matched) {
          setSelectedMedId(matched.id);
          const review = await api.getMedicationWindowReview(matched.id);
          setWindowReview(review);
        }
      }
    } catch (e: any) {
      setError(typeof e === "string" ? e : e?.message || "Failed to fetch PK data");
    } finally {
      setFetchingPk(false);
    }
  };

  const handleApproveWindow = async () => {
    if (!selectedMedId) return;
    try {
      setReviewBusy(true);
      const row = await api.approveMedicationWindowReview(selectedMedId);
      setWindowReview(row);
      setShowRejectForm(false);
    } catch (e: any) {
      setError(typeof e === "string" ? e : e?.message || "Failed to approve window");
    } finally {
      setReviewBusy(false);
    }
  };

  const handleRejectWindow = async () => {
    if (!selectedMedId) return;
    try {
      setReviewBusy(true);
      const body: {
        notes?: string;
        manual_lower_mg_l?: number;
        manual_upper_mg_l?: number;
      } = {};
      if (rejectNotes.trim()) body.notes = rejectNotes.trim();
      if (manualLow.trim() || manualHigh.trim()) {
        body.manual_lower_mg_l = Number(manualLow);
        body.manual_upper_mg_l = Number(manualHigh);
      }
      const row = await api.rejectMedicationWindowReview(selectedMedId, body);
      setWindowReview(row);
      setShowRejectForm(false);
      setManualLow("");
      setManualHigh("");
      setRejectNotes("");
    } catch (e: any) {
      setError(typeof e === "string" ? e : e?.message || "Failed to reject window");
    } finally {
      setReviewBusy(false);
    }
  };

  const chartData =
    result?.times_hr.map((t, i) => ({
      time: t,
      conc: result.conc_mg_per_L[i],
    })) ?? [];

  const selectedMed = medications.find((m) => m.id === selectedMedId);

  return (
  <>
    <Navbar />
      <div style={{ maxWidth: "960px", margin: "0 auto" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.5rem" }}>
          Dosing Simulation
        </h2>
        <p style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
          Patient identifier:{" "}
          <strong>{patientId || "unknown"}</strong>
          {selectedMed && (
            <>
              {" "} - Medication: <strong>{selectedMed.name}</strong>
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
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: "0.9rem", display: "flex", flexDirection: "column" }}>
              <span style={{ marginBottom: "0.25rem" }}>Fetch PK For</span>
              <input
                type="text"
                placeholder="Medication name (required)"
                value={fetchMedName}
                onChange={(e) => setFetchMedName(e.target.value)}
                style={{
                  padding: "0.3rem 0.6rem",
                  borderRadius: "0.5rem",
                  border: "1px solid #d1d5db",
                  minWidth: "16rem",
                }}
              />
            </label>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                fontSize: "0.85rem",
              }}
            >
              <input
                type="checkbox"
                checked={fetchUpsert}
                onChange={(e) => setFetchUpsert(e.target.checked)}
              />
              Upsert into DB
            </label>
              
            <button
              type="button"
              onClick={handleFetchPk}
              disabled={fetchingPk}
              style={{
                padding: "0.3rem 0.8rem",
                borderRadius: "999px",
                border: "1px solid #111827",
                background: "#111827",
                color: "#fff",
                cursor: "pointer",
                fontSize: "0.8rem",
                marginTop: 0,
              }}
            >
              {fetchingPk ? "Fetching PK..." : "Fetch PK"}
            </button>

            <button
              type="button"
              onClick={() => setShowNewMed((v) => !v)}
              style={{
                padding: "0.3rem 0.8rem",
                borderRadius: "999px",
                border: "1px solid #111827",
                background: "#111827",
                color: "#fff",
                cursor: "pointer",
                fontSize: "0.8rem",
                marginTop: 0,
              }}
            >
              {showNewMed ? "Cancel" : "+ Add medication"}
            </button>
            <button
              type="button"
              onClick={() => setShowEditMed((v) => !v)}
              disabled={!selectedMedId}
              style={{
                padding: "0.3rem 0.8rem",
                borderRadius: "999px",
                border: "1px solid #111827",
                background: "#111827",
                color: "#fff",
                cursor: "pointer",
                fontSize: "0.8rem",
                marginTop: 0,
              }}
            >
              {showEditMed ? "Close edit" : "Edit selected"}
            </button>
          </div>

          {pkFetchResult && (
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: "0.75rem",
                padding: "0.75rem",
                fontSize: "0.85rem",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: "0.4rem" }}>Fetched PK Values</div>
              <div>Half-life: {pkFetchResult.half_life_hr ?? "n/a"} hr</div>
              <div>Clearance: {pkFetchResult.clearance_L_per_hr ?? "n/a"} L/hr</div>
              <div>Vd: {pkFetchResult.Vd_L ?? "n/a"} L</div>
              <div>Bioavailability: {pkFetchResult.bioavailability ?? "n/a"}</div>
              <div>
                Scraped range: {pkFetchResult.therapeutic_window_lower_mg_l ?? "n/a"} - {pkFetchResult.therapeutic_window_upper_mg_l ?? "n/a"} mg/L
              </div>
              {pkFetchResult.window_review && (
                <>
                  <div>
                    Proposed window: {pkFetchResult.window_review.lower_mg_l ?? "n/a"} - {pkFetchResult.window_review.upper_mg_l ?? "n/a"} mg/L
                  </div>
                  <div>
                    Review status: {pkFetchResult.window_review.status} | Source: {pkFetchResult.window_review.source ?? "n/a"} | Confidence: {pkFetchResult.window_review.confidence_pct ?? "n/a"}%
                  </div>
                </>
              )}
              <div style={{ marginTop: "0.4rem" }}>
                Source summary: {pkFetchResult.sources ? JSON.stringify(pkFetchResult.sources) : "n/a"}
              </div>
            </div>
          )}

          <div
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: "0.75rem",
              padding: "0.75rem",
              fontSize: "0.85rem",
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Therapeutic Window Review</div>
            <div style={{ marginBottom: "0.25rem" }}>
              Queue pending manual entry: <strong>{queueCount}</strong>
            </div>
            {reviewLoading && <div>Loading review...</div>}
            {!reviewLoading && windowReview && (
              <>
                <div>Status: <strong>{windowReview.status}</strong></div>
                <div>
                  Proposed range: {windowReview.lower_mg_l ?? "n/a"} - {windowReview.upper_mg_l ?? "n/a"} mg/L
                </div>
                <div>Source: {windowReview.source ?? "n/a"} | Confidence: {windowReview.confidence_pct ?? "n/a"}%</div>
                {windowReview.reviewer_notes && <div>Notes: {windowReview.reviewer_notes}</div>}
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={handleApproveWindow}
                    disabled={reviewBusy}
                    style={{
                      padding: "0.3rem 0.8rem",
                      borderRadius: "999px",
                      border: "1px solid #111827",
                      background: "#111827",
                      color: "#fff",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                    }}
                  >
                    {reviewBusy ? "Saving..." : "Approve"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRejectForm((v) => !v)}
                    disabled={reviewBusy}
                    style={{
                      padding: "0.3rem 0.8rem",
                      borderRadius: "999px",
                      border: "1px solid #991b1b",
                      background: "#991b1b",
                      color: "#fff",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                    }}
                  >
                    Reject
                  </button>
                </div>
                {showRejectForm && (
                  <div
                    style={{
                      marginTop: "0.5rem",
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                      gap: "0.5rem",
                    }}
                  >
                    <FieldText label="Manual lower mg/L" value={manualLow} onChange={setManualLow} />
                    <FieldText label="Manual upper mg/L" value={manualHigh} onChange={setManualHigh} />
                    <FieldText label="Reject note (optional)" value={rejectNotes} onChange={setRejectNotes} />
                    <div style={{ gridColumn: "1 / -1" }}>
                      <button
                        type="button"
                        onClick={handleRejectWindow}
                        disabled={reviewBusy}
                        style={{
                          padding: "0.3rem 0.8rem",
                          borderRadius: "999px",
                          border: "1px solid #991b1b",
                          background: "#991b1b",
                          color: "#fff",
                          cursor: "pointer",
                          fontSize: "0.8rem",
                        }}
                      >
                        {reviewBusy ? "Saving..." : "Submit Reject"}
                      </button>
                      <span style={{ marginLeft: "0.5rem", color: "#7f1d1d" }}>
                        If you reject without manual values, this stays in manual_required queue.
                      </span>
                    </div>
                  </div>
                )}
              </>
            )}
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
                label="Generic name"
                value={newMedGenericName}
                onChange={setNewMedGenericName}
              />
              <FieldText
                label="Half-life (hr)"
                value={newMedHalfLife}
                onChange={setNewMedHalfLife}
              />
              <FieldText
                label="Bioavailability (0-1)"
                value={newMedBioavailability}
                onChange={setNewMedBioavailability}
              />
              <FieldText
                label="Clearance raw value"
                value={newMedClr}
                onChange={setNewMedClr}
              />
              <FieldText
                label="Clearance raw unit"
                value={newMedClrUnit}
                onChange={setNewMedClrUnit}
              />
              <FieldText
                label="Vd raw value"
                value={newMedVd}
                onChange={setNewMedVd}
              />
              <FieldText
                label="Vd raw unit"
                value={newMedVdUnit}
                onChange={setNewMedVdUnit}
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
              <FieldText
                label="Source URL"
                value={newMedSourceUrl}
                onChange={setNewMedSourceUrl}
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

          {showEditMed && selectedMed && (
            <div
              style={{
                border: "1px dashed #d1d5db",
                borderRadius: "0.75rem",
                padding: "0.75rem",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "0.5rem",
                fontSize: "0.85rem",
              }}
            >
              <div style={{ gridColumn: "1 / -1", fontWeight: 600 }}>
                Edit medication: {selectedMed.name}
              </div>
              <FieldText
                label="Generic name"
                value={editMedGenericName}
                onChange={setEditMedGenericName}
              />
              <FieldText
                label="Half-life (hr)"
                value={editMedHalfLife}
                onChange={setEditMedHalfLife}
              />
              <FieldText
                label="Bioavailability (0-1)"
                value={editMedBioavailability}
                onChange={setEditMedBioavailability}
              />
              <FieldText
                label="Clearance raw value"
                value={editMedClrRawValue}
                onChange={setEditMedClrRawValue}
              />
              <FieldText
                label="Clearance raw unit"
                value={editMedClrRawUnit}
                onChange={setEditMedClrRawUnit}
              />
              <FieldText
                label="Vd raw value"
                value={editMedVdRawValue}
                onChange={setEditMedVdRawValue}
              />
              <FieldText
                label="Vd raw unit"
                value={editMedVdRawUnit}
                onChange={setEditMedVdRawUnit}
              />
              <FieldText
                label="Therapeutic lower (mg/L)"
                value={editMedWinLow}
                onChange={setEditMedWinLow}
              />
              <FieldText
                label="Therapeutic upper (mg/L)"
                value={editMedWinHigh}
                onChange={setEditMedWinHigh}
              />
              <FieldText
                label="Source URL"
                value={editMedSourceUrl}
                onChange={setEditMedSourceUrl}
              />
              <div style={{ gridColumn: "1 / -1", display: "flex", gap: "0.5rem" }}>
                <button
                  type="button"
                  onClick={handleUpdateMedication}
                  disabled={updatingMed || deletingMed}
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
                  {updatingMed ? "Saving..." : "Save changes"}
                </button>
                <button
                  type="button"
                  onClick={handleDeleteMedication}
                  disabled={updatingMed || deletingMed}
                  style={{
                    padding: "0.4rem 0.9rem",
                    borderRadius: "999px",
                    border: "1px solid #991b1b",
                    background: "#991b1b",
                    color: "#fff",
                    cursor: "pointer",
                    fontSize: "0.85rem",
                  }}
                >
                  {deletingMed ? "Deleting..." : "Delete medication"}
                </button>
                {editMedErr && (
                  <span style={{ color: "#b91c1c", alignSelf: "center" }}>{editMedErr}</span>
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
              label="Absorption rate (hr^-1, optional)"
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
                <div>AUC: {result.auc_mg_h_l.toFixed(1)} mg*h/L</div>
                <div>Duration: {result.duration_hr} h</div>
                <div>Within target: {result.therapeutic_eval.pct_within}%</div>
                <div>Risk: {result.therapeutic_eval.ade_risk_level}</div>
              </div>
              {result.therapeutic_window && (
                <div style={{ marginTop: "0.5rem", fontSize: "0.88rem" }}>
                  Target window: {result.therapeutic_window.lower_mg_l ?? "n/a"} - {result.therapeutic_window.upper_mg_l ?? "n/a"} mg/L
                  {" "}({result.therapeutic_window.source ?? "unknown"})
                </div>
              )}
              {result.ade_screening && (
                <div style={{ marginTop: "0.5rem", fontSize: "0.88rem" }}>
                  ADE screening risk: <strong>{result.ade_screening.risk_level.toUpperCase()}</strong>
                </div>
              )}
              {result.params_used?.suggested_input_dose_mg_for_mid_window != null && (
                <div style={{ marginTop: "0.25rem", fontSize: "0.88rem" }}>
                  Suggested dose for mid-window: {result.params_used.suggested_input_dose_mg_for_mid_window.toFixed(1)} mg every {result.interval_hr} hr
                </div>
              )}
              {result.params_used?.recommended_regimens && result.params_used.recommended_regimens.length > 0 && (
                <div style={{ marginTop: "0.5rem", fontSize: "0.88rem" }}>
                  <div style={{ fontWeight: 600, marginBottom: "0.2rem" }}>Try These Regimens</div>
                  {result.params_used.recommended_regimens.map((r, idx) => (
                    <div key={idx}>
                      {r.dose_mg} mg q{r.interval_hr}h x{r.num_doses} doses | within: {r.pct_within.toFixed(1)}% | risk: {r.risk}
                      {r.meets_goal_96pct ? " | meets 96% goal" : ""}
                    </div>
                  ))}
                </div>
              )}
              {result.patient_context && (
                <div style={{ marginTop: "0.75rem", fontSize: "0.88rem" }}>
                  <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>
                    Patient Context Used
                  </div>
                  <div>
                    Age: {result.patient_context.age ?? "n/a"} | Sex: {result.patient_context.sex ?? "n/a"} | Weight: {result.patient_context.weight_kg ?? "n/a"} kg
                  </div>
                  <div>
                    SCr: {result.patient_context.serum_creatinine_mg_dl ?? "n/a"} mg/dL | CrCl: {result.patient_context.creatinine_clearance_ml_min ?? "n/a"} mL/min | CKD: {result.patient_context.ckd_stage ?? "n/a"}
                  </div>
                  <div>
                    Height: {result.patient_context.height_cm ?? "n/a"} cm | Pregnant: {result.patient_context.is_pregnant == null ? "n/a" : result.patient_context.is_pregnant ? "yes" : "no"} | Trimester: {result.patient_context.pregnancy_trimester ?? "n/a"}
                  </div>
                  <div>
                    Breastfeeding: {result.patient_context.is_breastfeeding == null ? "n/a" : result.patient_context.is_breastfeeding ? "yes" : "no"} | Liver: {result.patient_context.liver_disease_status ?? "n/a"} | Albumin: {result.patient_context.albumin_g_dl ?? "n/a"} g/dL
                  </div>
                  <div>
                    BP: {result.patient_context.systolic_bp_mm_hg ?? "n/a"}/{result.patient_context.diastolic_bp_mm_hg ?? "n/a"} mmHg | HR: {result.patient_context.heart_rate_bpm ?? "n/a"} bpm
                  </div>
                  <div>
                    Conditions: {(result.patient_context.conditions && result.patient_context.conditions.length > 0) ? result.patient_context.conditions.join(", ") : "n/a"}
                  </div>
                  <div>
                    Current meds: {(result.patient_context.current_medications && result.patient_context.current_medications.length > 0) ? result.patient_context.current_medications.join(", ") : "n/a"}
                  </div>
                </div>
              )}
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
              {result.ade_screening?.findings && result.ade_screening.findings.length > 0 && (
                <div
                  style={{
                    marginTop: "0.5rem",
                    fontSize: "0.88rem",
                    color: "#dc2626",
                    borderLeft: "3px solid #ef4444",
                    paddingLeft: "0.6rem",
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: "0.2rem" }}>Medication Safety Findings</div>
                  {result.ade_screening.findings.map((f, i) => (
                    <div key={i}>
                      [{f.severity.toUpperCase()}] {f.category}: {f.message}
                    </div>
                  ))}
                </div>
              )}
              <div
                style={{
                  marginTop: "0.75rem",
                  borderTop: "1px solid #e5e7eb",
                  paddingTop: "0.75rem",
                }}
              >
                <button
                  style={{
                    marginBottom: "0.75rem",
                    padding: "0.4rem 0.9rem",
                    borderRadius: "999px",
                    border: "1px solid green",
                    background: "green",
                    color: "#fff",
                    cursor: "pointer",
                  }}
                  onClick={() => handleAccept(result)}
                >
                  Accept This Simulation
                </button>
                <div style={{ fontWeight: 600, marginBottom: "0.3rem" }}>Send To Patient</div>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                  <input
                    placeholder="patient email"
                    value={shareEmail}
                    onChange={(e) => setShareEmail(e.target.value)}
                    style={{
                      padding: "0.35rem 0.6rem",
                      borderRadius: "0.5rem",
                      border: "1px solid #d1d5db",
                      minWidth: "260px",
                    }}
                  />
                  <button
                    onClick={handleShare}
                    disabled={shareBusy}
                    style={{
                      padding: "0.4rem 0.9rem",
                      borderRadius: "999px",
                      border: "1px solid #111827",
                      background: "#111827",
                      color: "#fff",
                      cursor: "pointer",
                    }}
                  >
                    {shareBusy ? "Sending..." : "Send Simulation"}
                  </button>
                </div>
                {shareMsg && <div style={{ marginTop: "0.35rem", fontSize: "0.88rem" }}>{shareMsg}</div>}
              </div>
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
                Concentration-Time Curve
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
        {results.length > 1 && (
          <div style={{ marginTop: "2rem" }}>
          <h3>Previous Simulation Runs</h3>

            {results.map((sim) => (
              <div
                key={sim.id}
                style={{
                  border: "1px solid #ccc",
                  padding: "10px",
                  marginBottom: "10px",
                  borderRadius: "8px",
                }}
              >
                <div><strong>Dose:</strong> {sim.dose_mg} mg</div>
                <div><strong>Interval:</strong> {sim.interval_hr} hr</div>
              
                <button onClick={() => handleAccept(sim)}>
                  Accept This One
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
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




