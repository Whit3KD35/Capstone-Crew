import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import create_tables
from app.api.routes import clinicians, patients, simulations, login, medications, pk, patient_login, it

load_dotenv()

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    configured = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return configured or DEFAULT_CORS_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Capstone Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
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
app.include_router(pk.router)
app.include_router(patient_login.router)
app.include_router(it.router)
