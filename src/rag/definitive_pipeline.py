"""RAG y análisis comparativo del pipeline de cierres definitivos."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd
from openai import OpenAI
from sqlalchemy import text

from src.config import settings
from src.database.connection import engine

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
HISTORICAL_TABLE = "historico_cierres_rag"
FINAL_TABLE = "cierres_definitivos"


def _read_historical_file() -> pd.DataFrame:
    """Lee el histórico como CSV o Excel según la extensión configurada."""
    path = settings.HISTORICAL_FILE
    if not path.exists():
        raise FileNotFoundError(f"Archivo histórico no encontrado: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def _safe_text(value: Any) -> str:
    """Convierte valores nulos a texto estable para embeddings y auditoría."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _database_value(value: Any) -> Any:
    """Convierte NaN de pandas en NULL para que PostgreSQL lo acepte."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def _historical_text(row: pd.Series) -> str:
    """Construye el documento textual que representa un cierre histórico."""
    fields = [
        f"canal: {_safe_text(row.get('canal'))}",
        f"empresa: {_safe_text(row.get('empresa_id'))}",
        f"punto de venta: {_safe_text(row.get('punto_venta_id'))}",
        f"modelo: {_safe_text(row.get('modelo_cotizado'))}",
        f"precio: {_safe_text(row.get('precio_lista'))}",
        f"horas al primer contacto: {_safe_text(row.get('horas_al_primer_contacto'))}",
        f"número de contactos: {_safe_text(row.get('numero_contactos'))}",
        f"cuota inicial: {_safe_text(row.get('manifesto_cuota_inicial'))}",
        f"forma de pago: {_safe_text(row.get('forma_pago_declarada'))}",
        f"pidió cita: {_safe_text(row.get('pidio_cita'))}",
        f"desenlace: {_safe_text(row.get('desenlace'))}",
    ]
    return " | ".join(fields)


def _lead_text(row: dict[str, Any]) -> str:
    """Construye el documento comparable para un lead ya analizado."""
    fields = [
        f"canal: {_safe_text(row.get('canal'))}",
        f"empresa: {_safe_text(row.get('empresa_id'))}",
        f"punto de venta: {_safe_text(row.get('punto_venta_id'))}",
        f"modelo: {_safe_text(row.get('modelo_interes'))}",
        f"precio: {_safe_text(row.get('precio_lista'))}",
        f"horas al primer contacto: {_safe_text(row.get('horas_al_primer_contacto'))}",
        f"número de contactos: {_safe_text(row.get('numero_contactos'))}",
        f"cuota inicial: {_safe_text(row.get('cuota_inicial_declarada'))}",
        f"forma de pago: {_safe_text(row.get('forma_pago'))}",
        f"pidió cita: {_safe_text(row.get('pidio_cita_cotizacion'))}",
        f"score actual: {_safe_text(row.get('score_prioridad'))}",
        f"temperatura actual: {_safe_text(row.get('temperatura'))}",
    ]
    return " | ".join(fields)


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    """Divide textos para solicitar embeddings en lotes controlados."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _embedding_literal(values: list[float]) -> str:
    """Serializa un embedding en el formato que acepta pgvector."""
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def create_rag_tables() -> None:
    """Crea las tablas nuevas sin modificar las tablas existentes."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {HISTORICAL_TABLE} (
                cierre_id VARCHAR(50) PRIMARY KEY,
                fecha_registro DATE NULL,
                canal VARCHAR(50),
                empresa_id VARCHAR(50),
                punto_venta_id VARCHAR(50),
                modelo_cotizado VARCHAR(150),
                precio_lista DOUBLE PRECISION,
                horas_al_primer_contacto DOUBLE PRECISION,
                numero_contactos INTEGER,
                manifesto_cuota_inicial VARCHAR(30),
                forma_pago_declarada VARCHAR(50),
                pidio_cita VARCHAR(20),
                desenlace VARCHAR(50),
                documento TEXT NOT NULL,
                embedding vector({EMBEDDING_DIMENSIONS}),
                creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {FINAL_TABLE} (
                lead_id VARCHAR(50) PRIMARY KEY REFERENCES leads(lead_id),
                score_pipeline DOUBLE PRECISION,
                temperatura_pipeline VARCHAR(20),
                cierre_historico_id VARCHAR(50) REFERENCES {HISTORICAL_TABLE}(cierre_id),
                similitud_historica DOUBLE PRECISION,
                tasa_exito_historica DOUBLE PRECISION,
                score_definitivo DOUBLE PRECISION NOT NULL,
                temperatura_definitiva VARCHAR(20) NOT NULL,
                recomendacion TEXT,
                analizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))


def load_historical_rag(batch_size: int = 100) -> int:
    """Carga el histórico y sus embeddings; es idempotente por ``cierre_id``."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY es necesaria para construir el RAG.")

    historical = _read_historical_file()
    required = {"lead_id", "desenlace"}
    missing = required.difference(historical.columns)
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en el histórico: {sorted(missing)}")

    documents = [_historical_text(row) for _, row in historical.iterrows()]
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    embeddings: list[list[float]] = []
    for batch in _chunks(documents, batch_size):
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        embeddings.extend(item.embedding for item in response.data)

    inserted = 0
    with engine.begin() as connection:
        for (_, row), document, embedding in zip(historical.iterrows(), documents, embeddings):
            payload = {
                "cierre_id": _safe_text(row.get("lead_id")),
                "documento": document,
                "embedding": _embedding_literal(embedding),
            }
            for column in [
                "fecha_registro", "canal", "empresa_id", "punto_venta_id",
                "modelo_cotizado", "precio_lista", "horas_al_primer_contacto",
                "numero_contactos", "manifesto_cuota_inicial",
                "forma_pago_declarada", "pidio_cita", "desenlace",
            ]:
                payload[column] = _database_value(row.get(column))

            connection.execute(text(f"""
                INSERT INTO {HISTORICAL_TABLE} (
                    cierre_id, fecha_registro, canal, empresa_id, punto_venta_id,
                    modelo_cotizado, precio_lista, horas_al_primer_contacto,
                    numero_contactos, manifesto_cuota_inicial, forma_pago_declarada,
                    pidio_cita, desenlace, documento, embedding
                ) VALUES (
                    :cierre_id, :fecha_registro, :canal, :empresa_id, :punto_venta_id,
                    :modelo_cotizado, :precio_lista, :horas_al_primer_contacto,
                    :numero_contactos, :manifesto_cuota_inicial, :forma_pago_declarada,
                    :pidio_cita, :desenlace, :documento, CAST(:embedding AS vector)
                ) ON CONFLICT (cierre_id) DO UPDATE SET
                    documento = EXCLUDED.documento,
                    embedding = EXCLUDED.embedding,
                    desenlace = EXCLUDED.desenlace
            """), payload)
            inserted += 1
    return inserted


