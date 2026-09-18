# import uvicorn
# from main import run_pipeline

# if __name__ == "__main__":
#     print("🔄 Paso 1: Verificando e ingresando leads nuevos...")
#     # Corre el pipeline (si no hay leads nuevos, termina en 1 segundo sin gastar tokens)
#     run_pipeline(max_workers=5)
    
#     print("\n🚀 Paso 2: Iniciando el servidor API con FastAPI...")
#     # Levanta la API directamente en el puerto 8000
#     uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True)


import threading
import time
import uvicorn
from main import run_pipeline



# ============================================================
# CONFIGURACIÓN
# ============================================================

PIPELINE_INTERVAL = 24 * 60 * 60  # 24 horas


# ============================================================
# EJECUCIÓN DEL PIPELINE
# ============================================================

def ejecutar_pipeline():
    """Ejecuta el pipeline y controla posibles errores."""

    try:
        print("\n🔄 Ejecutando pipeline...")
        run_pipeline(max_workers=5)
        print("✅ Pipeline terminado correctamente.")

    except Exception as e:
        print(f"❌ Error ejecutando el pipeline: {e}")


# ============================================================
# SCHEDULER
# ============================================================

def pipeline_scheduler():
    """
    Ejecuta el pipeline cada 24 horas.

    La primera ejecución NO se hace aquí porque
    ya se ejecuta antes de levantar FastAPI.
    """

    while True:

        print("\n⏰ Próxima ejecución del pipeline en 24 horas.")

        # Esperar 24 horas
        time.sleep(PIPELINE_INTERVAL)

        ejecutar_pipeline()


# ============================================================
# APLICACIÓN
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # 1. Ejecutar pipeline inmediatamente
    # --------------------------------------------------------

    print("🔄 Paso 1: Verificando e ingresando leads nuevos...")

    ejecutar_pipeline()


    # --------------------------------------------------------
    # 2. Crear scheduler en segundo plano
    # --------------------------------------------------------

    scheduler_thread = threading.Thread(
        target=pipeline_scheduler,
        daemon=True
    )

    scheduler_thread.start()

    print("⏰ Scheduler iniciado.")
    print("   El pipeline volverá a ejecutarse en 24 horas.")


    # --------------------------------------------------------
    # 3. Levantar API
    # --------------------------------------------------------

    print("\n🚀 Paso 2: Iniciando el servidor API con FastAPI...")

    uvicorn.run(
        "src.api:app",
        host="127.0.0.1",
        port=8000,
        # reload=True
    )