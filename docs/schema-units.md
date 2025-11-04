# Schema + Units

## Patients
- age: years
- sex: Male/Female/Other/Unknown
- weight: kg
- serum_creatinine: mg/dL
- creatinine_clearance (optional): mL/min
- ckd_stage (optional): G1–G5

## Medications
- name: text
- half_life: hours
- clearance: L/hr
- volume_of_distribution (Vd): L
- bioavailability (F): fraction 0–1
- therapeutic_window_lower: mg/L
- therapeutic_window_upper: mg/L

## Simulation (inputs)
- patient_id (or patient_email)
- medication_id
- dose: mg
- interval: hours
- duration: hours

## Simulation (outputs)
- cmax: mg/L
- cmin: mg/L
- auc (optional): mg·hr/L
- flag_too_high: true/false
- flag_too_low: true/false

## Rules
- Units are metric (SI).
- Store full precision; round only when displaying.
- F is a fraction (e.g., 0.85), not a percent.
- Drug-centric model; renal function (CrCl/CKD) affects dosing window checks.
