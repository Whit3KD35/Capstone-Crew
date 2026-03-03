import { useNavigate } from "react-router-dom";
import { type ChangeEvent, useEffect, useState } from "react";
import { api } from "../api";

type Patient = {
  id: string;
  email: string;

  name?: string | null;
  full_name?: string | null;

  number?: string | null;
  phone?: string | null;

  age?: number | null;
  sex?: string | null;
  weight_kg?: number | string | null;

  serum_creatinine_mg_dl?: number | string | null;
  creatinine_clearance_ml_min?: number | string | null;
  ckd_stage?: string | null;
  height_cm?: number | string | null;
  is_pregnant?: boolean | null;
  pregnancy_trimester?: string | null;
  is_breastfeeding?: boolean | null;
  liver_disease_status?: string | null;
  albumin_g_dl?: number | string | null;
  systolic_bp_mm_hg?: number | null;
  diastolic_bp_mm_hg?: number | null;
  heart_rate_bpm?: number | null;
  conditions?: string[] | null;
  current_medications?: string[] | null;
};

const CONDITION_OPTIONS = [
  "Diabetes",
  "Hypertension",
  "Heart Failure",
  "CKD",
  "Asthma",
  "COPD",
  "Coronary Artery Disease",
  "Hyperlipidemia",
];

const CURRENT_MED_OPTIONS = [
  "Metformin",
  "Lisinopril",
  "Amlodipine",
  "Atorvastatin",
  "Rosuvastatin",
  "Furosemide",
  "Carvedilol",
  "Insulin",
  "Warfarin",
  "Omega-3",
  "Prenatal Vitamin",
];

const BIOLOGICAL_SEX_OPTIONS = ["Female", "Male", "Intersex", "Unknown"];

function getSelectedValues(e: ChangeEvent<HTMLSelectElement>): string[] {
  return Array.from(e.target.selectedOptions).map((o) => o.value);
}

function canBePregnant(sex: string): boolean {
  const normalized = (sex || "").trim().toLowerCase();
  return normalized === "female" || normalized === "intersex";
}

function normalizeSexForUi(sex: string | null | undefined): string {
  const normalized = (sex || "").trim().toLowerCase();
  if (normalized === "m" || normalized === "male") return "Male";
  if (normalized === "f" || normalized === "female") return "Female";
  if (normalized === "intersex") return "Intersex";
  if (normalized === "unknown") return "Unknown";
  return sex || "";
}

