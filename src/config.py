"""Configuración central del pipeline y rutas de archivos de entrada."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar las variables privadas antes de construir el objeto de configuración.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    """Valores de entorno y ubicaciones de los archivos del proyecto."""

    # Credenciales y selección de la fuente de datos.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "FILE")
    
    # Todos los archivos de entrada viven en la carpeta data/ del repositorio.
    DATA_DIR: Path = BASE_DIR / "data"
    LEADS_FILE: Path = DATA_DIR / "leads.csv"
    CONVERSATIONS_FILE: Path = DATA_DIR / "conversaciones.json"
    CATALOG_FILE: Path = DATA_DIR / "catalogo_motos.csv"
    ADVISORS_FILE: Path = DATA_DIR / "asesores.csv"
    HISTORICAL_FILE: Path = DATA_DIR / "historico_cierres.csv"

settings = Settings()