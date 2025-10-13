import { useState } from "react";

export default function Simulation() {
  const [dose, setDose] = useState("");
  const [interval, setInterval] = useState("");
  const [result, setResult] = useState<string | null>(null);

  // Temp Calculation, just for show currently
  const runSimulation = () => {
    const d = dose || "1000";
    const i = interval || "12";
    setResult(`Recommended dose: ${d} mg every ${i} hours`);
  };

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Dosing Simulation</h2>

        <input
          placeholder="Dose (mg)"
          value={dose}
          onChange={(e) => setDose(e.target.value)}
        />
        <input
          placeholder="Interval (hours)"
          value={interval}
          onChange={(e) => setInterval(e.target.value)}
        />

        <button onClick={runSimulation}>Run Simulation</button>

        {result && (
          <div
            style={{
              marginTop: "1rem",
              fontWeight: "bold",
              color: "#333",
              background: "#eef0ff",
              padding: "0.75rem",
              borderRadius: "8px",
            }}
          >
            {result}
          </div>
        )}
      </div>
    </div>
  );
}
