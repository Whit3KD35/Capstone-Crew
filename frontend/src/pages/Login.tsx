import { useNavigate } from "react-router-dom";

export default function Login() {
  const nav = useNavigate();

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Login</h2>

        <input placeholder="Email" />
        <input type="password" placeholder="Password" />

        <button onClick={() => nav("/choose")}>Sign In</button>
        <p style={{ marginTop: "1rem" }}>
          Enter your login information to access the portal
        </p>
      </div>
    </div>
  );
}
