import uvicorn
from main import run_pipeline

if __name__ == "__main__":
    print("🔄 Paso 1: Verificando e ingresando leads nuevos...")
    # Corre el pipeline (si no hay leads nuevos, termina en 1 segundo sin gastar tokens)
    run_pipeline(max_workers=5)
    
    print("\n🚀 Paso 2: Iniciando el servidor API con FastAPI...")
    # Levanta la API directamente en el puerto 8000
    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True)