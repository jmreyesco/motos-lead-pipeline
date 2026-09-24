"""
Módulo de Scoring Predictivo - Motos y Servicios S.A.S.
Calcula la probabilidad de compra (0-100%) y la temperatura comercial (CALIENTE, TIBIO, FRÍO)
mediante Regresión Logística entrenada con datos históricos, corregida contra desviaciones
y sincronizada directamente con la tabla public.leads en PostgreSQL.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import text

from src.database.connection import engine


def calcular_probabilidad_regresion_logistica():
    print("🚀 Iniciando pipeline de scoring con Regresión Logística...")

    # ==============================================================================
    # 1. CARGA DE DATOS DESDE POSTGRESQL (SCHEMA CONFIRMADO)
    # ==============================================================================
    
    # Query Histórico (Entrenamiento)
    query_historico = """
        SELECT 
            canal,
            COALESCE(precio_lista, 0) AS precio_lista,
            horas_al_primer_contacto,
            COALESCE(numero_contactos, 1) AS numero_contactos,
            COALESCE(manifesto_cuota_inicial, 'NO_INFORMA') AS cuota,
            COALESCE(forma_pago_declarada, 'NO_INFORMA') AS forma_pago,
            COALESCE(pidio_cita, 'NO') AS pidio_cita,
            CASE 
                WHEN LOWER(TRIM(COALESCE(desenlace, ''))) IN ('cerrado', 'ganado', '1', 'true') THEN 1
                ELSE 0
            END AS desenlace
        FROM public.historico_cierres_rag
    """

    # Query Leads Activos (Inferencia) - JOIN exacto con catálogo vía SKU
    query_leads = """
        SELECT 
            l.lead_id,
            COALESCE(l.canal, 'WHATSAPP') AS canal,
            l.fecha_creacion AS fecha_registro,
            COALESCE(c.precio_lista, 0) AS precio_lista,
            1 AS numero_contactos,
            COALESCE(l.cuota_inicial_declarada::text, '0') AS cuota,
            COALESCE(l.forma_pago, 'NO_INFORMA') AS forma_pago,
            COALESCE(l.pidio_cita_cotizacion::text, 'NO') AS pidio_cita
        FROM public.leads l
        LEFT JOIN public.catalogo_motos c 
            ON TRIM(l.sku) = TRIM(c.sku)
    """

    with engine.connect() as conn:
        df_historico = pd.read_sql(text(query_historico), conn)
        df_leads = pd.read_sql(text(query_leads), conn)

    if df_historico.empty or df_leads.empty:
        print("⚠️ Error: No se encontraron registros en el histórico o en la tabla de leads.")
        return

    # ==============================================================================
    # 2. RESOLUCIÓN DE DESVIACIONES Y NORMALIZACIÓN DE DATOS
    # ==============================================================================
    
    # --- A. Homologación de Banderas Categóricas (pidio_cita) ---
    def normalizar_flag_cita(valor):
        val_str = str(valor).upper().strip()
        if val_str in ['TRUE', '1', 'SI', 'SÍ']:
            return 'SI'
        return 'NO'

    df_historico['pidio_cita'] = df_historico['pidio_cita'].apply(normalizar_flag_cita)
    df_leads['pidio_cita'] = df_leads['pidio_cita'].apply(normalizar_flag_cita)

    # --- B. Corrección de Escala para Cuota Inicial (Pesos a Millones) ---
    def normalizar_cuota(val):
        try:
            num = float(val)
            if num > 1000:
                num = num / 1000000.0  # Convierte valores en pesos ($2,500,000) a millones (2.5)
            if num >= 2.0:
                return 'ALTA'
            elif num > 0:
                return 'MEDIA'
            else:
                return 'NO'
        except ValueError:
            val_str = str(val).upper().strip()
            if val_str in ['SI', 'CREDITO', 'MEDIA', 'ALTA']:
                return 'MEDIA'
            return 'NO_INFORMA'

    df_historico['cuota'] = df_historico['cuota'].apply(normalizar_cuota)
    df_leads['cuota'] = df_leads['cuota'].apply(normalizar_cuota)

    # --- C. Tratamiento de Horas y Outliers con Transformación Logarítmica ---
    mediana_horas = df_historico['horas_al_primer_contacto'].median()
    if pd.isna(mediana_horas):
        mediana_horas = 8.0

    df_historico['horas_limpias'] = df_historico['horas_al_primer_contacto'].fillna(mediana_horas)
    df_historico['log_horas'] = np.log1p(np.maximum(0, df_historico['horas_limpias']))
    df_leads['log_horas'] = np.log1p(mediana_horas)

    # --- D. Normalización de Precio Lista ---
    precio_promedio = df_historico[df_historico['precio_lista'] > 0]['precio_lista'].mean()
    if pd.isna(precio_promedio):
        precio_promedio = 10000000.0

    df_historico['precio_lista'] = np.where(df_historico['precio_lista'] <= 0, precio_promedio, df_historico['precio_lista'])
    df_leads['precio_lista'] = np.where(df_leads['precio_lista'] <= 0, precio_promedio, df_leads['precio_lista'])

    # --- E. Unificación para Encoding Homogéneo ---
    combined_df = pd.concat([
        df_historico.drop(columns=['desenlace', 'horas_al_primer_contacto', 'horas_limpias']).assign(es_lead=0),
        df_leads.drop(columns=['lead_id', 'fecha_registro']).assign(es_lead=1)
    ], ignore_index=True)

    cat_cols = ["canal", "cuota", "forma_pago", "pidio_cita"]
    num_cols = ["precio_lista", "log_horas", "numero_contactos"]

    for col in cat_cols:
        combined_df[col] = combined_df[col].astype(str).str.upper().str.strip()

    for col in num_cols:
        combined_df[col] = pd.to_numeric(combined_df[col], errors="coerce").fillna(0)

    # --- F. Escalado Numérico (Z-Score) y One-Hot Encoding ---
    encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    scaler = StandardScaler()

    encoded_cats = encoder.fit_transform(combined_df[cat_cols])
    scaled_nums = scaler.fit_transform(combined_df[num_cols])

    X_all = np.hstack([scaled_nums, encoded_cats])

    # Separación en Matrices
    X_train = X_all[combined_df["es_lead"] == 0]
    y_train = df_historico["desenlace"].astype(int).values

    X_leads = X_all[combined_df["es_lead"] == 1]

    # ==============================================================================
    # 3. ENTRENAMIENTO DE LA REGRESIÓN LOGÍSTICA
    # ==============================================================================
    modelo = LogisticRegression(class_weight='balanced', random_state=42, max_iter=1000)
    modelo.fit(X_train, y_train)

    # ==============================================================================
    # 4. INFERENCIA Y ASIGNACIÓN DE TEMPERATURAS
    # ==============================================================================
    # Garantizar la toma explícita de la clase positiva (1 = Cerrado/Venta Exitosa)
    idx_clase_ganada = list(modelo.classes_).index(1)
    probabilidades = modelo.predict_proba(X_leads)[:, idx_clase_ganada]

    # Re-escalado Relativo MinMax
    min_p, max_p = probabilidades.min(), probabilidades.max()
    if max_p > min_p:
        scores_escalados = ((probabilidades - min_p) / (max_p - min_p)) * 100
    else:
        scores_escalados = probabilidades * 100

    df_leads["porcentaje_compra"] = np.round(scores_escalados, 2)

    def obtener_temperatura(porcentaje):
        if porcentaje >= 70:
            return "CALIENTE"
        elif porcentaje >= 40:
            return "TIBIO"
        else:
            return "FRÍO"

    df_leads["temperatura_lead"] = df_leads["porcentaje_compra"].apply(obtener_temperatura)

    # Impresión de control operacional
    print("\n" + "="*50)
    print("DISTRIBUCIÓN FINAL DE TEMPERATURAS COMERCIALES:")
    print(df_leads["temperatura_lead"].value_counts().to_string())
    print("="*50 + "\n")

    # ==============================================================================
    # 5. ACTUALIZACIÓN BATCH EN LA BASE DE DATOS (public.leads)
    # ==============================================================================
    update_query = text("""
        UPDATE public.leads 
        SET porcentaje_compra = :porcentaje,
            temperatura_lead = :temperatura
        WHERE lead_id = :id
    """)

    datos_a_actualizar = [
        {
            "porcentaje": float(row["porcentaje_compra"]),
            "temperatura": str(row["temperatura_lead"]),
            "id": row["lead_id"],
        }
        for _, row in df_leads.iterrows()
    ]

    with engine.begin() as conn:
        conn.execute(update_query, datos_a_actualizar)

    print(f"🎉 ¡Éxito! Se evaluaron y actualizaron {len(df_leads)} leads en la base de datos.")


if __name__ == "__main__":
    calcular_probabilidad_regresion_logistica()