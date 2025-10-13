from .api.routes import clinicians, patients, simulations

from fastapi import FastAPI

app = FastAPI(
    title="Capstone Backend"
)

app.include_router(clinicians.router)
app.include_router(patients.router)
app.include_router(simulations.router)