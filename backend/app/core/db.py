'''
import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Put it in backend/.env")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

def create_tables():
    SQLModel.metadata.create_all(engine)

def drop_tables():
    SQLModel.metadata.drop_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
'''

import os
from sqlmodel import SQLModel, Session, create_engine

# Optional: loads backend/.env if you're using one
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to backend/.env or your environment variables.")

# pool_pre_ping helps avoid stale connections; good for cloud DBs
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def create_tables():
    SQLModel.metadata.create_all(engine)

def drop_tables():
    SQLModel.metadata.drop_all(engine)

def get_session():
    with Session(engine) as session:
        yield session