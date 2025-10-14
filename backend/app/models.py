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
    age: int | None = None
    weight: int | None = None
    sex: str | None = None
    medications: list['Medication'] | None = Relationship(
        back_populates = 'patients',
        link_model = PatientMedicationLink
    )
    simulations: list["Simulation"] = Relationship(back_populates="patient")

class Medication(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str 
    generic_name: str | None = None

    patients: list[Patient] | None = Relationship(
        back_populates = 'medications',
        link_model = PatientMedicationLink
    )


class Simulation(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(foreign_key="patient.id")
    medication_id: uuid.UUID = Field(foreign_key="medication.id")

    dosage_mg: Decimal | None = Field(default=None, max_digits=6, decimal_places=3)
    interval_hours: int | None = None
    sim_results: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    created_at: datetime = Field(default_factory=datetime.now)

    patient: Patient = Relationship(back_populates="simulations")