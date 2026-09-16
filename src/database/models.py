# from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
# from sqlalchemy.orm import relationship
# from datetime import datetime
# from src.database.connection import Base

# class Asesor(Base):
#     __tablename__ = "asesores"

#     asesor_id = Column(Integer, primary_key=True, autoincrement=True)
#     nombre = Column(String(100), nullable=False)
#     empresa_id = Column(String(50), nullable=False)
#     punto_venta_id = Column(String(50), nullable=True)
#     capacidad_maxima = Column(Integer, default=10)
#     leads_actuales = Column(Integer, default=0)

#     # Columnas adicionales
#     activo = Column(String(10), default="SI")
#     fecha_ingreso = Column(DateTime, nullable=True)

#     # Relación inversa: Un asesor tiene múltiples leads asignados
#     leads = relationship("Lead", back_populates="asesor")


# class Lead(Base):
#     __tablename__ = "leads"

#     # Creacion de indices
#     lead_id = Column(String(50), primary_key=True, index=True)
#     # ... otros campos ...
    
#     # Creamos un índice directo en la columna temperatura
#     temperatura = Column(String(20), index=True) 
#     score_prioridad = Column(Float, index=True)

#     lead_id = Column(String(50), primary_key=True, index=True)
#     empresa_id = Column(String(50), nullable=True)
#     punto_venta_id = Column(String(50), nullable=True)
#     nombre = Column(String(100), nullable=True)
#     email = Column(String(100), nullable=True)
#     telefono = Column(String(50), nullable=True)
#     canal = Column(String(50), nullable=True)
#     modelo_interes = Column(String(100), nullable=True)
#     cuota_inicial_declarada = Column(Float, default=0.0)
#     forma_pago = Column(String(50), nullable=True)
#     intencion_compra = Column(String(50), nullable=True)
#     objecion_principal = Column(String(255), nullable=True)
#     pidio_cita_cotizacion = Column(Boolean, default=False)
#     score_prioridad = Column(Float, default=0.0)
#     temperatura = Column(String(20), nullable=True)
#     # asesor_id = Column(Integer, ForeignKey("asesores.asesor_id"), nullable=True)

#     # Clave Foránea apuntando a la tabla 'asesores'
#     asesor_id = Column(Integer, ForeignKey("asesores.asesor_id"), nullable=True)
    
#     # Objeto de relación para navegar desde Python (ej: lead.asesor.nombre)
#     asesor = relationship("Asesor", back_populates="leads")

#     estado_gestion = Column(String(50), default="NUEVO")
#     fecha_creacion = Column(DateTime, default=datetime.utcnow)




from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from src.database.connection import Base


class Asesor(Base):
    __tablename__ = "asesores"

    # Cambiado de Integer a String(50) para soportar IDs como 'AS-001'
    asesor_id = Column(String(50), primary_key=True)
    nombre = Column(String(100), nullable=False)
    empresa_id = Column(String(50), nullable=False)
    punto_venta_id = Column(String(50), nullable=True)
    capacidad_maxima = Column(Integer, default=10)
    leads_actuales = Column(Integer, default=0)

    # Columnas adicionales
    activo = Column(String(10), default="SI")
    fecha_ingreso = Column(DateTime, nullable=True)

    # Relación inversa: Un asesor tiene múltiples leads asignados
    leads = relationship("Lead", back_populates="asesor")


class Lead(Base):
    __tablename__ = "leads"

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

    # Índices y campos limpios (sin duplicados)
    score_prioridad = Column(Float, default=0.0, index=True)
    temperatura = Column(String(20), nullable=True, index=True)

    # Clave Foránea apuntando a 'asesores.asesor_id' como String(50)
    asesor_id = Column(String(50), ForeignKey("asesores.asesor_id"), nullable=True)

    # Navegación SQLAlchemy
    asesor = relationship("Asesor", back_populates="leads")

    estado_gestion = Column(String(50), default="NUEVO")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)