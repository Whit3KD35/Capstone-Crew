import { useState } from "react";

export default function App() {
  const [page, setPage] = useState<"login" | "patient" | "simulation">("login");

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1>Digital Twin</h1>
      </header>

      {page === "login" && (
        <section>
          <h2>Login</h2>
          <input placeholder="Email" style={{ display: "block", marginBottom: 8 }} />
          <input placeholder="Password" type="password" style={{ display: "block", marginBottom: 8 }} />
          <button onClick={() => setPage("patient")}>Sign in</button>
        </section>
      )}

      {page === "patient" && (
        <section>
          <h2>Patient Area</h2>
          <button onClick={() => setPage("simulation")}>Simulation</button>
        </section>
      )}

      {page === "simulation" && (
        <section>
          <h2>Simulation Page</h2>
          <p>Dosing simulation temp</p>
        </section>
      )}
    </div>
  );
}
