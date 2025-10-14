import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { api } from "../api";

export default function BasicInfo() {
  const nav = useNavigate();
  const [full_name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [err, setErr] = useState("");
  const isExisting = localStorage.getItem("existing") === "true";

  // Prefill
  async function tryPrefill() {
    if (!isExisting || !email) return;
    try {
      const p = await api.getPatientByEmail(email);
      if (p?.name) setName(p.name);
      if (p?.number) setPhone(p.number);
      if (!p?.name && p?.full_name) setName(p.full_name);
      if (!p?.number && p?.phone) setPhone(p.phone);
    } catch {
    }
  }

  async function onNext() {
    setErr("");
    localStorage.setItem("patient_email", email || "");

    try {
      if (isExisting) {
        // Update basic fields if provided
        if (email && (full_name || phone)) {
          try {
            await api.updatePatientBody(email, {
              name: full_name || undefined,
              number: phone || undefined,
            });
          } catch {
          }
        }
      } else {
        // Create new patient with backend
        await api.createPatientBasic({
          name: full_name,
          number: phone,
          email: email || undefined,
        });
      }
      nav("/info");
    } catch (e: any) {
      setErr(String(e));
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Basic Patient Information</h2>

        <input
          placeholder="Full Name"
          value={full_name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          placeholder="Phone Number"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <input
          placeholder="Email (optional)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={tryPrefill}
        />

        <button onClick={onNext}>Next</button>
        {err && <p style={{ color: "red" }}>{err}</p>}
      </div>
    </div>
  );
}
