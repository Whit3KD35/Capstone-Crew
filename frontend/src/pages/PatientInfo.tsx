import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
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
};

export default function PatientInfo() {
  const nav = useNavigate();

  const [patient, setPatient] = useState<Patient | null>(null);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [scr, setScr] = useState("");      // serum creatinine (mg/dL)
  const [crcl, setCrcl] = useState("");    // creatinine clearance (mL/min)
  const [ckdStage, setCkdStage] = useState("");

  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const email = localStorage.getItem("patient_email") || "";

  useEffect(() => {
    if (!email) {
      nav("/basic");
      return;
    }

    api
      .getPatientByEmail(email)
      .then((p: Patient) => {
        setPatient(p);

        // Store UUID for possible future use
        if (p.id) {
          localStorage.setItem("patient_id", p.id);
        }

        const name =
          (p.full_name ?? undefined) ||
          (p.name ?? undefined) ||
          "";
        const phoneVal =
          (p.phone ?? undefined) ||
          (p.number ?? undefined) ||
          "";

        setFullName(name);
        setPhone(phoneVal);

        if (p.age != null) setAge(String(p.age));
        if (p.sex != null) setSex(p.sex);

        if (p.weight_kg != null) setWeightKg(String(p.weight_kg));
        if (p.serum_creatinine_mg_dl != null)
          setScr(String(p.serum_creatinine_mg_dl));
        if (p.creatinine_clearance_ml_min != null)
          setCrcl(String(p.creatinine_clearance_ml_min));
        if (p.ckd_stage != null) setCkdStage(p.ckd_stage);
      })
      .catch(() => {
        setErr("Could not load patient. Please go back and try again.");
      });
  }, [email, nav]);

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
        // demographics
        name: fullName || undefined,
        number: phone || undefined,
        age: age ? Number(age) : undefined,
        sex: sex || undefined,

        // clinical / PK-relevant
        weight_kg: weightKg ? Number(weightKg) : undefined,
        serum_creatinine_mg_dl: scr ? Number(scr) : undefined,
        creatinine_clearance_ml_min: crcl ? Number(crcl) : undefined,
        ckd_stage: ckdStage || undefined,
      });

      setMsg("Saved");

      nav("/simulate", {
        state: {
          patientId: patient.id,
          // medicationId is optional
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

        <input
          placeholder="Full Name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <input
          placeholder="Phone Number"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />

        <input
          placeholder="Age"
          value={age}
          onChange={(e) => setAge(e.target.value)}
        />
        <input
          placeholder="Sex"
          value={sex}
          onChange={(e) => setSex(e.target.value)}
        />
        <input
          placeholder="Weight (kg)"
          value={weightKg}
          onChange={(e) => setWeightKg(e.target.value)}
        />

        <input
          placeholder="Serum creatinine (mg/dL)"
          value={scr}
          onChange={(e) => setScr(e.target.value)}
        />
        <input
          placeholder="Creatinine clearance (mL/min)"
          value={crcl}
          onChange={(e) => setCrcl(e.target.value)}
        />
        <input
          placeholder="CKD stage (e.g. 'Stage 2')"
          value={ckdStage}
          onChange={(e) => setCkdStage(e.target.value)}
        />

        <button onClick={onSave}>Save &amp; Simulate</button>

        {msg && <p>{msg}</p>}
        {err && <p style={{ color: "red" }}>{err}</p>}
      </div>
    </div>
  );
}
