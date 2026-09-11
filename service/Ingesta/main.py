# main.py
# Microservicio de Ingesta - SmartFlow GDL 2026
# Universidad de Guadalajara / CUCEI
# Puerto: 8001
# Usa cliente oficial de Supabase compatible con Python 3.13

from fastapi import FastAPI, HTTPException
from datetime import datetime
from models import SensorReading
from database import get_supabase
import httpx
import os

# ─────────────────────────────────────────────────────────────
# INICIALIZAR APP
# ─────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    try:
        sb = get_supabase()
        sb.table("traffic_readings").select("id").limit(1).execute()
        print("Base de datos Supabase inicializada")
    except Exception as e:
        print(f"ERROR en startup: {str(e)}")
    yield

app = FastAPI(
    title="SmartFlow GDL - Microservicio de Ingesta",
    description="Recibe y persiste lecturas de sensores de trafico urbano",
    version="2.0.0",
    lifespan=lifespan
)

# ─────────────────────────────────────────────────────────────
# LLAMAR AL MICROSERVICIO DE PREDICCION
# ─────────────────────────────────────────────────────────────
PREDICCION_URL = os.getenv("PREDICCION_URL", "http://localhost:8002")

def llamar_prediccion(lectura_id: int, lectura: SensorReading):
    try:
        datos = {
            "intersection_id": lectura.intersection_id,
            "reading_id":      lectura_id,
            "vehicles_count":  lectura.vehicles_count,
            "avg_speed_kmh":   lectura.avg_speed_kmh,
            "hour_of_day":     lectura.hour_of_day,
            "day_of_week":     lectura.day_of_week,
            "is_peak_hour":    lectura.is_peak_hour,
            "incident_flag":   lectura.incident_flag,
            "weather":         lectura.weather,
            "historical_avg":  lectura.historical_avg,
        }
        httpx.post(
            f"{PREDICCION_URL}/predict",
            json=datos,
            timeout=3
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# GET / - verificacion rapida
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "servicio": "ingesta",
        "proyecto": "SmartFlow GDL",
        "estado":   "activo",
        "version":  "2.0.0",
    }


# ─────────────────────────────────────────────────────────────
# GET /health - estado detallado
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    try:
        sb     = get_supabase()
        result = sb.table("traffic_readings").select("id", count="exact").execute()
        total  = result.count if result.count else 0
        return {
            "estado":         "healthy",
            "timestamp":      datetime.utcnow().isoformat(),
            "total_lecturas": total,
            "base_de_datos":  "Supabase conectada",
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Base de datos no disponible: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# POST /readings - recibe datos del sensor
# ─────────────────────────────────────────────────────────────
@app.post("/readings", status_code=201)
def recibir_lectura(lectura: SensorReading):
    try:
        sb = get_supabase()

        datos = {
            "intersection_id":   lectura.intersection_id,
            "intersection_name": lectura.intersection_name,
            "lat":               lectura.lat,
            "lon":               lectura.lon,
            "timestamp":         lectura.timestamp,
            "vehicles_count":    lectura.vehicles_count,
            "avg_speed_kmh":     lectura.avg_speed_kmh,
            "congestion_level":  lectura.congestion_level,
            "incident_flag":     lectura.incident_flag,
            "incident_detail":   lectura.incident_detail,
            "weather":           lectura.weather,
            "hour_of_day":       lectura.hour_of_day,
            "day_of_week":       lectura.day_of_week,
            "is_peak_hour":      lectura.is_peak_hour,
            "historical_avg":    lectura.historical_avg,
        }

        result = sb.table("traffic_readings").insert(datos).execute()
        registro_id = result.data[0]["id"] if result.data else None

        print(f"[{lectura.intersection_id}] Lectura #{registro_id} guardada "
              f"- {lectura.congestion_level.upper()} "
              f"| {lectura.avg_speed_kmh} km/h")

        # Llamar al microservicio de prediccion
        if registro_id:
            llamar_prediccion(registro_id, lectura)

        return {
            "mensaje":         "Lectura guardada en Supabase",
            "id":              registro_id,
            "intersection_id": lectura.intersection_id,
            "congestion":      lectura.congestion_level,
            "timestamp":       lectura.timestamp,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando lectura: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# GET /readings/{intersection_id} - ultimas lecturas
# ─────────────────────────────────────────────────────────────
@app.get("/readings/{intersection_id}")
def obtener_lecturas(intersection_id: str, limite: int = 10):
    try:
        sb = get_supabase()
        result = (
            sb.table("traffic_readings")
            .select("id, timestamp, vehicles_count, avg_speed_kmh, congestion_level, incident_flag, weather")
            .eq("intersection_id", intersection_id)
            .order("created_at", desc=True)
            .limit(limite)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No hay lecturas para {intersection_id}"
            )

        return {
            "intersection_id": intersection_id,
            "total":           len(result.data),
            "lecturas":        result.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando lecturas: {str(e)}"
        )