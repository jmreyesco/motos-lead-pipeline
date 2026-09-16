# import pandas as pd
# from sqlalchemy.orm import Session
# from src.database.models import Lead, Asesor
# from typing import Dict, Any, Optional, List


# class LeadRepository:
#     """
#     Maneja las operaciones de lectura y escritura de leads en PostgreSQL.
#     """

#     def __init__(self, db_session: Session):
#         self.db = db_session

#     def save_lead(self, lead_data: Dict[str, Any]) -> Lead:
#         """Crea o actualiza un registro de lead en la base de datos."""
#         lead_id = lead_data.get("lead_id")
#         existing_lead = self.db.query(Lead).filter(Lead.lead_id == lead_id).first()

#         if existing_lead:
#             for key, value in lead_data.items():
#                 if hasattr(existing_lead, key):
#                     setattr(existing_lead, key, value)
#             lead_obj = existing_lead
#         else:
#             lead_obj = Lead(**lead_data)
#             self.db.add(lead_obj)

#         self.db.commit()
#         self.db.refresh(lead_obj)
#         return lead_obj

#     def assign_available_advisor(self, empresa_id: Any, punto_venta_id: Optional[Any]) -> Optional[int]:
#         """
#         Encuentra un asesor disponible con capacidad dentro de la misma empresa y punto de venta.
#         """
#         query = self.db.query(Asesor).filter(Asesor.empresa_id == str(empresa_id))
#         if punto_venta_id and pd.notna(punto_venta_id):
#             query = query.filter(Asesor.punto_venta_id == str(punto_venta_id))
            
#         advisor = query.first()
#         return advisor.asesor_id if advisor else None

#     def get_priority_leads(self, limit: int = 50) -> List[Lead]:
#         """Obtiene leads en estado CALIENTE ordenados por puntaje de mayor a menor."""
#         return (
#             self.db.query(Lead)
#             .filter(Lead.temperatura == "CALIENTE")
#             .order_by(Lead.score_prioridad.desc())
#             .limit(limit)
#             .all()
#         )

#     def get_leads_filtered(
#         self,
#         temperatura: Optional[str] = None,
#         estado: Optional[str] = None,
#         limit: int = 100
#     ) -> List[Lead]:
#         """Consulta general con filtros opcionales."""
#         query = self.db.query(Lead)
#         if temperatura:
#             query = query.filter(Lead.temperatura == temperatura.upper())
#         if estado:
#             query = query.filter(Lead.estado_gestion == estado.upper())
#         return query.order_by(Lead.score_prioridad.desc()).limit(limit).all()

#     def update_lead_status(self, lead_id: str, new_status: str) -> Optional[Lead]:
#         """Actualiza el estado de gestión de un lead tras ser contactado."""
#         lead = self.db.query(Lead).filter(Lead.lead_id == lead_id).first()
#         if lead:
#             lead.estado_gestion = new_status.upper()
#             self.db.commit()
#             self.db.refresh(lead)
#         return lead

#     def get_leads_by_company(self, empresa_id: str):
#         """
#         Consulta en la base de datos aplicando un filtro estricto por empresa_id.
#         Garantiza la separación multitenant solicitada.
#         """
#         return (
#             self.db.query(Lead)
#             .filter(Lead.empresa_id == empresa_id)
#             .order_by(Lead.score_prioridad.desc())
#             .all()
#         )


#     def save_advisors(self, df_advisors: pd.DataFrame):
#             """Inserta asesores mapeando las columnas del CSV al modelo de la BD."""
#             try:
#                 for _, row in df_advisors.iterrows():
#                     asesor_id_raw = row.get("asesor_id")
#                     if pd.isna(asesor_id_raw):
#                         continue
                    
#                     # Manejo de IDs si provienen de float (ej: 10.0 -> "10")
#                     if isinstance(asesor_id_raw, float) and asesor_id_raw.is_integer():
#                         asesor_id = str(int(asesor_id_raw))
#                     else:
#                         asesor_id = str(asesor_id_raw)

#                     # Evitar duplicados si ya existe
#                     existing = self.db.query(Asesor).filter(Asesor.asesor_id == asesor_id).first()
#                     if existing:
#                         continue

#                     # Validar capacidad de manera segura
#                     capacidad_raw = row.get("capacidad_diaria_leads")
#                     capacidad = int(capacidad_raw) if pd.notna(capacidad_raw) else 0

#                     # Formatear punto_venta_id
#                     pv_raw = row.get("punto_venta_id")
#                     pv_id = None
#                     if pd.notna(pv_raw):
#                         pv_id = str(int(pv_raw)) if isinstance(pv_raw, float) and pv_raw.is_integer() else str(pv_raw)

