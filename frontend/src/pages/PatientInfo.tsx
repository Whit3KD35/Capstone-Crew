import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

export default function PatientInfo() {
  const nav = useNavigate();

  const [age, setAge] = useState<string>("");
  const [sex, setSex] = useState("");
  const [weight, setWeight] = useState<string>("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const email = localStorage.getItem("patient_email") || "";
  const isExisting = localStorage.getItem("existing") === "true";

  useEffect(() => {
    // Prefill (works for both new or existing currently, email is the part that determines)
    if (email) {
      api
        .getPatientByEmail(email)
        .then((p) => {
          if (p?.age != null) setAge(String(p.age));
          if (p?.sex) setSex(p.sex);
          if (p?.weight != null) setWeight(String(p.weight));
        })
        .catch(() => {});
    }
  }, [email, isExisting]);

  async function onSave() {
    setErr("");
    setMsg("");
    try {
      if (email) {
        await api.updatePatientBody(email, {
          age: age ? Number(age) : undefined,
          sex: sex || undefined,
          weight: weight ? Number(weight) : undefined,
        });
      }
      setMsg("Saved");
      nav("/simulate");
    } catch (e: any) {
      setErr(String(e));
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Patient Information</h2>

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
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
        />

        <button onClick={onSave}>Save</button>
        {msg && <p>{msg}</p>}
        {err && <p style={{ color: "red" }}>{err}</p>}
      </div>
    </div>
  );
}
