"""Conexión compartida a PostgreSQL y ciclo de vida de sesiones."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config import settings

# El engine administra el pool de conexiones hacia PostgreSQL.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Todos los modelos ORM heredan de esta Base.
Base = declarative_base()

# Las sesiones se crean por petición o por ejecución del pipeline.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Crea las tablas en PostgreSQL si aún no existen."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Entrega una sesión a FastAPI y la cierra siempre al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()