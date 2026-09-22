"""Cálculo de probabilidad por Similitud al Perfil de Venta Exitosa."""

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import text

from src.database.connection import engine


def calcular_probabilidad_por_similitud():
    # 1. Cargar el histórico de CIERRES EFECTIVOS
    query_historico = """
        SELECT 
            canal,
            precio_lista,
            horas_al_primer_contacto,
            numero_contactos,
            COALESCE(manifesto_cuota_inicial, 'NO_INFORMA') AS cuota,
            COALESCE(forma_pago_declarada, 'no_informa') AS forma_pago,
            COALESCE(pidio_cita, 'NO') AS pidio_cita
        FROM public.historico_cierres_rag
    """

    # 2. Cargar los LEADS ACTIVOS a evaluar
    query_leads = """
        SELECT 
            lead_id,
            canal,
            0 AS precio_lista,
            0 AS horas_al_primer_contacto,
            1 AS numero_contactos,
            COALESCE(cuota_inicial_declarada::text, 'NO_INFORMA') AS cuota,
            COALESCE(forma_pago, 'no_informa') AS forma_pago,
            COALESCE(pidio_cita_cotizacion, 'NO') AS pidio_cita
        FROM public.leads
    """

    with engine.connect() as conn:
        df_historico = pd.read_sql(text(query_historico), conn)
        df_leads = pd.read_sql(text(query_leads), conn)

    if df_historico.empty or df_leads.empty:
        print("⚠️ Faltan datos en histórico o en leads.")
        return

    # Unificar para codificar variables categóricas de forma homogénea
    combined_df = pd.concat(
        [
            df_historico.assign(es_lead=0),
            df_leads.drop(columns=["lead_id"]).assign(es_lead=1),
        ],
        ignore_index=True,
    )

    cat_cols = ["canal", "cuota", "forma_pago", "pidio_cita"]
    num_cols = ["precio_lista", "horas_al_primer_contacto", "numero_contactos"]

    # CORRECCIÓN DE SINTAXIS: .str.upper().str.strip()
    for col in cat_cols:
        combined_df[col] = combined_df[col].astype(str).str.upper().str.strip()

    # Asegurar que las columnas numéricas sean válidas
    for col in num_cols:
        combined_df[col] = pd.to_numeric(combined_df[col], errors="coerce").fillna(0)

    encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    scaler = StandardScaler()

    encoded_cats = encoder.fit_transform(combined_df[cat_cols])
    scaled_nums = scaler.fit_transform(combined_df[num_cols])

    X_all = np.hstack([scaled_nums, encoded_cats])

    # Separar matriz transformada
    X_historico = X_all[combined_df["es_lead"] == 0]
    X_leads = X_all[combined_df["es_lead"] == 1]

    # 3. CREAR EL "PERFIL IDEAL": Promedio vectorial del histórico de ventas
    perfil_cliente_ideal = np.mean(X_historico, axis=0).reshape(1, -1)

    # 4. CALCULAR SIMILITUD DE CADA LEAD CONTRA EL PERFIL IDEAL
    similitudes = cosine_similarity(X_leads, perfil_cliente_ideal).flatten()

    # Normalizar valores para escalar correctamente de 0 a 100%
    min_sim = similitudes.min() if len(similitudes) > 0 else 0
    max_sim = similitudes.max() if len(similitudes) > 0 else 1
    
    if max_sim > min_sim:
        scores_normalizados = ((similitudes - min_sim) / (max_sim - min_sim)) * 100
    else:
        scores_normalizados = similitudes * 100

    df_leads["score_calculado"] = np.round(scores_normalizados).astype(int)

    # 5. ACTUALIZAR EN BASE DE DATOS (tabla public.leads)
    with engine.begin() as conn:
        for _, row in df_leads.iterrows():
            conn.execute(
                text("""
                UPDATE public.leads 
                SET score_similitud = :score
                WHERE lead_id = :id
            """),
                {"score": int(row["score_calculado"]), "id": row["lead_id"]},
            )

    print(
        f"✅ {len(df_leads)} leads evaluados con éxito según similitud con histórico de ventas."
    )


if __name__ == "__main__":
    calcular_probabilidad_por_similitud()