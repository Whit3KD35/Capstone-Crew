const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Helper to parse JSON or throw the response text
const J = async (r: Response) =>
  r.ok ? r.json() : Promise.reject(await r.text());

// Types
export type PatientUpdateBody = Partial<{
  age: number;
  sex: string;
  weight_kg: number;
  name: string;
  number: string;
  serum_creatinine_mg_dl: number;
  creatinine_clearance_ml_min: number;
  ckd_stage: string;
}>;

export type SimulationRunPayload = {
  patient_id: string;
  medication_id: string;
  dose_mg: number;
  interval_hr: number;
  num_doses: number;
  dt_hr: number;
  absorption_rate_hr?: number | null;
};

export type Medication = {
  id: string;
  name: string;
  half_life_hr?: number | null;
  clearance_l_hr?: number | null;
  vd_l?: number | null;
  therapeutic_window_lower_mg_l?: number | null;
  therapeutic_window_upper_mg_l?: number | null;
};

// API object

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

  // identifier = email
  getPatientByEmail: (email: string) =>
    fetch(`${BASE}/patients/${encodeURIComponent(email)}`).then(J),

  // identifier = email
  updatePatientBody: (identifier: string, body: PatientUpdateBody) =>
    fetch(`${BASE}/patients/${encodeURIComponent(identifier)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J),

  // Medications
  listMedications: () =>
    fetch(`${BASE}/medications/`).then(J) as Promise<Medication[]>,

  createMedication: (body: {
    name: string;
    half_life_hr?: number;
    clearance_raw_value?: number;
    clearance_raw_unit?: string;
    volume_of_distribution_raw_value?: number;
    volume_of_distribution_raw_unit?: string;
    therapeutic_window_lower_mg_l?: number;
    therapeutic_window_upper_mg_l?: number;
  }) =>
    fetch(`${BASE}/medications/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J) as Promise<Medication>,

  // Simulations
  runSimulation: (body: SimulationRunPayload) =>
    fetch(`${BASE}/sims/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J),
};
