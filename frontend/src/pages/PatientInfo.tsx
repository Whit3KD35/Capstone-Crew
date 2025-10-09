import { useNavigate } from "react-router-dom";
import { useState } from "react";

export default function PatientInfo() {
  const nav = useNavigate();
  const [existing, setExisting] = useState(false); // setExisting is a temp for when we create the autofill function

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Patient Information</h2>

        {!existing ? (
          <>
            <input placeholder="Age" />
            <input placeholder="Sex" />
            <input placeholder="Weight (kg)" />
            <input placeholder="Current Medications" />
          </>
        ) : (
          <p>Existing patient info will be loaded automatically.</p>
        )}

        <button onClick={() => nav("/simulate")}>Next</button>
      </div>
    </div>
  );
}