export default function PatientInfo() {
  const nav = useNavigate();

  const [patient, setPatient] = useState<Patient | null>(null);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [scr, setScr] = useState("");
  const [crcl, setCrcl] = useState("");
  const [ckdStage, setCkdStage] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [isPregnant, setIsPregnant] = useState("");
  const [pregnancyTrimester, setPregnancyTrimester] = useState("");
  const [isBreastfeeding, setIsBreastfeeding] = useState("");
  const [liverDiseaseStatus, setLiverDiseaseStatus] = useState("");
  const [albuminGdl, setAlbuminGdl] = useState("");

  const [systolicBp, setSystolicBp] = useState("");
  const [diastolicBp, setDiastolicBp] = useState("");
  const [heartRate, setHeartRate] = useState("");
  const [conditions, setConditions] = useState<string[]>([]);
  const [currentMeds, setCurrentMeds] = useState<string[]>([]);

  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const email = localStorage.getItem("patient_email") || "";
  const pregnancyRelevant = canBePregnant(sex);

  useEffect(() => {
    if (!email) {
      nav("/basic");
      return;
    }

    api
      .getPatientByEmail(email)
      .then((p: Patient) => {
        setPatient(p);

        if (p.id) {
          localStorage.setItem("patient_id", p.id);
        }

        const name = (p.full_name ?? undefined) || (p.name ?? undefined) || "";
        const phoneVal = (p.phone ?? undefined) || (p.number ?? undefined) || "";

        setFullName(name);
        setPhone(phoneVal);

        if (p.age != null) setAge(String(p.age));
        if (p.sex != null) setSex(normalizeSexForUi(p.sex));
        if (p.weight_kg != null) setWeightKg(String(p.weight_kg));
        if (p.serum_creatinine_mg_dl != null) setScr(String(p.serum_creatinine_mg_dl));
        if (p.creatinine_clearance_ml_min != null) setCrcl(String(p.creatinine_clearance_ml_min));
        if (p.ckd_stage != null) setCkdStage(p.ckd_stage);
        if (p.height_cm != null) setHeightCm(String(p.height_cm));
        if (p.is_pregnant != null) setIsPregnant(p.is_pregnant ? "yes" : "no");
        if (p.pregnancy_trimester != null) setPregnancyTrimester(p.pregnancy_trimester);
        if (p.is_breastfeeding != null) setIsBreastfeeding(p.is_breastfeeding ? "yes" : "no");
        if (p.liver_disease_status != null) setLiverDiseaseStatus(p.liver_disease_status);
        if (p.albumin_g_dl != null) setAlbuminGdl(String(p.albumin_g_dl));

        if (p.systolic_bp_mm_hg != null) setSystolicBp(String(p.systolic_bp_mm_hg));
        if (p.diastolic_bp_mm_hg != null) setDiastolicBp(String(p.diastolic_bp_mm_hg));
        if (p.heart_rate_bpm != null) setHeartRate(String(p.heart_rate_bpm));
        if (p.conditions) setConditions(p.conditions);
        if (p.current_medications) setCurrentMeds(p.current_medications);
      })
      .catch(() => {
        setErr("Could not load patient. Please go back and try again.");
      });
  }, [email, nav]);

  useEffect(() => {
    if (!pregnancyRelevant) {
      setIsPregnant("");
      setPregnancyTrimester("");
      setIsBreastfeeding("");
    }
  }, [pregnancyRelevant]);

  async function onSave() {
    setErr("");
    setMsg("");

    if (!email) {
      setErr("No patient email found.");
      return;
    }
    if (!patient || !patient.id) {
      setErr("No patient loaded.");
      return;
    }

    try {
      await api.updatePatientBody(email, {
        name: fullName || undefined,
        number: phone || undefined,
        age: age ? Number(age) : undefined,
        sex: sex || undefined,
        weight_kg: weightKg ? Number(weightKg) : undefined,
        serum_creatinine_mg_dl: scr ? Number(scr) : undefined,
        creatinine_clearance_ml_min: crcl ? Number(crcl) : undefined,
        ckd_stage: ckdStage || undefined,
        height_cm: heightCm ? Number(heightCm) : undefined,
        is_pregnant: isPregnant ? isPregnant === "yes" : undefined,
        pregnancy_trimester: pregnancyTrimester || undefined,
        is_breastfeeding: isBreastfeeding ? isBreastfeeding === "yes" : undefined,
        liver_disease_status: liverDiseaseStatus || undefined,
        albumin_g_dl: albuminGdl ? Number(albuminGdl) : undefined,
        systolic_bp_mm_hg: systolicBp ? Number(systolicBp) : undefined,
        diastolic_bp_mm_hg: diastolicBp ? Number(diastolicBp) : undefined,
        heart_rate_bpm: heartRate ? Number(heartRate) : undefined,
        conditions,
        current_medications: currentMeds,
      });

      setMsg("Saved");

      nav("/simulate", {
        state: {
          patientId: patient.id,
        },
      });
    } catch (e: unknown) {
      const message =
        typeof e === "string"
          ? e
          : (e as { message?: string })?.message || "Failed to save";
      setErr(message);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Patient Information</h2>

        {email && (
          <p style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>
            Email: <strong>{email}</strong>
          </p>
        )}

        <input placeholder="Full Name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <input placeholder="Phone Number" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <input placeholder="Age" value={age} onChange={(e) => setAge(e.target.value)} />
        <select value={sex} onChange={(e) => setSex(e.target.value)}>
          <option value="">Biological sex</option>
          {BIOLOGICAL_SEX_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <input placeholder="Weight (kg)" value={weightKg} onChange={(e) => setWeightKg(e.target.value)} />
        <input placeholder="Height (cm)" value={heightCm} onChange={(e) => setHeightCm(e.target.value)} />

        <input placeholder="Serum creatinine (mg/dL)" value={scr} onChange={(e) => setScr(e.target.value)} />
        <input placeholder="Creatinine clearance (mL/min)" value={crcl} onChange={(e) => setCrcl(e.target.value)} />
        <input placeholder="CKD stage (e.g. G2)" value={ckdStage} onChange={(e) => setCkdStage(e.target.value)} />

        <input placeholder="Systolic BP (mmHg)" value={systolicBp} onChange={(e) => setSystolicBp(e.target.value)} />
        <input placeholder="Diastolic BP (mmHg)" value={diastolicBp} onChange={(e) => setDiastolicBp(e.target.value)} />
        <input placeholder="Heart Rate (bpm)" value={heartRate} onChange={(e) => setHeartRate(e.target.value)} />

        {pregnancyRelevant && (
          <>
            <select value={isPregnant} onChange={(e) => setIsPregnant(e.target.value)}>
              <option value="">Pregnant?</option>
              <option value="no">No</option>
              <option value="yes">Yes</option>
            </select>

            {isPregnant === "yes" && (
              <input
                placeholder="Pregnancy trimester (e.g. 1st / 2nd / 3rd)"
                value={pregnancyTrimester}
                onChange={(e) => setPregnancyTrimester(e.target.value)}
              />
            )}

            <select value={isBreastfeeding} onChange={(e) => setIsBreastfeeding(e.target.value)}>
              <option value="">Breastfeeding?</option>
              <option value="no">No</option>
              <option value="yes">Yes</option>
            </select>
          </>
        )}

        <input
          placeholder="Liver disease status (optional)"
          value={liverDiseaseStatus}
          onChange={(e) => setLiverDiseaseStatus(e.target.value)}
        />
        <input placeholder="Albumin (g/dL)" value={albuminGdl} onChange={(e) => setAlbuminGdl(e.target.value)} />

        <label style={{ display: "block", textAlign: "left", marginTop: "0.8rem" }}>Conditions (multi-select)</label>
        <select multiple value={conditions} onChange={(e) => setConditions(getSelectedValues(e))}>
          {CONDITION_OPTIONS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <label style={{ display: "block", textAlign: "left", marginTop: "0.8rem" }}>Current Medications (multi-select)</label>
        <select multiple value={currentMeds} onChange={(e) => setCurrentMeds(getSelectedValues(e))}>
          {CURRENT_MED_OPTIONS.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>

        <button onClick={onSave}>Save &amp; Simulate</button>

        {msg && <p>{msg}</p>}
        {err && <p style={{ color: "red" }}>{err}</p>}
      </div>
    </div>
  );
}
