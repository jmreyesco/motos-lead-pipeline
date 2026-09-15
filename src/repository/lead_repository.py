import pandas as pd
from sqlalchemy.orm import Session
from src.database.models import Lead, Asesor
from typing import Dict, Any, Optional, List

class LeadRepository:
    """
    Maneja las operaciones de lectura y escritura de leads en PostgreSQL.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def save_lead(self, lead_data: Dict[str, Any]) -> Lead:
        """Crea o actualiza un registro de lead en la base de datos."""
        lead_id = lead_data.get("lead_id")
        existing_lead = self.db.query(Lead).filter(Lead.lead_id == lead_id).first()

        if existing_lead:
            for key, value in lead_data.items():
                if hasattr(existing_lead, key):
                    setattr(existing_lead, key, value)
            lead_obj = existing_lead
        else:
            lead_obj = Lead(**lead_data)
            self.db.add(lead_obj)

        self.db.commit()
        self.db.refresh(lead_obj)
        return lead_obj

    def assign_available_advisor(self, empresa_id: Any, punto_venta_id: Optional[Any]) -> Optional[int]:
        """
        Encuentra un asesor disponible con capacidad dentro de la misma empresa y punto de venta.
        """
        query = self.db.query(Asesor).filter(Asesor.empresa_id == str(empresa_id))
        if punto_venta_id and pd.notna(punto_venta_id):
            query = query.filter(Asesor.punto_venta_id == str(punto_venta_id))
            
        advisor = query.first()
        return advisor.asesor_id if advisor else None

    def get_priority_leads(self, limit: int = 50) -> List[Lead]:
        """Obtiene leads en estado CALIENTE ordenados por puntaje de mayor a menor."""
        return (
            self.db.query(Lead)
            .filter(Lead.temperatura == "CALIENTE")
            .order_by(Lead.score_prioridad.desc())
            .limit(limit)
            .all()
        )

    def get_leads_filtered(
        self,
        temperatura: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 100
    ) -> List[Lead]:
        """Consulta general con filtros opcionales."""
        query = self.db.query(Lead)
        if temperatura:
            query = query.filter(Lead.temperatura == temperatura.upper())
        if estado:
            query = query.filter(Lead.estado_gestion == estado.upper())
        return query.order_by(Lead.score_prioridad.desc()).limit(limit).all()

    def update_lead_status(self, lead_id: str, new_status: str) -> Optional[Lead]:
        """Actualiza el estado de gestión de un lead tras ser contactado."""
        lead = self.db.query(Lead).filter(Lead.lead_id == lead_id).first()
        if lead:
            lead.estado_gestion = new_status.upper()
            self.db.commit()
            self.db.refresh(lead)
        return lead