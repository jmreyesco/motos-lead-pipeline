import re
import pandas as pd
from typing import Dict, Any

class DataCleaner:
    """
    Normaliza y deduplica los datos de leads antes de procesarlos o persistirlos.
    """

    @staticmethod
    def clean_phone(phone: Any) -> str:
        """Elimina caracteres no numéricos y estandariza el formato telefónico."""
        if pd.isna(phone):
            return ""
        phone_str = str(phone)
        digits = re.sub(r"\D", "", phone_str)
        # Ajuste para prefijo de Colombia (+57) si aplica
        if len(digits) == 10 and digits.startswith("3"):
            return f"+57{digits}"
        elif len(digits) == 12 and digits.startswith("57"):
            return f"+{digits}"
        return digits

    @staticmethod
    def clean_email(email: Any) -> str:
        """Limpia espacios y pasa correos a minúsculas."""
        if pd.isna(email):
            return ""
        return str(email).strip().lower()

    @classmethod
    def process_leads_dataframe(cls, df_leads: pd.DataFrame) -> pd.DataFrame:
        """Aplica transformaciones de limpieza y elimina duplicados directos."""
        df = df_leads.copy()

        # Estandarización de cadenas de texto
        if "email" in df.columns:
            df["email"] = df["email"].apply(cls.clean_email)
        if "telefono" in df.columns:
            df["telefono"] = df["telefono"].apply(cls.clean_phone)
        if "nombre" in df.columns:
            df["nombre"] = df["nombre"].astype(str).str.strip().str.title()

        # Deduplicación priorizando registros con más datos completos
        subset_cols = [col for col in ["email", "telefono"] if col in df.columns]
        if subset_cols:
            df = df.drop_duplicates(subset=subset_cols, keep="first")

        return df


    @staticmethod
    def format_conversation_text(messages_list: list) -> str:
        """
        Transforma la lista de mensajes de WhatsApp en un único texto continuo.
        """
        if not messages_list or not isinstance(messages_list, list):
            return ""

        transcript = []
        for msg in messages_list:
            if isinstance(msg, dict):
                role = msg.get("emisor") or msg.get("autor") or msg.get("role") or "Cliente/Asesor"
                text = msg.get("mensaje") or msg.get("texto") or msg.get("content") or ""
                transcript.append(f"{role}: {text}")
            elif isinstance(msg, str):
                transcript.append(msg)
                
        return "\n".join(transcript)