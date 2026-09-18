"""Normalización de datos de contacto y conversaciones."""

import re
import pandas as pd
from typing import Dict, Any

class DataCleaner:
    """Limpia datos antes de enviarlos a IA o guardarlos en PostgreSQL."""

    @staticmethod
    def clean_phone(phone: Any) -> str:
        """
        Limpia y estandariza el número telefónico.
        - Elimina cualquier carácter que no sea numérico (+, -, espacios, paréntesis).
        - Asegura el formato internacional de Colombia (+57) para números de 10 dígitos.
        """
        if pd.isna(phone):
            return ""
        
        phone_str = str(phone)
        # Extrae solo los dígitos numéricos
        digits = re.sub(r"\D", "", phone_str)
        
        # Si viene con prefijo '57' y tiene más de 10 dígitos, nos quedamos con los últimos 10
        if len(digits) > 10 and digits.startswith("57"):
            digits = digits[-10:]
            
        # Si es un celular colombiano válido de 10 dígitos que inicia por 3, agregamos +57
        if len(digits) == 10 and digits.startswith("3"):
            return f"+57{digits}"
            
        return digits if digits else ""

    @staticmethod
    def clean_email(email: Any) -> str:
        """
        Normaliza la dirección de correo electrónico.
        - Elimina espacios al inicio y al final.
        - Convierte todo el texto a minúsculas para comparaciones uniformes.
        """
        if pd.isna(email):
            return ""
        clean = str(email).strip().lower()
        return clean if clean != "nan" else ""

    @classmethod
    def process_leads_dataframe(cls, df_leads: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica las transformaciones de limpieza y ejecuta el proceso de DEDUPLICACIÓN.
        Retorna un DataFrame limpio y sin registros duplicados.
        """
        df = df_leads.copy()

        # ==========================================================
        # PASO 1: NORMALIZACIÓN DE CAMPOS CLAVE
        # ==========================================================
        if "email" in df.columns:
            df["email"] = df["email"].apply(cls.clean_email)
            
        if "telefono" in df.columns:
            df["telefono"] = df["telefono"].apply(cls.clean_phone)
            
        if "nombre_cliente" in df.columns:
            # Capitaliza los nombres correctamente (ej: "juan perez" -> "Juan Perez")
            df["nombre_cliente"] = df["nombre_cliente"].astype(str).str.strip().str.title()

        # ==========================================================
        # PASO 2: DEDUPLICACIÓN SECUENCIAL (Estrategia por prioridad)
        # ==========================================================
        
        # ----------------------------------------------------------
        # A. Deduplicación por EMAIL
        # ----------------------------------------------------------
        if "email" in df.columns:
            # Separa registros con email válido de los registros con email vacío
            has_email = df[df["email"] != ""]
            no_email = df[df["email"] == ""]
            
            # Elimina duplicados manteniendo el PRIMER registro encontrado (keep='first')
            has_email = has_email.drop_duplicates(subset=["email"], keep="first")
            
            # Recombina los datos deduplicados por email con los que no tenían email
            df = pd.concat([has_email, no_email], ignore_index=True)

        # ----------------------------------------------------------
        # B. Deduplicación por TELÉFONO
        # ----------------------------------------------------------
        if "telefono" in df.columns:
            # Separa registros con teléfono válido de los registros con teléfono vacío
            has_phone = df[df["telefono"] != ""]
            no_phone = df[df["telefono"] == ""]
            
            # Elimina duplicados por número telefónico manteniendo el primer registro
            has_phone = has_phone.drop_duplicates(subset=["telefono"], keep="first")
            
            # Recombina el DataFrame final
            df = pd.concat([has_phone, no_phone], ignore_index=True)

        return df

    @staticmethod
    def format_conversation_text(messages_list: list) -> str:
        """
        Convierte el arreglo JSON de mensajes de WhatsApp en un único texto
        continuo formateado para que el LLM (IA) pueda analizar la conversación.
        """
        if not messages_list or not isinstance(messages_list, list):
            return ""

        transcript = []
        for msg in messages_list:
            if isinstance(msg, dict):
                # Extrae el emisor (Cliente o Asesor) y el texto del mensaje
                role = msg.get("emisor") or msg.get("autor") or msg.get("role") or "Cliente/Asesor"
                text = msg.get("mensaje") or msg.get("texto") or msg.get("content") or ""
                transcript.append(f"{role.capitalize()}: {text.strip()}")
            elif isinstance(msg, str):
                transcript.append(msg.strip())
                
        return "\n".join(transcript)