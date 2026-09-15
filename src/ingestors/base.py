from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd

class BaseLeadIngestor(ABC):
    """
    Interfaz abstracta para la ingesta de datos.
    Permite intercambiar fuentes de información (archivos planos, DB, Webhooks/APIs).
    """

    @abstractmethod
    def get_leads(self) -> pd.DataFrame:
        """Retorna el DataFrame con los leads recibidos."""
        pass

    @abstractmethod
    def get_conversations(self) -> Dict[str, Any]:
        """Retorna el diccionario/JSON con las transcripciones de WhatsApp."""
        pass

    @abstractmethod
    def get_catalog(self) -> pd.DataFrame:
        """Retorna el catálogo de motocicletas."""
        pass

    @abstractmethod
    def get_advisors(self) -> pd.DataFrame:
        """Retorna los asesores comerciales y su capacidad."""
        pass

    @abstractmethod
    def get_historical_closures(self) -> pd.DataFrame:
        """Retorna el histórico de cierres para calibrar el scoring."""
        pass