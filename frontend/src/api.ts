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
  height_cm: number;
  is_pregnant: boolean;
  pregnancy_trimester: string;
  is_breastfeeding: boolean;
  liver_disease_status: string;
  albumin_g_dl: number;
  systolic_bp_mm_hg: number;
  diastolic_bp_mm_hg: number;
  heart_rate_bpm: number;
  conditions: string[];
  current_medications: string[];
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
  generic_name?: string | null;
  half_life_hr?: number | null;
  bioavailability_f?: number | null;
  clearance_raw_value?: number | null;
  clearance_raw_unit?: string | null;
  volume_of_distribution_raw_value?: number | null;
  volume_of_distribution_raw_unit?: string | null;
  therapeutic_window_lower_mg_l?: number | null;
  therapeutic_window_upper_mg_l?: number | null;
  source_url?: string | null;
};

export type PkFetchResponse = {
  half_life_hr?: number | null;
  clearance_L_per_hr?: number | null;
  Vd_L?: number | null;
  bioavailability?: number | null;
  clearance_raw_value?: number | null;
  clearance_raw_unit?: string | null;
  Vd_raw_value?: number | null;
  Vd_raw_unit?: string | null;
  therapeutic_window_lower_mg_l?: number | null;
  therapeutic_window_upper_mg_l?: number | null;
  sources?: Record<string, { has_raw_text: boolean; raw_char_count: number }>;
  consensus?: Record<string, unknown>;
  window_review?: {
    status: "proposed" | "approved" | "rejected" | "manual_required";
    lower_mg_l?: number | null;
    upper_mg_l?: number | null;
    source?: string | null;
    confidence_pct?: number | null;
    reviewer_notes?: string | null;
  };
};

export type WindowReview = {
  medication_id: string;
  status: "proposed" | "approved" | "rejected" | "manual_required";
  lower_mg_l?: number | null;
  upper_mg_l?: number | null;
  source?: string | null;
  confidence_pct?: number | null;
  reviewer_notes?: string | null;
  updated_at?: string | null;
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
  listSimulationMedications: () =>
    fetch(`${BASE}/medications/simulation-ready`).then(J) as Promise<Medication[]>,

  createMedication: (body: {
    name: string;
    generic_name?: string;
    half_life_hr?: number;
    bioavailability_f?: number;
    clearance_raw_value?: number;
    clearance_raw_unit?: string;
    volume_of_distribution_raw_value?: number;
    volume_of_distribution_raw_unit?: string;
    therapeutic_window_lower_mg_l?: number;
    therapeutic_window_upper_mg_l?: number;
    source_url?: string;
  }) =>
    fetch(`${BASE}/medications/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J) as Promise<Medication>,
  updateMedication: (
    name: string,
    body: {
      generic_name?: string;
      half_life_hr?: number;
      bioavailability_f?: number;
      clearance_raw_value?: number;
      clearance_raw_unit?: string;
      volume_of_distribution_raw_value?: number;
      volume_of_distribution_raw_unit?: string;
      therapeutic_window_lower_mg_l?: number;
      therapeutic_window_upper_mg_l?: number;
      source_url?: string;
    }
  ) =>
    fetch(`${BASE}/medications/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J) as Promise<Medication>,
  deleteMedication: (name: string) =>
    fetch(`${BASE}/medications/${encodeURIComponent(name)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    }).then(J) as Promise<{
      deleted: boolean;
      name: string;
      removed_reviews: number;
      removed_links: number;
      removed_simulations: number;
    }>,

  getMedicationWindowReview: (medicationId: string) =>
    fetch(`${BASE}/medications/${encodeURIComponent(medicationId)}/window-review`).then(J) as Promise<WindowReview>,
  approveMedicationWindowReview: (medicationId: string) =>
    fetch(`${BASE}/medications/${encodeURIComponent(medicationId)}/window-review/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }).then(J) as Promise<WindowReview>,
  rejectMedicationWindowReview: (
    medicationId: string,
    body: {
      notes?: string;
      manual_lower_mg_l?: number;
      manual_upper_mg_l?: number;
    }
  ) =>
    fetch(`${BASE}/medications/${encodeURIComponent(medicationId)}/window-review/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J) as Promise<WindowReview>,
  listWindowReviewQueue: () =>
    fetch(`${BASE}/medications/window-review/queue`).then(J) as Promise<WindowReview[]>,

  fetchMedicationPk: (name: string, upsert = true) =>
    fetch(
      `${BASE}/pk/fetch?name=${encodeURIComponent(name)}&upsert=${upsert}&include_raw=false`
    ).then(J) as Promise<PkFetchResponse>,

  // Simulations
  runSimulation: (body: SimulationRunPayload) =>
    fetch(`${BASE}/sims/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(J),
};
