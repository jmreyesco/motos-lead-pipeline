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
    empresa_id: Optional[str] = Query(None, description="ID de la empresa/concesionario"),
    asesor_id: Optional[str] = Query(None, description="ID del asesor asignado"),
    db: Session = Depends(get_db)
):
    """
    Obtiene los leads clasificados como 'CALIENTE' ordenados del score más alto al más bajo.
    Ideal para llamar inmediatamente por el call center o asesores.
    """
    repo = LeadRepository(db)
    return repo.get_priority_leads(
        limit=limit,
        empresa_id=empresa_id,
        asesor_id=asesor_id,
    )


# @app.get("/api/v1/leads", response_model=List[LeadResponse])
# def get_leads(
#     temperatura: Optional[str] = Query(None, description="Filtro: CALIENTE, TIBIO, FRIO"),
#     estado: Optional[str] = Query(None, description="Filtro: NUEVO, ASIGNADO, CONTACTADO, VENDIDO, etc."),
#     limit: int = Query(default=100, ge=1, le=1000),
#     db: Session = Depends(get_db)
# ):
#     """Obtiene una lista de leads permitiendo filtrar por temperatura y estado de gestión."""
#     repo = LeadRepository(db)
#     return repo.get_leads_filtered(temperatura=temperatura, estado=estado, limit=limit)

@app.get("/api/v1/leads", response_model=List[LeadResponse])
def get_leads_list(
    temperatura: Optional[str] = Query(None, description="Filtro: CALIENTE, TIBIO, FRIO"),
    estado: Optional[str] = Query(None, description="Filtro: NUEVO, ASIGNADO, etc."),
    empresa_id: Optional[str] = Query(None, description="ID de la empresa/concesionario"),
    asesor_id: Optional[str] = Query(None, description="ID del asesor asignado"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de leads filtrados por temperatura, estado, empresa y asesor.
    """
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