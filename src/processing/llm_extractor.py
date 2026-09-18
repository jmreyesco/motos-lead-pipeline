"""Extracción estructurada de señales comerciales mediante OpenAI."""

from typing import Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from src.config import settings

# 1. Definición del Esquema Pydantic (Garantiza el JSON estricto)
class ExtractedLeadContext(BaseModel):
    """Campos normalizados que la IA debe extraer de una conversación."""
    modelo_interes: Optional[str] = Field(
        default=None, 
        description="Modelo de motocicleta específico por el que pregunta el cliente."
    )
    cuota_inicial_declarada: float = Field(
        default=0.0, 
        description="Monto en dinero de cuota inicial que el cliente dice tener disponible."
    )
    forma_pago: str = Field(
        default="NO_ESPECIFICA", 
        description="Forma de pago mencionada. Opciones: 'CREDITO', 'CONTADO', 'NO_ESPECIFICA'."
    )
    intencion_compra: str = Field(
        default="MEDIA", 
        description="Intención de compra deducida del diálogo. Opciones: 'ALTA', 'MEDIA', 'BAJA'."
    )
    objecion_principal: Optional[str] = Field(
        default=None, 
        description="Principal impedimento o duda expresada (ej: 'Intereses altos', 'Sin fiador', 'Precio')."
    )
    pidio_cita_cotizacion: bool = Field(
        default=False, 
        description="True si el cliente solicitó explícitamente una cotización formal, prueba de manejo o cita."
    )

# 2. Extractor con OpenAI API
class ConversationLLMExtractor:
    """
    Analiza las conversaciones de WhatsApp usando GPT-4o-mini con Structured Outputs.
    """

    def __init__(self):
        """Crea el cliente sólo cuando existe una clave de OpenAI."""
        self.api_key = settings.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def extract_info(self, conversation_text: str) -> ExtractedLeadContext:
        """Analiza una conversación y devuelve un resultado validado por Pydantic."""
        if not self.client:
            # Fallback seguro por si se ejecuta sin API key durante pruebas iniciales
            return ExtractedLeadContext()

        prompt_system = (
            "Eres un analista de datos experto en ventas de motocicletas. "
            "Tu tarea es analizar la siguiente transcripción de chat entre un cliente y un asesor "
            "y extraer de forma precisa y objetiva los campos solicitados."
        )

        try:
            # Uso de Structured Outputs nativo de OpenAI
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": f"Transcripción del chat:\n{conversation_text}"}
                ],
                response_format=ExtractedLeadContext,
                temperature=0.0 # Determinístico
            )
            return completion.choices[0].message.parsed
        except Exception as e:
            print(f"Error al procesar extracción con LLM: {e}")
            return ExtractedLeadContext()