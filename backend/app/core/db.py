from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import Engine

PG_USER = "capstone_admin"
PG_PASS = "capstone_admin"
PG_PORT = "5432"
DB = "postgresql+psycopg2"
DB_HOST = "digitial-twin-db.crmm8iyoooip.us-east-2.rds.amazonaws.com"
DB_NAME = "app"

DB_URL = f"{DB}://{PG_USER}:{PG_PASS}@{DB_HOST}:{PG_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)

def create_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session