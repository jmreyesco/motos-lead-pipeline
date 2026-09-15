import pandas as pd
from typing import Dict, Any, Tuple, Optional
from src.processing.llm_extractor import ExtractedLeadContext

class LeadScorer:
    """
    Calcula el puntaje de prioridad (0-100) y asigna la temperatura del lead.
    """

    def __init__(self, historical_df: pd.DataFrame = None):
        self.historical_df = historical_df

    def calculate_score(
        self, 
        lead_data: Dict[str, Any], 
        ia_context: Optional[ExtractedLeadContext] = None, 
        catalog_df: pd.DataFrame = None
    ) -> Tuple[float, str]:
        """
        Calcula el score final ponderado.
        Retorna (score_prioridad, temperatura).
        """
        score = 0.0

        # Si no hubo conversación, instanciamos un contexto por defecto
        if ia_context is None:
            ia_context = ExtractedLeadContext()

        # 1. Intención de Compra extraída por la IA (Hasta 35 puntos)
        if ia_context.intencion_compra == "ALTA":
            score += 35.0
        elif ia_context.intencion_compra == "MEDIA":
            score += 20.0
        elif ia_context.intencion_compra == "BAJA":
            score += 5.0

        # 2. Solicitud explícita de cotización o cita (Hasta 25 puntos)
        if ia_context.pidio_cita_cotizacion:
            score += 25.0

        # 3. Disponibilidad de Cuota Inicial (Hasta 20 puntos)
        if ia_context.cuota_inicial_declarada > 0:
            score += 20.0
            # Bonificación si la cuota es alta (>= 2,000,000 COP)
            if ia_context.cuota_inicial_declarada >= 2000000:
                score += 5.0

        # 4. Canal de Entrada y Datos Completos (Hasta 15 puntos)
        canal = str(lead_data.get("canal", "")).upper()
        if "WHATSAPP" in canal or "META" in canal:
            score += 10.0
        elif "WEB" in canal:
            score += 5.0

        if lead_data.get("email") and lead_data.get("telefono"):
            score += 5.0

        # Limitar el score máximo a 100.0
        final_score = min(round(score, 2), 100.0)

        # Asignación de Temperatura
        if final_score >= 70.0:
            temperatura = "CALIENTE"
        elif final_score >= 40.0:
            temperatura = "TIBIO"
        else:
            temperatura = "FRIO"

        return final_score, temperatura