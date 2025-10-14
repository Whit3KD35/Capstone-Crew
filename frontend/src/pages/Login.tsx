import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { api } from "../api";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPwd] = useState("");
  const [err, setErr] = useState("");

  async function onSignIn() {
    setErr("");
    try {
      await api.login(email, password);
      nav("/choose");
    } catch (e: any) {
      setErr(String(e));
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Digital Twin</h1>
        <h2>Login</h2>

        <input placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} />
        <input type="password" placeholder="Password" value={password} onChange={e=>setPwd(e.target.value)} />

        <button onClick={onSignIn}>Sign In</button>
        {err && <p style={{color:"red"}}>{err}</p>}
        <p style={{ marginTop: "1rem" }}>Enter your login information to access the portal</p>
      </div>
    </div>
  );
}
