# main.py
# Microservicio de Prediccion IA - SmartFlow GDL 2026
# Universidad de Guadalajara / CUCEI
# Puerto: 8002 - Compatible con Python 3.13

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager
from predictor import Predictor
import os
import json
import redis
from supabase import create_client, Client

# ─────────────────────────────────────────────────────────────
# CONEXION A SUPABASE
# ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ipcunenaytijdproskxf.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_tUdmn3h_fIx9zERQweNTyA_HYqThsb4")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────────────────────────
# CONEXION A REDIS (cache de predicciones, TTL 60s)
# ─────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL")
CACHE_TTL_SEGUNDOS = 60

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None
    if redis_client:
        redis_client.ping()
        print("Conexion a Redis establecida (cache TTL 60s)")
    else:
        print("REDIS_URL no configurada - el servicio corre sin cache")
except Exception as e:
    print(f"No se pudo conectar a Redis, se continua sin cache: {e}")
    redis_client = None


def guardar_en_cache(intersection_id: str, resultado: dict):
    """Guarda la ultima prediccion de una interseccion en Redis con TTL de 60s."""
    if not redis_client:
        return
    try:
        redis_client.setex(
            f"pred:{intersection_id}",
            CACHE_TTL_SEGUNDOS,
            json.dumps(resultado),
        )
    except Exception as e:
        print(f"Aviso: no se pudo escribir en cache Redis: {e}")


