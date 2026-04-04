import uuid

from typing import Any, Optional
from datetime import datetime
from decimal import Decimal

from sqlmodel import SQLModel, Field, Column, Relationship
from pydantic import EmailStr, BaseModel
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Integer, String, DateTime


class Test(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    password: str = Field(min_length=8, max_length=40)


class Clinician(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    last_login: Optional[datetime] = Field(default=None)
    last_simulation_at: Optional[datetime] = Field(default=None)


class PatientMedicationLink(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    medication_id: uuid.UUID = Field(foreign_key="medication.id")
    is_active: bool = True


class Patient(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    number: str | None = None
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    age: int | None = None
    sex: str | None = None
    last_login: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    last_simulation_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))

    full_name: str | None = None
    phone: str | None = None
    weight_kg: Decimal | None = None
    serum_creatinine_mg_dl: Decimal | None = None
    creatinine_clearance_ml_min: Decimal | None = None
    ckd_stage: str | None = None

    medications: list["Medication"] | None = Relationship(
        back_populates="patients",
        link_model=PatientMedicationLink
    )
    simulations: list["Simulation"] = Relationship(back_populates="patient")
    clinical_factors: Optional["PatientClinicalFactors"] = Relationship(back_populates="patient")
    vital_signs: Optional["PatientVitalSigns"] = Relationship(back_populates="patient")
    condition_links: list["PatientConditionLink"] = Relationship(back_populates="patient")
    current_medications: list["PatientCurrentMedication"] = Relationship(back_populates="patient")


class PatientClinicalFactors(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id", unique=True, index=True)

    height_cm: Decimal | None = None
    is_pregnant: bool | None = None
    pregnancy_trimester: str | None = None
    is_breastfeeding: bool | None = None
    liver_disease_status: str | None = None
    albumin_g_dl: Decimal | None = None

    patient: Patient = Relationship(back_populates="clinical_factors")


class PatientVitalSigns(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id", unique=True, index=True)
    systolic_bp_mm_hg: int | None = None
    diastolic_bp_mm_hg: int | None = None
    heart_rate_bpm: int | None = None

    patient: Patient = Relationship(back_populates="vital_signs")


class Condition(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True, unique=True)

    patient_links: list["PatientConditionLink"] = Relationship(back_populates="condition")


class PatientConditionLink(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id", index=True)
    condition_id: uuid.UUID = Field(foreign_key="condition.id", index=True)

    patient: Patient = Relationship(back_populates="condition_links")
    condition: Condition = Relationship(back_populates="patient_links")


class PatientCurrentMedication(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id", index=True)
    name: str

    patient: Patient = Relationship(back_populates="current_medications")


class Medication(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    generic_name: str | None = None

    half_life_hr: Decimal | None = None
    bioavailability_f: Decimal | None = None

    clearance_raw_value: Decimal | None = None
    clearance_raw_unit: str | None = None
    volume_of_distribution_raw_value: Decimal | None = None
    volume_of_distribution_raw_unit: str | None = None

    therapeutic_window_lower_mg_l: Decimal | None = None
    therapeutic_window_upper_mg_l: Decimal | None = None
    source_url: str | None = None

    patients: list[Patient] | None = Relationship(
        back_populates="medications",
        link_model=PatientMedicationLink
    )


class MedicationTherapeuticWindowReview(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    medication_id: uuid.UUID = Field(foreign_key="medication.id", unique=True, index=True)
    status: str = Field(default="manual_required", index=True)
    lower_mg_l: Decimal | None = None
    upper_mg_l: Decimal | None = None
    source: str | None = None
    confidence_pct: Decimal | None = None
    reviewer_notes: str | None = None
    updated_at: datetime = Field(default_factory=datetime.now)


class Simulation(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    medication_id: uuid.UUID = Field(foreign_key="medication.id")

    dosage_mg: Decimal | None = Field(default=None, max_digits=6, decimal_places=3)
    interval_hours: int | None = None
    sim_results: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    dose_mg: Decimal | None = None
    interval_hr: Decimal | None = None
    duration_hr: Decimal | None = None
    cmax_mg_l: Decimal | None = None
    cmin_mg_l: Decimal | None = None
    auc_mg_h_l: Decimal | None = None
    flag_too_high: bool | None = None
    flag_too_low: bool | None = None

    created_at: datetime = Field(default_factory=datetime.now)

    patient: Patient = Relationship(back_populates="simulations")

class AcceptedSimulation(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)

    patient_id: uuid.UUID = Field(foreign_key="patient.id", index=True)
    medication_id: uuid.UUID = Field(foreign_key="medication.id", index=True)

    simulation_id: uuid.UUID = Field(foreign_key="simulation.id", unique=True)

    accepted_at: datetime = Field(default_factory=datetime.now)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
class ITUser(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role: str = Field(default="it")
    
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashedPassword: str
    last_login: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    last_simulation_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))

class UserResponse(BaseModel):
    id: int
    email: str
    last_login: Optional[datetime] = None
    last_simulation_at: Optional[datetime] = None