#                     # Validar fecha_ingreso
#                     fecha_raw = row.get("fecha_ingreso")
#                     if isinstance(fecha_raw, pd.Timestamp):
#                         fecha_ingreso = fecha_raw.to_pydatetime()
#                     elif pd.notna(fecha_raw):
#                         fecha_ingreso = fecha_raw
#                     else:
#                         fecha_ingreso = None

#                     nuevo_asesor = Asesor(
#                         asesor_id=asesor_id,
#                         nombre=str(row.get("nombre")) if pd.notna(row.get("nombre")) else "",
#                         punto_venta_id=pv_id,
#                         empresa_id=str(row.get("empresa_id")) if pd.notna(row.get("empresa_id")) else "EMP-01",
#                         capacidad_maxima=capacidad,
#                         activo=str(row.get("activo", "SI")).upper() == "SI" if pd.notna(row.get("activo")) else True,
#                         fecha_ingreso=fecha_ingreso
#                     )
#                     self.db.add(nuevo_asesor)

#                 self.db.commit()
#             except Exception:
#                 self.db.rollback()
#                 raise





import math
import pandas as pd
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from src.database.models import Lead, Asesor


class LeadRepository:
    """
    Maneja las operaciones de lectura y escritura de leads y asesores en PostgreSQL.
    """

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

    # def get_leads_filtered(
    #     self,
    #     temperatura: Optional[str] = None,
    #     estado: Optional[str] = None,
    #     limit: int = 100,
    # ) -> List[Lead]:
        """Consulta general con filtros opcionales."""
        query = self.db.query(Lead)
        if temperatura:
            query = query.filter(Lead.temperatura == temperatura.upper())
        if estado:
            query = query.filter(Lead.estado_gestion == estado.upper())
        return query.order_by(Lead.score_prioridad.desc()).limit(limit).all()


    def get_leads_filtered(
        self, 
        temperatura: Optional[str] = None, 
        estado: Optional[str] = None,
        empresa_id: Optional[str] = None,
        asesor_id: Optional[str] = None,
        limit: int = 100
        ):
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
        """
        Consulta en la base de datos aplicando un filtro estricto por empresa_id.
        Garantiza la separación multitenant solicitada.
        """
        return (
            self.db.query(Lead)
            .filter(Lead.empresa_id == empresa_id)
            .order_by(Lead.score_prioridad.desc())
            .all()
        )

    def save_advisors(self, df_advisors: pd.DataFrame):
        """Inserta asesores mapeando las columnas del CSV/DataFrame al modelo de la BD."""
        try:
            for _, row in df_advisors.iterrows():
                asesor_id_raw = row.get("asesor_id")
                if pd.isna(asesor_id_raw):
                    continue

                # Manejo de IDs si provienen de float (ej: 10.0 -> "10")
                if isinstance(asesor_id_raw, float) and asesor_id_raw.is_integer():
                    asesor_id = str(int(asesor_id_raw))
                else:
                    asesor_id = str(asesor_id_raw)

                # Evitar duplicados si ya existe
                existing = (
                    self.db.query(Asesor)
                    .filter(Asesor.asesor_id == asesor_id)
                    .first()
                )
                if existing:
                    continue

                # Validar capacidad de manera segura
                capacidad_raw = row.get("capacidad_diaria_leads")
                capacidad = int(capacidad_raw) if pd.notna(capacidad_raw) else 0

                # Formatear punto_venta_id
                pv_raw = row.get("punto_venta_id")
                pv_id = None
                if pd.notna(pv_raw):
                    pv_id = (
                        str(int(pv_raw))
                        if isinstance(pv_raw, float) and pv_raw.is_integer()
                        else str(pv_raw)
                    )

                # Validar fecha_ingreso
                fecha_raw = row.get("fecha_ingreso")
                if isinstance(fecha_raw, pd.Timestamp):
                    fecha_ingreso = fecha_raw.to_pydatetime()
                elif pd.notna(fecha_raw):
                    fecha_ingreso = fecha_raw
                else:
                    fecha_ingreso = None

                nuevo_asesor = Asesor(
                    asesor_id=asesor_id,
                    nombre=(
                        str(row.get("nombre"))
                        if pd.notna(row.get("nombre"))
                        else ""
                    ),
                    punto_venta_id=pv_id,
                    empresa_id=(
                        str(row.get("empresa_id"))
                        if pd.notna(row.get("empresa_id"))
                        else "EMP-01"
                    ),
                    capacidad_maxima=capacidad,
                    activo=(
                        str(row.get("activo", "SI")).upper() == "SI"
                        if pd.notna(row.get("activo"))
                        else True
                    ),
                    fecha_ingreso=fecha_ingreso,
                )
                self.db.add(nuevo_asesor)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise