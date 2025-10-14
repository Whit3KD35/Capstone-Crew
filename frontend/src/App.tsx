import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import Login from "./pages/Login";
import PatientChoice from "./pages/PatientChoice";
import BasicInfo from "./pages/BasicInfo";
import PatientInfo from "./pages/PatientInfo";
import Simulation from "./pages/Simulation";

function Shell() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1>Digital Twin</h1>
      </header>
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/choose" element={<PatientChoice />} />
          <Route path="/basic" element={<BasicInfo />} />
          <Route path="/info" element={<PatientInfo />} />
          <Route path="/simulate" element={<Simulation />} />

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
