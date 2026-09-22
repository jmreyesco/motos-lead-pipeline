"""Esquemas de entrada y salida usados por los endpoints de leads."""

from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class LeadBase(BaseModel):
    """Campos públicos comunes de un lead."""
    lead_id: str
    empresa_id: Optional[str] = None
    punto_venta_id: Optional[str] = None
    nombre: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    canal: Optional[str] = None
    modelo_interes: Optional[str] = None
    sku: Optional[str] = None
    cuota_inicial_declarada: float = 0.0
    forma_pago: Optional[str] = None
    intencion_compra: Optional[str] = None
    objecion_principal: Optional[str] = None
    pidio_cita_cotizacion: bool = False
    score_prioridad: float = 0.0
    temperatura: Optional[str] = None
    asesor_id: Optional[str] = None
    estado_gestion: Optional[str] = "NUEVO"

class LeadResponse(LeadBase):
    """Respuesta ORM serializable que entrega la API."""
    fecha_creacion: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class LeadStatusUpdate(BaseModel):
    """Cuerpo de la petición para cambiar el estado de gestión."""
    estado_gestion: str  # Ej: "CONTACTADO", "EN_NEGOCIACION", "VENDIDO", "DESCARTADO"