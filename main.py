import sys
import pandas as pd
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from tqdm import tqdm

from src.database.connection import engine, SessionLocal, Base
import src.database.models  # Carga los modelos en Base
from src.ingestors.file_ingestor import FileIngestor
from src.processing.cleaner import DataCleaner
from src.processing.llm_extractor import ConversationLLMExtractor, ExtractedLeadContext
from src.processing.scorer import LeadScorer
from src.repository.lead_repository import LeadRepository


def init_database():
    """Crea las tablas en la base de datos si aún no existen."""
    Base.metadata.create_all(bind=engine)


def process_single_lead(
    # Una fila individual extraída del DataFrame de ***leads.csv***. Contiene los datos básicos del cliente (id, nombre, teléfono, empresa, punto de venta).
    row: pd.Series,
    # El diccionario creado a partir de ***conversaciones.json***. Permite buscar la charla de WhatsApp del cliente usando su lead_id
    conversations_dict: Dict[str, Any],
    # Una instancia del extractor de IA. Es la clase encargada de comunicarse con gpt-4o-mini ***para analizar el texto del chat.***
    llm_extractor: ConversationLLMExtractor,
    #Puntajes y cálculos de temperatura para priorizar leads. Se basa en reglas de negocio y datos históricos.
    scorer: LeadScorer,
    # El catálogo de motos cargado en memoria ***(catalogo_motos.csv).*** Sirve para validar precios, cilindrajes o referencias de interés.
    df_catalog: pd.DataFrame,
    # Un conjunto con los IDs de los leads que ya están guardados y analizados en la BD
    existing_lead_ids: set  
) -> Optional[Dict[str, Any]]:
    """
    Procesa un único lead:
    Si ya existe en la BD con análisis de IA, lo omite para no gastar tokens.
    """
    lead_id = str(row.get("lead_id", ""))

    # 🛑 1. OMITIR LLAMADA A LA IA SI EL LEAD YA FUE PROCESADO PREVIAMENTE
    if lead_id in existing_lead_ids:
        return None

    lead_dict = row.to_dict()

    # A. Formatear transcripción de chat
    raw_chat = conversations_dict.get(lead_id, [])
    chat_text = DataCleaner.format_conversation_text(raw_chat) if raw_chat else ""

    # B. Extracción con LLM (Solo si no existe en BD y tiene contenido > 20 caracteres)
    ia_context: Optional[ExtractedLeadContext] = None
    if chat_text and len(chat_text.strip()) > 20:
        try:
            ia_context = llm_extractor.extract_info(chat_text)
        except Exception as e:
            ia_context = ExtractedLeadContext()

    # C. Cálculo de Score y Temperatura
    score, temperatura = scorer.calculate_score(
        lead_data=lead_dict,
        ia_context=ia_context,
        catalog_df=df_catalog
    )

    # D. Mapeo de Identificadores
    empresa_id = str(row.get("empresa_id", "EMP-01")) if pd.notna(row.get("empresa_id")) else "EMP-01"
    punto_venta_id = str(row.get("punto_venta_id")) if pd.notna(row.get("punto_venta_id")) else None

    # E. Armar el payload estructurado
    return {
        "lead_id": lead_id,
        "empresa_id": empresa_id,
        "punto_venta_id": punto_venta_id,
        "nombre": str(row.get("nombre_cliente", "")),
        "email": str(row.get("email", "")) if pd.notna(row.get("email")) else None,
        "telefono": str(row.get("telefono", "")) if pd.notna(row.get("telefono")) else None,
        "canal": str(row.get("canal", "OTROS")).upper(),
        "modelo_interes": ia_context.modelo_interes if (ia_context and ia_context.modelo_interes) else row.get("modelo_interes_texto"),
        "cuota_inicial_declarada": ia_context.cuota_inicial_declarada if ia_context else 0.0,
        "forma_pago": ia_context.forma_pago if ia_context else "NO_ESPECIFICA",
        "intencion_compra": ia_context.intencion_compra if ia_context else "MEDIA",
        "objecion_principal": ia_context.objecion_principal if ia_context else None,
        "pidio_cita_cotizacion": ia_context.pidio_cita_cotizacion if ia_context else False,
        "score_prioridad": score,
        "temperatura": temperatura,
    }


