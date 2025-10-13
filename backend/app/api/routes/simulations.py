from fastapi import APIRouter, Depends
from ...models import Simulation
from sqlmodel import Session
from ...core.db import get_session

router = APIRouter(
    prefix="/sims",
    tags=["sims"]
)

@router.post("/")
def add_simulation(sim: Simulation, session: Session = Depends(get_session)):
    return {"message": "add sim"}