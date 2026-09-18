"""Lectura de los CSV y JSON que alimentan el pipeline."""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from src.config import settings
from src.ingestors.base import BaseLeadIngestor

class FileIngestor(BaseLeadIngestor):
    """
    Adaptador de ingesta basado en los archivos locales entregados (.csv y .json).
    """

    def __init__(self):
        """Resuelve una sola vez las rutas configuradas para todos los insumos."""
        self.leads_path = settings.LEADS_FILE
        self.conversations_path = settings.CONVERSATIONS_FILE
        self.catalog_path = settings.CATALOG_FILE
        self.advisors_path = settings.ADVISORS_FILE
        self.historical_path = settings.HISTORICAL_FILE

    def get_leads(self) -> pd.DataFrame:
        """Lee los leads originales que serán limpiados y procesados."""
        if not self.leads_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.leads_path}")
        return pd.read_csv(self.leads_path)

    def get_conversations(self) -> Dict[str, Any]:
        """Lee y normaliza conversaciones para buscarlas por ``lead_id``."""
        if not self.conversations_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.conversations_path}")
        
        with open(self.conversations_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Si el JSON es una lista, la convertimos a un diccionario indexado por lead_id
        if isinstance(data, list):
            conversations_map = {}
            for item in data:
                # Soporta si la clave se llama 'lead_id' o 'id'
                lead_id = str(item.get("lead_id") or item.get("id") or "")
                messages = item.get("mensajes") or item.get("conversacion") or item.get("messages") or []
                if lead_id:
                    conversations_map[lead_id] = messages
            return conversations_map

        return data

    def get_catalog(self) -> pd.DataFrame:
        """Lee el catálogo usado como referencia del pipeline."""
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.catalog_path}")
        return pd.read_csv(self.catalog_path)

    def get_advisors(self) -> pd.DataFrame:
        """Lee los asesores que se sincronizan con PostgreSQL."""
        if not self.advisors_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.advisors_path}")
        return pd.read_csv(self.advisors_path)

    def get_historical_closures(self) -> pd.DataFrame:
        """Lee el histórico disponible para futuras calibraciones del score."""
        if not self.historical_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {self.historical_path}")
        return pd.read_csv(self.historical_path)
