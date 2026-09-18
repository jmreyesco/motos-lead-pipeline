"""API REST para consultar leads, métricas y estados de gestión."""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd

from src.config import settings
from src.database.connection import Base, engine, get_db
from src.repository.lead_repository import LeadRepository
from src.schemas.lead import LeadResponse, LeadStatusUpdate
import src.database.models
from src.database.models import Lead


def sync_reference_tables() -> None:
    """
    Crea las tablas ORM y carga asesores/catálogo si están vacíos.

    Este paso permite levantar sólo FastAPI sin ejecutar previamente main.py.
    Las tablas se cargan una sola vez para no duplicar claves primarias.
    """
    try:
        Base.metadata.create_all(bind=engine)

        inspector = inspect(engine)
        if not inspector.has_table("asesores"):
            return

        if settings.DATA_SOURCE != "FILE":
            return

        with engine.connect() as conn:
            advisors_count = conn.execute(text("SELECT COUNT(*) FROM asesores")).scalar() or 0
            if settings.ADVISORS_FILE.exists() and advisors_count == 0:
                advisors_df = pd.read_csv(settings.ADVISORS_FILE)
                if "asesor_id" in advisors_df.columns:
                    advisors_df = advisors_df.drop_duplicates(subset=["asesor_id"], keep="first")
                    advisors_df.to_sql("asesores", con=engine, if_exists="append", index=False)

            catalog_count = conn.execute(text("SELECT COUNT(*) FROM catalogo_motos")).scalar() or 0
            if settings.CATALOG_FILE.exists() and catalog_count == 0:
                catalog_df = pd.read_csv(settings.CATALOG_FILE)
                if "sku" in catalog_df.columns:
                    catalog_df = catalog_df.drop_duplicates(subset=["sku"], keep="first")
                    catalog_df.to_sql("catalogo_motos", con=engine, if_exists="append", index=False)
    except Exception as exc:
        print(f"⚠️ No se pudo sincronizar la data de referencia: {exc}")


app = FastAPI(
    title="Motos Lead Pipeline API",
    description="API REST para consulta y gestión de leads priorizados con scoring de IA.",
    version="1.0.0",
)


@app.on_event("startup")
def startup_event():
    """Se ejecuta al levantar la API y prepara tablas base desde CSV."""
    sync_reference_tables()


# CORS permite que el frontend React, ejecutándose en otro puerto, consuma la API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, reemplaza "*" por tu dominio de React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """Confirma que el servidor está activo."""
    return {"message": "Servidor de Lead Pipeline activo y listo para recibir peticiones."}


@app.get("/api/v1/leads/prioritarios", response_model=List[LeadResponse])
def get_priority_leads(
    limit: int = Query(default=50, ge=1, le=500),
    empresa_id: Optional[str] = Query(None, description="ID de la empresa/concesionario"),
    asesor_id: Optional[str] = Query(None, description="ID del asesor asignado"),
    db: Session = Depends(get_db)
):
    """Obtiene leads calientes, opcionalmente filtrados por empresa y asesor."""
    repo = LeadRepository(db)
    return repo.get_priority_leads(
        limit=limit,
        empresa_id=empresa_id,
        asesor_id=asesor_id,
    )


