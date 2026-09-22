"""Consultas y persistencia de leads mediante SQLAlchemy."""

import math
import pandas as pd
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.database.models import Lead, Asesor


class LeadRepository:
    """Aísla el acceso a las tablas ``leads`` y ``asesores``."""

    def __init__(self, db_session: Session):
        self.db = db_session

    @staticmethod
    def _clean_pandas_value(val: Any) -> Any:
        """Convierte valores nulos o problemáticos de Pandas a None (SQL NULL)."""
        if pd.isna(val):
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val

    def save_lead(self, lead_data: Dict[str, Any]) -> Lead:
        """Crea o actualiza un registro de lead en la base de datos limpiando valores NaN de Pandas."""
        # Limpiar dict para reemplazar np.nan / pd.NaT por None
        clean_data = {k: self._clean_pandas_value(v) for k, v in lead_data.items()}

        lead_id = clean_data.get("lead_id")
        existing_lead = (
            self.db.query(Lead).filter(Lead.lead_id == lead_id).first()
            if lead_id
            else None
        )

        if existing_lead:
            for key, value in clean_data.items():
                if hasattr(existing_lead, key):
                    setattr(existing_lead, key, value)
            lead_obj = existing_lead
        else:
            lead_obj = Lead(**clean_data)
            self.db.add(lead_obj)

        try:
            self.db.commit()
            self.db.refresh(lead_obj)
            return lead_obj
        except Exception:
            self.db.rollback()
            raise

    def assign_skus_from_model(self) -> int:
        """
        Asigna el SKU del catálogo según el texto del modelo de interés.

        La actualización se ejecuta sobre todos los leads para que también
        sincronice una tabla ya poblada y deje en NULL los modelos sin regla.
        El orden de las condiciones es intencional: PostgreSQL usa la primera
        condición coincidente del CASE.
        """
        result = self.db.execute(text("""
            UPDATE leads
            SET sku = CASE
                WHEN modelo_interes ILIKE '%twister%' OR modelo_interes ILIKE '%cb 125%' THEN 'SKU-001'
                WHEN modelo_interes ILIKE '%xr 150%' OR modelo_interes ILIKE '%xr150%' THEN 'SKU-002'
                WHEN modelo_interes ILIKE '%cb 190%' OR modelo_interes ILIKE '%cb190%' THEN 'SKU-003'
                WHEN modelo_interes ILIKE '%navi%' THEN 'SKU-004'
                WHEN modelo_interes ILIKE '%dio%' THEN 'SKU-005'
                WHEN modelo_interes ILIKE '%xre 300%' OR modelo_interes ILIKE '%xre%' THEN 'SKU-006'
                WHEN modelo_interes ILIKE '%boxer%' THEN 'SKU-007'
                WHEN modelo_interes ILIKE '%ns 125%' OR modelo_interes ILIKE '%ns125%' THEN 'SKU-008'
                WHEN modelo_interes ILIKE '%ns 160%' OR modelo_interes ILIKE '%ns160%' THEN 'SKU-009'
                WHEN modelo_interes ILIKE '%rs 200%' OR modelo_interes ILIKE '%rs200%' THEN 'SKU-010'
                WHEN modelo_interes ILIKE '%dominar%' THEN 'SKU-011'
                WHEN modelo_interes ILIKE '%discover%' THEN 'SKU-012'
                WHEN modelo_interes ILIKE '%gn 125%' OR modelo_interes ILIKE '%gn%' THEN 'SKU-013'
                WHEN modelo_interes ILIKE '%gixxer%' THEN 'SKU-014'
                WHEN modelo_interes ILIKE '%v-strom%' OR modelo_interes ILIKE '%vstrom%' THEN 'SKU-015'
                WHEN modelo_interes ILIKE '%best%' THEN 'SKU-016'
                WHEN modelo_interes ILIKE '%nkd%' THEN 'SKU-017'
                WHEN modelo_interes ILIKE '%dynamic%' THEN 'SKU-018'
                WHEN modelo_interes ILIKE '%ttr%' THEN 'SKU-019'
                WHEN modelo_interes ILIKE '%evo%' THEN 'SKU-020'
                WHEN modelo_interes ILIKE '%eco%' OR modelo_interes ILIKE '%deluxe%' THEN 'SKU-021'
                WHEN modelo_interes ILIKE '%hunk%' THEN 'SKU-022'
                WHEN modelo_interes ILIKE '%xpulse%' THEN 'SKU-023'
                WHEN modelo_interes ILIKE '%dash%' THEN 'SKU-024'
                ELSE NULL
            END
        """))
        self.db.commit()
        return result.rowcount

    def assign_available_advisor(
        self, empresa_id: Any, punto_venta_id: Optional[Any]
    ) -> Optional[str]:
        """
        Encuentra un asesor disponible dentro de la misma empresa y punto de venta.
        """
        if pd.isna(empresa_id):
            return None

        query = self.db.query(Asesor).filter(Asesor.empresa_id == str(empresa_id))

        if punto_venta_id and pd.notna(punto_venta_id):
            # Normalizar float a int si viene como 1.0 -> "1"
            if isinstance(punto_venta_id, float) and punto_venta_id.is_integer():
                pv_str = str(int(punto_venta_id))
            else:
                pv_str = str(punto_venta_id)
            query = query.filter(Asesor.punto_venta_id == pv_str)

        advisor = query.first()
        return str(advisor.asesor_id) if advisor else None

    def get_priority_leads(
        self,
        limit: int = 50,
        empresa_id: Optional[str] = None,
        asesor_id: Optional[str] = None,
    ) -> List[Lead]:
        """Obtiene leads calientes aplicando filtros opcionales."""
        query = self.db.query(Lead).filter(Lead.temperatura == "CALIENTE")

        if empresa_id:
            query = query.filter(Lead.empresa_id == empresa_id.strip())
        if asesor_id:
            query = query.filter(Lead.asesor_id == asesor_id.strip())

        return query.order_by(Lead.score_prioridad.desc()).limit(limit).all()

    def get_leads_filtered(
        self, 
        temperatura: Optional[str] = None, 
        estado: Optional[str] = None,
        empresa_id: Optional[str] = None,
        asesor_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Lead]:
        """Devuelve leads ordenados por score y filtrados por los parámetros dados."""
        query = self.db.query(Lead)

        if temperatura and temperatura.upper() != "GRAFICOS":
            query = query.filter(Lead.temperatura == temperatura.strip().upper())
        if estado:
            query = query.filter(Lead.estado_gestion == estado.strip().upper())
        if empresa_id:
            query = query.filter(Lead.empresa_id == empresa_id.strip())
        if asesor_id:
            query = query.filter(Lead.asesor_id == asesor_id.strip())

        return query.order_by(Lead.score_prioridad.desc()).limit(limit).all()

    def update_lead_status(self, lead_id: str, new_status: str) -> Optional[Lead]:
        """Actualiza el estado de gestión de un lead tras ser contactado."""
        lead = self.db.query(Lead).filter(Lead.lead_id == lead_id).first()
        if lead:
            lead.estado_gestion = new_status.upper()
            try:
                self.db.commit()
                self.db.refresh(lead)
            except Exception:
                self.db.rollback()
                raise
        return lead

    def get_leads_by_company(self, empresa_id: str) -> List[Lead]:
        """Devuelve todos los leads de una empresa, ordenados por prioridad."""
        return (
            self.db.query(Lead)
            .filter(Lead.empresa_id == empresa_id)
            .order_by(Lead.score_prioridad.desc())
            .all()
        )
