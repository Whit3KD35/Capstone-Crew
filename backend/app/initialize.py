import logging
import os
from core.db import create_tables, drop_tables
import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

'''
def init() -> None:
    with Session(engine) as session:
        init_db(session)
'''

def main() -> None:
    logger.info("Ensuring tables exist...")
    # Safety guard for production deploys.
    if os.getenv("RESET_DB_ON_STARTUP", "").strip().lower() == "true":
        logger.warning("RESET_DB_ON_STARTUP=true, dropping all tables before recreation.")
        drop_tables()
    create_tables()
    logger.info("Database initialization complete")


if __name__ == "__main__":
    main()
