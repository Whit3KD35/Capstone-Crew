from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

<<<<<<< HEAD
from .api.routes import clinicians, patients, simulations, login, medications, bert
from .core.db import create_tables
=======
from app.core.db import create_tables
from app.api.routes import clinicians, patients, simulations, login, medications, pk

load_dotenv()
>>>>>>> 23cb757e01e74d921449fa562dc75a93a8156edf

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Capstone Backend", lifespan=lifespan)

# CORS
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
app.include_router(simulations.router)  # <-- sims
app.include_router(login.router)
app.include_router(medications.router)
<<<<<<< HEAD
app.include_router(bert.router)
=======
app.include_router(pk.router)
>>>>>>> 23cb757e01e74d921449fa562dc75a93a8156edf
