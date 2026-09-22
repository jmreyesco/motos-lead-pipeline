"""Modelos ORM que representan las tablas usadas por la aplicación."""

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from src.database.connection import Base


class Asesor(Base):
    """Asesor comercial disponible para recibir leads."""

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


class CatalogoMoto(Base):
    """Moto disponible en el catálogo comercial."""

    __tablename__ = "catalogo_motos"

    sku = Column(String(50), primary_key=True)
    marca = Column(String(100), nullable=True)
    linea = Column(String(150), nullable=True)
    cilindraje = Column(String(50), nullable=True)
    segmento = Column(String(80), nullable=True)
    precio_lista = Column(Float, default=0.0)
    puntos_venta_disponibles = Column(String(255), nullable=True)
    unidades_disponibles = Column(Integer, default=0)


class Lead(Base):
    """Lead enriquecido, puntuado y asignado para gestión comercial."""

    __tablename__ = "leads"

    lead_id = Column(String(50), primary_key=True, index=True)
    empresa_id = Column(String(50), nullable=True)
    punto_venta_id = Column(String(50), nullable=True)
    nombre = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    telefono = Column(String(50), nullable=True)
    canal = Column(String(50), nullable=True)
    modelo_interes = Column(String(100), nullable=True)
    sku = Column(String(50), nullable=True, index=True)
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