def _success_value(outcome: str) -> float:
    """Convierte el desenlace histórico en una señal binaria de éxito."""
    return 1.0 if outcome.strip().upper() in {"VENDIDO", "CERRADO", "GANADO", "EXITOSO"} else 0.0


def analyze_definitive_closures(top_k: int = 5) -> int:
    """Contrasta cada lead existente con sus cierres históricos más similares."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY es necesaria para analizar los leads.")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    with engine.begin() as connection:
        leads = connection.execute(text("SELECT * FROM leads ORDER BY lead_id")).mappings().all()
        processed = 0
        for lead in leads:
            document = _lead_text(dict(lead))
            embedding = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=document,
            ).data[0].embedding
            vector = _embedding_literal(embedding)
            matches = connection.execute(text(f"""
                SELECT cierre_id, desenlace, 1 - (embedding <=> CAST(:embedding AS vector)) AS similitud
                FROM {HISTORICAL_TABLE}
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """), {"embedding": vector, "top_k": top_k}).mappings().all()
            if not matches:
                continue

            weights = [max(float(match["similitud"]), 0.0) for match in matches]
            total_weight = sum(weights) or 1.0
            success_rate = sum(
                weight * _success_value(match["desenlace"])
                for weight, match in zip(weights, matches)
            ) / total_weight
            pipeline_score = float(lead["score_prioridad"] or 0.0)
            # Este score pertenece exclusivamente al análisis histórico.
            # El score del pipeline original se conserva sólo como referencia.
            definitive_score = round(success_rate * 100.0, 2)
            temperature = "CALIENTE" if definitive_score >= 70 else "TIBIO" if definitive_score >= 40 else "FRIO"
            recommendation = (
                "Priorizar: patrones históricos similares muestran alta probabilidad de cierre."
                if success_rate >= 0.60
                else "Dar seguimiento: la evidencia histórica es mixta o insuficiente."
                if success_rate >= 0.30
                else "Revisar estrategia: los patrones históricos similares muestran bajo cierre."
            )
            connection.execute(text(f"""
                INSERT INTO {FINAL_TABLE} (
                    lead_id, score_pipeline, temperatura_pipeline, cierre_historico_id,
                    similitud_historica, tasa_exito_historica, score_definitivo,
                    temperatura_definitiva, recomendacion
                ) VALUES (
                    :lead_id, :score_pipeline, :temperatura_pipeline, :cierre_historico_id,
                    :similitud_historica, :tasa_exito_historica, :score_definitivo,
                    :temperatura_definitiva, :recomendacion
                ) ON CONFLICT (lead_id) DO UPDATE SET
                    score_pipeline = EXCLUDED.score_pipeline,
                    temperatura_pipeline = EXCLUDED.temperatura_pipeline,
                    cierre_historico_id = EXCLUDED.cierre_historico_id,
                    similitud_historica = EXCLUDED.similitud_historica,
                    tasa_exito_historica = EXCLUDED.tasa_exito_historica,
                    score_definitivo = EXCLUDED.score_definitivo,
                    temperatura_definitiva = EXCLUDED.temperatura_definitiva,
                    recomendacion = EXCLUDED.recomendacion,
                    analizado_en = CURRENT_TIMESTAMP
            """), {
                "lead_id": lead["lead_id"],
                "score_pipeline": pipeline_score,
                "temperatura_pipeline": lead["temperatura"],
                "cierre_historico_id": matches[0]["cierre_id"],
                "similitud_historica": float(matches[0]["similitud"]),
                "tasa_exito_historica": round(success_rate, 4),
                "score_definitivo": definitive_score,
                "temperatura_definitiva": temperature,
                "recomendacion": recommendation,
            })
            processed += 1
    return processed


def run_definitive_pipeline() -> None:
    """Ejecuta sólo el nuevo análisis RAG, sin reprocesar el pipeline original."""
    create_rag_tables()
    loaded = load_historical_rag()
    analyzed = analyze_definitive_closures()
    print(f"✅ RAG histórico sincronizado: {loaded} registros.")
    print(f"✅ Cierres definitivos calculados: {analyzed} leads.")


if __name__ == "__main__":
    run_definitive_pipeline()