def leer_de_cache(intersection_id: str) -> Optional[dict]:
    """Lee la ultima prediccion cacheada de una interseccion, si sigue vigente."""
    if not redis_client:
        return None
    try:
        data = redis_client.get(f"pred:{intersection_id}")
        return json.loads(data) if data else None
    except Exception as e:
        print(f"Aviso: no se pudo leer cache Redis: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# URL MICROSERVICIO OPTIMIZACION
# ─────────────────────────────────────────────────────────────
OPTIMIZACION_URL = os.getenv("OPTIMIZACION_URL", "http://localhost:8003")

# ─────────────────────────────────────────────────────────────
# PREDICTOR
# ─────────────────────────────────────────────────────────────
predictor = None

# Clave de Redis donde se guarda el hash {intersection_id: congestion_level}
# usado para saber cuando ya tenemos lectura de las 5 intersecciones.
# Antes era un diccionario global en memoria (predicciones_actuales), lo cual
# no es correcto en un sistema distribuido si el servicio llega a correr con
# mas de una replica. Con Redis, el estado se comparte entre instancias.
REDIS_KEY_NIVELES_ACTUALES = "niveles_congestion_actuales"


def guardar_nivel_actual(intersection_id: str, nivel: str):
    if not redis_client:
        return
    try:
        redis_client.hset(REDIS_KEY_NIVELES_ACTUALES, intersection_id, nivel)
    except Exception as e:
        print(f"Aviso: no se pudo actualizar niveles en Redis: {e}")


def contar_niveles_actuales() -> dict:
    if not redis_client:
        return {}
    try:
        return redis_client.hgetall(REDIS_KEY_NIVELES_ACTUALES)
    except Exception as e:
        print(f"Aviso: no se pudo leer niveles de Redis: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    global predictor
    predictor = Predictor()
    print("Microservicio de Prediccion IA listo en :8002")
    yield


# ─────────────────────────────────────────────────────────────
# INICIALIZAR APP
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartFlow GDL - Microservicio de Prediccion IA",
    description="Predice nivel de congestion vehicular usando Random Forest",
    version="2.0.0",
    lifespan=lifespan
)


# ─────────────────────────────────────────────────────────────
# LLAMAR AL OPTIMIZADOR
# ─────────────────────────────────────────────────────────────
def llamar_optimizacion(niveles: list):
    # Comunicacion sincrona via HTTP directo entre microservicios
    # (no se usa un broker de mensajes como RabbitMQ en este proyecto).
    try:
        import httpx
        httpx.post(
            f"{OPTIMIZACION_URL}/optimize",
            json={"niveles_congestion": niveles},
            timeout=30
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# MODELOS PYDANTIC
# ─────────────────────────────────────────────────────────────
class LecturaInput(BaseModel):
    intersection_id: str
    reading_id:      Optional[int] = None
    vehicles_count:  int
    avg_speed_kmh:   float
    hour_of_day:     int
    day_of_week:     int
    is_peak_hour:    bool
    incident_flag:   bool
    weather:         str
    historical_avg:  float


# ─────────────────────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "servicio": "prediccion",
        "proyecto": "SmartFlow GDL",
        "estado":   "activo",
        "modelo":   "Random Forest",
        "version":  "2.0.0",
        "cache":    "redis" if redis_client else "deshabilitado",
    }


# ─────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    try:
        result = supabase.table("predictions").select("id", count="exact").execute()
        total  = result.count if result.count else 0

        redis_ok = False
        if redis_client:
            try:
                redis_client.ping()
                redis_ok = True
            except Exception:
                redis_ok = False

        return {
            "estado":             "healthy",
            "timestamp":          datetime.utcnow().isoformat(),
            "modelo":             "Random Forest cargado",
            "total_predicciones": total,
            "redis":              "ok" if redis_ok else "no disponible",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ─────────────────────────────────────────────────────────────
# POST /predict
# ─────────────────────────────────────────────────────────────
@app.post("/predict", status_code=201)
def predecir(lectura: LecturaInput):
    try:
        resultado = predictor.predecir(lectura.dict())

        datos = {
            "intersection_id":  lectura.intersection_id,
            "reading_id":       lectura.reading_id,
            "congestion_level": resultado["congestion_level"],
            "confidence":       resultado["confidence"],
            "prob_low":         resultado["probabilities"].get("low", 0),
            "prob_medium":      resultado["probabilities"].get("medium", 0),
            "prob_high":        resultado["probabilities"].get("high", 0),
            "predicted_at":     datetime.utcnow().isoformat(),
        }

        result = supabase.table("predictions").insert(datos).execute()
        registro_id = result.data[0]["id"] if result.data else None

        print(f"[{lectura.intersection_id}] Prediccion #{registro_id} - "
              f"{resultado['congestion_level'].upper()} "
              f"| Confianza: {resultado['confidence']:.2%}")

        respuesta = {
            "id":               registro_id,
            "intersection_id":  lectura.intersection_id,
            "congestion_level": resultado["congestion_level"],
            "confidence":       resultado["confidence"],
            "probabilities":    resultado["probabilities"],
            "predicted_at":     datos["predicted_at"],
        }

        # Cachear la ultima prediccion de esta interseccion (TTL 60s)
        guardar_en_cache(lectura.intersection_id, respuesta)

        # Guardar nivel actual en Redis y llamar optimizador si ya tenemos las 5
        guardar_nivel_actual(lectura.intersection_id, resultado["congestion_level"])
        niveles_actuales = contar_niveles_actuales()

        if len(niveles_actuales) == 5:
            niveles = [
                niveles_actuales.get(f"INT-00{i}", "medium")
                for i in range(1, 6)
            ]
            llamar_optimizacion(niveles)

        return respuesta

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en prediccion: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# GET /predict/{intersection_id}
# ─────────────────────────────────────────────────────────────
@app.get("/predict/{intersection_id}")
def obtener_predicciones(intersection_id: str, limite: int = 10):
    try:
        # Atajo rapido: si solo piden la ultima lectura (limite=1),
        # se intenta servir desde el cache de Redis antes de ir a Supabase.
        if limite == 1:
            cacheada = leer_de_cache(intersection_id)
            if cacheada:
                return {
                    "intersection_id": intersection_id,
                    "total": 1,
                    "fuente": "cache",
                    "predicciones": [cacheada],
                }

        result = (
            supabase.table("predictions")
            .select("id, congestion_level, confidence, prob_low, prob_medium, prob_high, predicted_at")
            .eq("intersection_id", intersection_id)
            .order("predicted_at", desc=True)
            .limit(limite)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No hay predicciones para {intersection_id}"
            )

        return {
            "intersection_id": intersection_id,
            "total":           len(result.data),
            "fuente":          "supabase",
            "predicciones":    result.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en prediccion: {str(e)}"
        )
