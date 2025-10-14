const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const J = async (r: Response) => (r.ok ? r.json() : Promise.reject(await r.text()));

export const api = {
  // Clinicians
  login: (email: string, password: string) =>
    fetch(`${BASE}/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then(J),

  // Patients
  listPatients: () => fetch(`${BASE}/patients/`).then(J),

  createPatientBasic: (body: { name: string; number: string; email?: string }) =>
    fetch(`${BASE}/patients/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J),

  getPatientByEmail: (email: string) =>
    fetch(`${BASE}/patients/${encodeURIComponent(email)}`).then(J),

  updatePatientBody: (
    email: string,
    body: Partial<{ age: number; sex: string; weight: number; name: string; number: string }>
  ) =>
    fetch(`${BASE}/patients/${encodeURIComponent(email)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J),
};
