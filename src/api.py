from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from src.database.connection import get_db
from src.repository.lead_repository import LeadRepository
from src.schemas.lead import LeadResponse, LeadStatusUpdate
from src.database.models import Lead 

app = FastAPI(
    title="Motos Lead Pipeline API",
    description="API REST para consulta y gestión de leads priorizados con scoring de IA.",
    version="1.0.0",
)

# Configurar middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, reemplaza "*" por tu dominio de React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Servidor de Lead Pipeline activo y listo para recibir peticiones."}


@app.get("/api/v1/leads/prioritarios", response_model=List[LeadResponse])
def get_priority_leads(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Obtiene los leads clasificados como 'CALIENTE' ordenados del score más alto al más bajo.
    Ideal para llamar inmediatamente por el call center o asesores.
    """
    repo = LeadRepository(db)
    return repo.get_priority_leads(limit=limit)


@app.get("/api/v1/leads", response_model=List[LeadResponse])
def get_leads(
    temperatura: Optional[str] = Query(None, description="Filtro: CALIENTE, TIBIO, FRIO"),
    estado: Optional[str] = Query(None, description="Filtro: NUEVO, ASIGNADO, CONTACTADO, VENDIDO, etc."),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Obtiene una lista de leads permitiendo filtrar por temperatura y estado de gestión."""
    repo = LeadRepository(db)
    return repo.get_leads_filtered(temperatura=temperatura, estado=estado, limit=limit)


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
def get_metrics_summary(db: Session = Depends(get_db)):
    """
    Retorna la distribución total de leads por temperatura y estado de gestión
    para alimentar los gráficos del Dashboard.
    """
    repo = LeadRepository(db)
    
    # Conteos por Temperatura
    calientes = db.query(Lead).filter(Lead.temperatura == "CALIENTE").count()
    tibios = db.query(Lead).filter(Lead.temperatura == "TIBIO").count()
    frios = db.query(Lead).filter(Lead.temperatura == "FRIO").count()
    
    # Conteos por Estado
    asignados = db.query(Lead).filter(Lead.estado_gestion == "ASIGNADO").count()
    contactados = db.query(Lead).filter(Lead.estado_gestion == "CONTACTADO").count()
    negociacion = db.query(Lead).filter(Lead.estado_gestion == "EN_NEGOCIACION").count()
    vendidos = db.query(Lead).filter(Lead.estado_gestion == "VENDIDO").count()
    descartados = db.query(Lead).filter(Lead.estado_gestion == "DESCARTADO").count()

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
        }
    }