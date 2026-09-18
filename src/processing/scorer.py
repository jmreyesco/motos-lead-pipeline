"""Reglas determinísticas para puntuar y clasificar leads."""

import pandas as pd
from typing import Dict, Any, Tuple, Optional
from src.processing.llm_extractor import ExtractedLeadContext

class LeadScorer:
    """
    Calcula el puntaje de prioridad (0-100) y asigna la temperatura del lead
    ajustado a la evidencia estadística del histórico de cierres.
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
        Suma señales comerciales y devuelve ``(score, temperatura)``.

        ``historical_df`` y ``catalog_df`` se conservan en la firma porque
        forman parte del contrato actual del pipeline; las reglas vigentes
        todavía no los usan directamente.
        """
        score = 0.0

        if ia_context is None:
            ia_context = ExtractedLeadContext()

        # 1. INTENCIÓN DE COMPRA (IA) - Max 30 Puntos
        if ia_context.intencion_compra == "ALTA":
            score += 30.0
        elif ia_context.intencion_compra == "MEDIA":
            score += 18.0
        elif ia_context.intencion_compra == "BAJA":
            score += 5.0

        # 2. SOLICITUD DE CITA / PRUEBA / COTIZACIÓN - Max 25 Puntos
        # Evidencia: Eleva la conversión al 11.8%
        if ia_context.pidio_cita_cotizacion or str(lead_data.get("pidio_cita", "")).upper() == "SI":
            score += 25.0

        # 3. MANIFIESTO DE CUOTA INICIAL Y FORMA DE PAGO - Max 25 Puntos
        # Evidencia: Contado o cuota informada elevan la probabilidad de cierre
        cuota = ia_context.cuota_inicial_declarada
        manifesto_cuota = str(lead_data.get("manifesto_cuota_inicial", "")).upper()
        
        if cuota > 0 or manifesto_cuota == "SI":
            score += 15.0
            if cuota >= 2000000:
                score += 5.0 # Bonificación por solvencia
                
        forma_pago = str(ia_context.forma_pago or lead_data.get("forma_pago_declarada", "")).upper()
        if "CONTADO" in forma_pago:
            score += 5.0

        # 4. VELOCIDAD Y CALIDAD DEL CONTACTO (OPERACIONAL) - Max 15 Puntos
        # Evidencia: Respuesta < 1 hora eleva la conversión al 15.1%
        horas_contacto = lead_data.get("horas_al_primer_contacto")
        if horas_contacto is not None:
            if horas_contacto <= 1.0:
                score += 15.0  # Máxima prioridad por atención inmediata
            elif horas_contacto <= 4.0:
                score += 10.0
            elif horas_contacto <= 12.0:
                score += 5.0

        # 5. INTEGRIDAD DE CONTACTO - Max 5 Puntos
        if lead_data.get("email") and lead_data.get("telefono"):
            score += 5.0

        # Limitar score final
        final_score = min(round(score, 2), 100.0)

        # Asignación de Temperatura basada en percentiles de éxito
        if final_score >= 70.0:
            temperatura = "CALIENTE"
        elif final_score >= 40.0:
            temperatura = "TIBIO"
        else:
            temperatura = "FRIO"

        return final_score, temperatura
