import { useNavigate } from "react-router-dom";

export default function BasicInfo() {
  const nav = useNavigate();

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Basic Patient Information</h2>

        <input placeholder="Full Name" />
        <input placeholder="Phone Number" />
        <input placeholder="Email (optional)" />

        <button onClick={() => nav("/info")}>Next</button>
      </div>
    </div>
  );
}
