from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api.routes import clinicians, patients, simulations, login, medications
from .core.db import create_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield

app = FastAPI(title="Capstone Backend", lifespan=lifespan)

# CORS:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(clinicians.router)
app.include_router(patients.router)
app.include_router(simulations.router)
app.include_router(login.router)
app.include_router(medications.router)