@app.get("/api/v1/leads", response_model=List[LeadResponse])
def get_leads_list(
    temperatura: Optional[str] = Query(None, description="Filtro: CALIENTE, TIBIO, FRIO"),
    estado: Optional[str] = Query(None, description="Filtro: NUEVO, ASIGNADO, etc."),
    empresa_id: Optional[str] = Query(None, description="ID de la empresa/concesionario"),
    asesor_id: Optional[str] = Query(None, description="ID del asesor asignado"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Obtiene leads ordenados por score con filtros opcionales."""
    repo = LeadRepository(db)
    return repo.get_leads_filtered(
        temperatura=temperatura,
        estado=estado,
        empresa_id=empresa_id,
        asesor_id=asesor_id,
        limit=limit
    )

@app.patch("/api/v1/leads/{lead_id}/estado", response_model=LeadResponse)
def update_lead_status(
    lead_id: str,
    status_update: LeadStatusUpdate,
    db: Session = Depends(get_db)
):
    """Permite al asesor o al sistema actualizar el estado de gestión de un lead."""
    repo = LeadRepository(db)
    updated_lead = repo.update_lead_status(lead_id, status_update.estado_gestion)
    if not updated_lead:
        raise HTTPException(status_code=404, detail=f"Lead con ID {lead_id} no fue encontrado.")
    return updated_lead

@app.get("/api/v1/metrics/summary")
def get_metrics_summary(
    empresa_id: Optional[str] = Query(None, description="ID de la empresa/concesionario"),
    asesor_id: Optional[str] = Query(None, description="ID del asesor asignado"),
    db: Session = Depends(get_db),
):
    """Devuelve los conteos que usa el dashboard para sus gráficos."""
    query = db.query(Lead)
    if empresa_id:
        query = query.filter(Lead.empresa_id == empresa_id.strip())
    if asesor_id:
        query = query.filter(Lead.asesor_id == asesor_id.strip())

    # Conteos por Temperatura
    calientes = query.filter(Lead.temperatura == "CALIENTE").count()
    tibios = query.filter(Lead.temperatura == "TIBIO").count()
    frios = query.filter(Lead.temperatura == "FRIO").count()
    
    # Conteos por Estado
    asignados = query.filter(Lead.estado_gestion == "ASIGNADO").count()
    contactados = query.filter(Lead.estado_gestion == "CONTACTADO").count()
    negociacion = query.filter(Lead.estado_gestion == "EN_NEGOCIACION").count()
    vendidos = query.filter(Lead.estado_gestion == "VENDIDO").count()
    descartados = query.filter(Lead.estado_gestion == "DESCARTADO").count()

    canal_expression = func.coalesce(
        func.nullif(func.trim(Lead.canal), ""),
        "SIN CANAL",
    )
    canales = dict(
        query.with_entities(canal_expression, func.count(Lead.lead_id))
        .group_by(canal_expression)
        .all()
    )

    total = calientes + tibios + frios

    return {
        "total_leads": total,
        "temperaturas": {
            "CALIENTE": calientes,
            "TIBIO": tibios,
            "FRIO": frios,
        },
        "estados": {
            "ASIGNADO": asignados,
            "CONTACTADO": contactados,
            "EN_NEGOCIACION": negociacion,
            "VENDIDO": vendidos,
            "DESCARTADO": descartados
        },
        "canales": canales,
    }


@app.get("/api/v1/e-leads")
def get_leads(
    empresa_id: str = Query(..., description="ID obligatorio de la empresa a consultar"),
    db: Session = Depends(get_db)
):
    """
    Endpoint multitenant: Retorna únicamente los leads pertenecientes a la empresa solicitada.
    """
    try:
        repo = LeadRepository(db)
        leads = repo.get_leads_by_company(empresa_id)
        
        leads_data = [
            {
                "lead_id": l.lead_id,
                # Busca 'nombre_cliente' y si no existe usa 'nombre'
                "nombre_cliente": getattr(l, "nombre_cliente", getattr(l, "nombre", "")),
                "telefono": getattr(l, "telefono", ""),
                "email": getattr(l, "email", ""),
                "empresa_id": l.empresa_id,
                "punto_venta_id": getattr(l, "punto_venta_id", None),
                "modelo_interes": getattr(l, "modelo_interes", None),
                "temperatura": getattr(l, "temperatura", None),
                "score_prioridad": getattr(l, "score_prioridad", None),
                "estado_gestion": getattr(l, "estado_gestion", None),
            }
            for l in leads
        ] if leads else []

        return {
            "status": "success",
            "empresa_id": empresa_id,
            "total_registros": len(leads_data),
            "data": leads_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener los leads para la empresa {empresa_id}: {str(e)}"
        )
