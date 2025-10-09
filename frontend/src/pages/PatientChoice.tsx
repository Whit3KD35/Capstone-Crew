import { useNavigate } from "react-router-dom";

export default function PatientChoice() {
  const nav = useNavigate();

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Patient Selection</h2>
        <p>Choose how you would like to continue:</p>

        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <button onClick={() => nav("/basic")}>New Patient</button>
          <button onClick={() => nav("/basic")}>Existing Patient</button>
        </div>
      </div>
    </div>
  );
}
