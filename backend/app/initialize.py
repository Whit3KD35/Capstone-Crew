import logging
from sqlmodel import Session
from core.db import engine, create_tables, drop_tables
import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

'''
def init() -> None:
    with Session(engine) as session:
        init_db(session)
'''

def main() -> None:
    logger.info("Creating tables...")
    #init()
    drop_tables()
    create_tables()
    logger.info("Tables created")


if __name__ == "__main__":
    main()