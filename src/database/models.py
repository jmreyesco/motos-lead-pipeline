from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from datetime import datetime
from src.database.connection import Base

class Asesor(Base):
    __tablename__ = "asesores"

    asesor_id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    empresa_id = Column(String(50), nullable=False)
    punto_venta_id = Column(String(50), nullable=True)
    capacidad_maxima = Column(Integer, default=10)
    leads_actuales = Column(Integer, default=0)

class Lead(Base):
    __tablename__ = "leads"

    # Creacion de indices
    lead_id = Column(String(50), primary_key=True, index=True)
    # ... otros campos ...
    
    # Creamos un índice directo en la columna temperatura
    temperatura = Column(String(20), index=True) 
    score_prioridad = Column(Float, index=True)

    lead_id = Column(String(50), primary_key=True, index=True)
    empresa_id = Column(String(50), nullable=True)
    punto_venta_id = Column(String(50), nullable=True)
    nombre = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    telefono = Column(String(50), nullable=True)
    canal = Column(String(50), nullable=True)
    modelo_interes = Column(String(100), nullable=True)
    cuota_inicial_declarada = Column(Float, default=0.0)
    forma_pago = Column(String(50), nullable=True)
    intencion_compra = Column(String(50), nullable=True)
    objecion_principal = Column(String(255), nullable=True)
    pidio_cita_cotizacion = Column(Boolean, default=False)
    score_prioridad = Column(Float, default=0.0)
    temperatura = Column(String(20), nullable=True)
    asesor_id = Column(Integer, ForeignKey("asesores.asesor_id"), nullable=True)
    estado_gestion = Column(String(50), default="NUEVO")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)