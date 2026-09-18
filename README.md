# Motos Lead Pipeline

Pipeline de leads para motocicletas. Lee archivos CSV/JSON, limpia contactos,
extrae señales comerciales con OpenAI, calcula un score, asigna asesores,
guarda los resultados en PostgreSQL y los expone mediante FastAPI.

## Flujo de ejecución

1. `run_app.py` ejecuta `run_pipeline()` y luego inicia Uvicorn.
2. `main.py` crea las tablas ORM y consulta los `lead_id` ya procesados.
3. `FileIngestor` lee leads, conversaciones, asesores, catálogo e histórico.
4. `DataCleaner` normaliza teléfonos, correos, nombres y elimina duplicados.
5. Cada conversación se convierte en texto y `ConversationLLMExtractor` extrae
   modelo, cuota, forma de pago, intención, objeción y solicitud de cita.
6. `LeadScorer` calcula el score y asigna `CALIENTE`, `TIBIO` o `FRIO`.
7. Se asigna un asesor por empresa y punto de venta.
8. `LeadRepository` inserta o actualiza el lead en PostgreSQL.
9. FastAPI ofrece consultas de leads, métricas y actualización de estados.

## Archivos de entrada

- `data/leads.csv`: datos originales de los prospectos.
- `data/conversaciones.json`: chats asociados por `lead_id`.
- `data/asesores.csv`: asesores y sus puntos de venta.
- `data/catalogo_motos.csv`: catálogo y disponibilidad.
- `data/historico_cierres.csv`: histórico disponible para futuras calibraciones.

## Análisis RAG de cierres definitivos

El análisis histórico es una funcionalidad independiente y no se ejecuta al
levantar la API ni al ejecutar el pipeline original. Lee
`data/historico_cierres.csv` (también admite `.xlsx`/`.xls`), genera embeddings
con `text-embedding-3-small` y los guarda en PostgreSQL usando `pgvector`.
Después busca los cierres históricos más parecidos a cada registro de `leads`,
combina la evidencia histórica con el score actual y guarda el resultado en:

- `historico_cierres_rag`: documentos históricos y sus vectores.
- `cierres_definitivos`: score, temperatura, similitud, tasa histórica de éxito
  y recomendación por lead.

La extensión PostgreSQL `vector` debe estar habilitada y `OPENAI_API_KEY` debe
estar configurada. Para ejecutarlo explícitamente:

```powershell
python -m pip install -r requirements.txt
python run_definitive_pipeline.py
```

El proceso es idempotente: no elimina ni modifica `leads`; actualiza sólo las
dos tablas nuevas. El score definitivo conserva el 70% del score existente y
usa 30% de la tasa de éxito de los vecinos históricos, para que el nuevo
análisis no reemplace silenciosamente la lógica actual.

## Ejecución

Con el entorno virtual activado:

```powershell
.\venv\Scripts\python.exe run_app.py
```

Para iniciar sólo la API:

```powershell
.\venv\Scripts\python.exe -m uvicorn src.api:app --reload
```

La API queda disponible en `http://127.0.0.1:8000`.

## Endpoints principales

- `GET /api/v1/leads/prioritarios`
- `GET /api/v1/leads`
- `PATCH /api/v1/leads/{lead_id}/estado`
- `GET /api/v1/metrics/summary`

Los endpoints de leads aceptan filtros opcionales por temperatura, estado,
empresa y asesor. Las métricas también respetan empresa y asesor.

## Decisiones de limpieza

- Se conservaron `BaseLeadIngestor` y `FileIngestor` porque forman la
  abstracción activa de ingesta y permiten añadir otras fuentes en el futuro.
- Se eliminaron archivos vacíos o legados que no se importaban:
  `dashboard/app.py`, `src/ingestors/api_ingestor.py` y el `schema.sql`
  antiguo, que además no coincidía con los modelos ORM reales.
- Se excluyen del control de versiones `.env`, `venv`, cachés y bytecode.
- La sincronización de asesores y catálogo es idempotente: si la tabla ya tiene
  filas, no vuelve a insertar el CSV.
