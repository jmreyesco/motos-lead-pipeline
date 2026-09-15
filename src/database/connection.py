from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config import settings

# 1. Crear motor de base de datos
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# 2. Crear clase base declarativa (AQUÍ SE CREA, NO SE IMPORTA DE MODELS)
Base = declarative_base()

# 3. Creador de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Crea las tablas en PostgreSQL si aún no existen."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Generador de sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()