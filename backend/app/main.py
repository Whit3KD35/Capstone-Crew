from .api.routes import clinicians, patients, simulations, login, medications

from fastapi import FastAPI

app = FastAPI(
    title="Capstone Backend"
)

app.include_router(clinicians.router)
app.include_router(patients.router)
app.include_router(simulations.router)
app.include_router(login.router)
app.include_router(medications.router)