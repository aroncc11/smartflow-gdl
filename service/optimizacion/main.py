# main.py
# Microservicio de Optimizacion GA - SmartFlow GDL 2026
# Universidad de Guadalajara / CUCEI
# Puerto: 8003 - Compatible con Python 3.13

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List
from datetime import datetime
from contextlib import asynccontextmanager
from genetic_algorithm import optimizar_semaforos, INTERSECCIONES
import os
from supabase import create_client, Client

# ─────────────────────────────────────────────────────────────
# CONEXION A SUPABASE
# ─────────────────────────────────────────────────────────────
# Sin valor por defecto: la clave real ya no vive en el codigo fuente.
# Deben estar configuradas como variables de entorno en Railway.
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─────────────────────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    print("Microservicio de Optimizacion GA listo en :8003")
    yield


# ─────────────────────────────────────────────────────────────
# INICIALIZAR APP
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartFlow GDL - Microservicio de Optimizacion GA",
    description="Optimiza tiempos de semaforo usando Algoritmo Genetico DEAP",
    version="2.0.0",
    lifespan=lifespan
)


# ─────────────────────────────────────────────────────────────
# MODELOS PYDANTIC
# ─────────────────────────────────────────────────────────────
class OptimizacionInput(BaseModel):
    niveles_congestion: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "niveles_congestion": ["high", "medium", "low", "high", "medium"]
            }
        }


# ─────────────────────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "servicio":  "optimizacion",
        "proyecto":  "SmartFlow GDL",
        "estado":    "activo",
        "algoritmo": "Algoritmo Genetico DEAP",
        "version":   "2.0.0",
    }


# ─────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    try:
        result = supabase.table("traffic_lights").select("id", count="exact").execute()
        total  = result.count if result.count else 0
        return {
            "estado":               "healthy",
            "timestamp":            datetime.utcnow().isoformat(),
            "total_optimizaciones": total,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Guardado en Supabase (en segundo plano, NO bloquea la respuesta)
# ─────────────────────────────────────────────────────────────
def _guardar_tiempos_async(tiempos_optimos: dict, fitness: float):
    """
    Guarda el resultado de la optimizacion en Supabase DESPUES de que la
    respuesta ya se envio al cliente. El Algoritmo Genetico ya termino su
    trabajo (tipicamente en milisegundos); este guardado historico no debe
    determinar si la peticion se considera exitosa, ni hacer esperar a
    quien pidio la optimizacion por un viaje de red hacia la base de datos.
    """
    optimized_at = datetime.utcnow().isoformat()
    for int_id, tiempos in tiempos_optimos.items():
        datos_insert = {
            "intersection_id":   int_id,
            "intersection_name": tiempos["nombre"],
            "congestion_level":  tiempos["congestion"],
            "verde_default":     tiempos["verde_default"],
            "verde_optimo":      tiempos["verde_optimo"],
            "rojo_optimo":       tiempos["rojo_optimo"],
            "amarillo":          tiempos["amarillo"],
            "fitness":           fitness,
            "optimized_at":      optimized_at,
        }
        try:
            supabase.table("traffic_lights").insert(datos_insert).execute()
        except Exception as e:
            # El cliente ya recibio su resultado; solo se registra el aviso.
            print(f"[{int_id}] Aviso: fallo el guardado en Supabase en segundo plano: {e}")


# ─────────────────────────────────────────────────────────────
# POST /optimize
# ─────────────────────────────────────────────────────────────
@app.post("/optimize", status_code=201)
def optimizar(datos: OptimizacionInput, background_tasks: BackgroundTasks):
    if len(datos.niveles_congestion) != 5:
        raise HTTPException(
            status_code=400,
            detail="Se requieren exactamente 5 niveles de congestion"
        )

    niveles_validos = {"low", "medium", "high"}
    for nivel in datos.niveles_congestion:
        if nivel not in niveles_validos:
            raise HTTPException(
                status_code=400,
                detail=f"Nivel invalido: {nivel}"
            )

    try:
        print(f"\nEjecutando AG con niveles: {datos.niveles_congestion}")
        inicio = datetime.utcnow()

        resultado = optimizar_semaforos(datos.niveles_congestion)

        duracion = (datetime.utcnow() - inicio).total_seconds()
        print(f"AG completado en {duracion:.2f}s | Fitness: {resultado['fitness']:.2f}")

        # El guardado en Supabase se hace DESPUES de responder al cliente.
        background_tasks.add_task(
            _guardar_tiempos_async,
            resultado["tiempos_optimos"],
            resultado["fitness"],
        )

        return {
            "mensaje":         "Optimizacion completada",
            "duracion_seg":    round(duracion, 2),
            "generaciones":    resultado["generaciones"],
            "fitness":         round(resultado["fitness"], 2),
            "tiempos_optimos": resultado["tiempos_optimos"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en optimizacion: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# GET /optimize/latest
# ─────────────────────────────────────────────────────────────
@app.get("/optimize/latest")
def ultima_optimizacion():
    try:
        resultado = {}
        for config in INTERSECCIONES:
            result = (
                supabase.table("traffic_lights")
                .select("*")
                .eq("intersection_id", config["id"])
                .order("optimized_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                resultado[config["id"]] = result.data[0]

        if not resultado:
            raise HTTPException(
                status_code=404,
                detail="No hay optimizaciones registradas"
            )

        return resultado

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
