import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "FILE")
    
    # Rutas relativas para los insumos sintéticos
    DATA_DIR: Path = BASE_DIR / "data"
    LEADS_FILE: Path = DATA_DIR / "leads.csv"
    CONVERSATIONS_FILE: Path = DATA_DIR / "conversaciones.json"
    CATALOG_FILE: Path = DATA_DIR / "catalogo_motos.csv"
    ADVISORS_FILE: Path = DATA_DIR / "asesores.csv"
    HISTORICAL_FILE: Path = DATA_DIR / "historico_cierres.csv"

settings = Settings()