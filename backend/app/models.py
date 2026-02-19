import uuid

from typing import Any
from datetime import datetime
from decimal import Decimal

from sqlmodel import SQLModel, Field, Column, Relationship
from pydantic import EmailStr, BaseModel
from sqlalchemy.dialects.postgresql import JSONB


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
    password: str = Field(min_length=8, max_length=40)


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
    password: str = Field(min_length=8, max_length=128)
    age: int | None = None
    sex: str | None = None

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
