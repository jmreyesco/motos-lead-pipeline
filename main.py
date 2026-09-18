"""Orquestador de ingesta, enriquecimiento, scoring y persistencia."""

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
    """Crea las tablas declaradas en los modelos SQLAlchemy."""
    Base.metadata.create_all(bind=engine)


def sync_reference_table(
    dataframe: pd.DataFrame,
    table_name: str,
    key_column: str,
) -> None:
    """
    Carga una tabla de referencia sólo cuando está vacía.

    Las tablas de asesores y catálogo se usan como datos maestros. Se evita
    insertar el mismo CSV en cada ejecución del pipeline porque sus claves
    primarias impedirían duplicados y generarían errores innecesarios.
    """
    with engine.connect() as connection:
        current_rows = connection.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")
        ).scalar() or 0

    if current_rows:
        print(f"ℹ️ La tabla {table_name} ya contiene datos; no se recarga.")
        return

    clean_dataframe = dataframe.drop_duplicates(
        subset=[key_column],
        keep="first",
    )
    clean_dataframe.to_sql(
        table_name,
        con=engine,
        if_exists="append",
        index=False,
    )
    print(f"✅ Tabla {table_name} sincronizada: {len(clean_dataframe)} registros.")


def process_single_lead(
    # Fila individual de leads.csv con la información básica del prospecto.
    row: pd.Series,
    # Conversaciones indexadas por lead_id para localizar el chat correcto.
    conversations_dict: Dict[str, Any],
    # Analizador OpenAI que convierte el chat en campos estructurados.
    llm_extractor: ConversationLLMExtractor,
    # Reglas que convierten las señales del lead en score y temperatura.
    scorer: LeadScorer,
    # Catálogo cargado para mantener el contrato actual del scorer.
    df_catalog: pd.DataFrame,
    # IDs que ya tienen temperatura y no deben consumir tokens otra vez.
    existing_lead_ids: set,
) -> Optional[Dict[str, Any]]:
    """Procesa un lead y devuelve el payload listo para guardarse."""
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
    """Ejecuta el flujo completo de archivos, IA, scoring y PostgreSQL."""
    print("🚀 Iniciando el pipeline de Ingesta, Extracción y Scoring...")

    # 1. Asegurar tablas en BD
    init_database()

    # 2. Consultar IDs ya analizados para evitar llamadas repetidas a OpenAI.
    db = SessionLocal()
    try:
        query_result = db.execute(text("SELECT lead_id FROM leads WHERE temperatura IS NOT NULL")).fetchall()
        existing_lead_ids = set(row[0] for row in query_result)
    except Exception:
        existing_lead_ids = set()
    finally:
        db.close()

    print(f"ℹ️ {len(existing_lead_ids)} leads ya están analizados en la BD y serán omitidos.")

    # 3. Leer todos los archivos de entrada.
    ingestor = FileIngestor()
    df_leads = ingestor.get_leads()
    conversations_dict = ingestor.get_conversations()
    df_catalog = ingestor.get_catalog()
    df_historical = ingestor.get_historical_closures()
    df_advisors = ingestor.get_advisors()

    print(f"📥 Leads leídos desde archivo: {len(df_leads)}")

    # 3.1 Cargar asesores antes de intentar asignarlos a los leads.
    try:
        df_to_save = df_advisors.copy()
        if "capacidad_diaria_leads" in df_to_save.columns:
            df_to_save = df_to_save.rename(columns={"capacidad_diaria_leads": "capacidad_maxima"})
        sync_reference_table(df_to_save, "asesores", "asesor_id")
    except Exception as e:
        print(f"⚠️ No se pudo sincronizar asesores: {e}")

    # 3.2 Cargar el catálogo para dejarlo disponible como tabla de referencia.
    try:
        sync_reference_table(df_catalog, "catalogo_motos", "sku")
    except Exception as e:
        print(f"⚠️ No se pudo sincronizar el catálogo de motos: {e}")

    # 4. Limpieza de datos
    df_leads_cleaned = DataCleaner.process_leads_dataframe(df_leads)

    # 5. Crear los componentes que se reutilizarán durante todo el lote.
    llm_extractor = ConversationLLMExtractor()
    scorer = LeadScorer(historical_df=df_historical)

    processed_payloads = []

    # 6. Procesar en paralelo porque la extracción de IA es una operación I/O.
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

    # 7. Asignar asesor y guardar únicamente los leads nuevos.
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