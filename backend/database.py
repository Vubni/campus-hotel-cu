import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

# По умолчанию — локальный Postgres; в Docker переопределяется через DATABASE_URL.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://obshaga:obshaga@localhost:5432/obshaga",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_db(retries: int = 30, delay: float = 1.0):
    """Ждём готовности БД — контейнер Postgres может стартовать не сразу."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == retries:
                raise
            time.sleep(delay)