def run_pipeline(max_workers: int = 5):
    """
    Ejecuta el pipeline optimizado con concurrencia e incremento.
    """
    print("🚀 Iniciando el pipeline de Ingesta, Extracción y Scoring...")

    # 1. Asegurar tablas en BD
    init_database()

    # 2. Consultar IDs que ya fueron analizados en la BD
    db = SessionLocal()
    try:
        query_result = db.execute(text("SELECT lead_id FROM leads WHERE temperatura IS NOT NULL")).fetchall()
        existing_lead_ids = set(row[0] for row in query_result)
    except Exception:
        existing_lead_ids = set()
    finally:
        db.close()

    print(f"ℹ️ {len(existing_lead_ids)} leads ya están analizados en la BD y serán omitidos.")

    # 3. Ingesta de datos
    ingestor = FileIngestor()
    df_leads = ingestor.get_leads()
    conversations_dict = ingestor.get_conversations()
    df_catalog = ingestor.get_catalog()
    df_historical = ingestor.get_historical_closures()
    df_advisors = ingestor.get_advisors()

    print(f"📥 Leads leídos desde archivo: {len(df_leads)}")

    # 🛠️ 3.1 Cargar / Actualizar Asesores en la Base de Datos antes de asignar
    db = SessionLocal()
    try:
        df_to_save = df_advisors.copy()

        if "capacidad_diaria_leads" in df_to_save.columns:
            df_to_save = df_to_save.rename(columns={"capacidad_diaria_leads": "capacidad_maxima"})

        df_to_save = df_to_save.drop_duplicates(subset=["asesor_id"], keep="first")
        df_to_save.to_sql("asesores", con=engine, if_exists="append", index=False)
        print("✅ Asesores sincronizados en la base de datos.")
    except Exception as e:
        print(f"⚠️ Nota al guardar asesores (pueden ya existir): {e}")
    finally:
        db.close()

    # 🛠️ 3.2 Cargar / Actualizar Catálogo de Motos en la Base de Datos
    db = SessionLocal()
    try:
        df_catalog_to_save = df_catalog.copy()
        df_catalog_to_save = df_catalog_to_save.drop_duplicates(subset=["sku"], keep="first")
        df_catalog_to_save.to_sql("catalogo_motos", con=engine, if_exists="append", index=False)
        print("✅ Catálogo de motos sincronizado en la base de datos.")
    except Exception as e:
        print(f"⚠️ Nota al guardar el catálogo de motos (pueden ya existir): {e}")
    finally:
        db.close()

    # 4. Limpieza de datos
    df_leads_cleaned = DataCleaner.process_leads_dataframe(df_leads)

    # 5. Componentes principales
    llm_extractor = ConversationLLMExtractor()
    scorer = LeadScorer(historical_df=df_historical)

    processed_payloads = []

    # 6. Procesamiento concurrente con ThreadPoolExecutor
    rows = [row for _, row in df_leads_cleaned.iterrows()]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                process_single_lead,
                row,
                conversations_dict,
                llm_extractor,
                scorer,
                df_catalog,
                existing_lead_ids  # <-- Se pasa la variable aquí explícitamente
            ): row for row in rows
        }

        # Barra de progreso interactiva
        for future in tqdm(as_completed(futures), total=len(rows), desc="Procesando leads nuevos"):
            try:
                payload = future.result()
                if payload is not None:  # Solo guardar los que no fueron omitidos
                    processed_payloads.append(payload)
            except Exception as exc:
                print(f"❌ Error procesando un registro: {exc}")

    if not processed_payloads:
        print("✅ No hay leads nuevos para procesar. Cero tokens consumidos.")
        return

    # 7. Persistencia en Base de Datos para leads nuevos
    print(f"💾 Guardando {len(processed_payloads)} leads nuevos en la Base de Datos...")
    db = SessionLocal()
    repository = LeadRepository(db)

    try:
        for payload in processed_payloads:
            advisor_id = repository.assign_available_advisor(payload["empresa_id"], payload["punto_venta_id"])
            payload["asesor_id"] = advisor_id
            payload["estado_gestion"] = "ASIGNADO" if advisor_id else "NUEVO"

            repository.save_lead(payload)

        print(f"✅ Pipeline finalizado exitosamente. {len(processed_payloads)} leads nuevos guardados.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error durante el guardado en base de datos: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_pipeline(max_workers=5)