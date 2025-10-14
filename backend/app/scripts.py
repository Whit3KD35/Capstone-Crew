from models import Clinician, Medication, Patient
from core.db import engine, Session
from sqlmodel import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_clinician():
    with Session(engine) as session:
        temp_clinican = session.exec(
            select(Clinician).where(Clinician.email == "admin@ex.com")
        ).first()

        if not temp_clinican:
            temp_clinician = Clinician(
                email = "admin@ex.com",
                name = "Dr. Fake",
                password = "123456"
            )

            session.add(temp_clinician)
            session.commit()

def seed_medications():
    with Session(engine) as session:
        med_1 = session.exec(
            select(Medication).where(Medication.name == "Warfarin")
        ).first()

        med_2 = session.exec(
            select(Medication).where(Medication.name == "Hydrocoritizone")
        ).first()

        med_3 = session.exec(
            select(Medication).where(Medication.name == "Lythium")
        ).first()

        if not med_1:
            med_1 = Medication(
                name = "Warfarin"
            )
            session.add(med_1)
            session.commit()

        if not med_2:
            med_2 = Medication(
                name = "Hydrocoritizone"
            )
            session.add(med_2)
            session.commit()

        if not med_3:
            med_3 = Medication(
                name = "Lythium"
            )
            session.add(med_3)
            session.commit()

def seed_patient():
    with Session(engine) as session:
        temp_patient = session.exec(
            select(Patient).where(Patient.email == "testpatient@ex.com")
        ).first()

        if not temp_patient:
            temp_patient = Patient(
                email = "testpatient@ex.com",
                name = "Test Patient",
                age = 40,
                weight = 75,
                sex = "M"
            )

            session.add(temp_patient)
            session.commit()

def main():
    logger.info("Starting seed...")
    seed_clinician()
    seed_medications()
    seed_patient()
    logger.info("Seed complete")

if __name__ == "__main__":
    main()