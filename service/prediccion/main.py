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
from supabase import create_client, Client

# ─────────────────────────────────────────────────────────────
# CONEXION A SUPABASE
# ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ipcunenaytijdproskxf.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_tUdmn3h_fIx9zERQweNTyA_HYqThsb4")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────────────────────────
# URL MICROSERVICIO OPTIMIZACION
# ─────────────────────────────────────────────────────────────
OPTIMIZACION_URL = os.getenv("OPTIMIZACION_URL", "http://localhost:8003")

# ─────────────────────────────────────────────────────────────
# PREDICTOR Y ESTADO
# ─────────────────────────────────────────────────────────────
predictor = None
predicciones_actuales = {}


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
    }


# ─────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    try:
        result = supabase.table("predictions").select("id", count="exact").execute()
        total  = result.count if result.count else 0
        return {
            "estado":             "healthy",
            "timestamp":          datetime.utcnow().isoformat(),
            "modelo":             "Random Forest cargado",
            "total_predicciones": total,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ─────────────────────────────────────────────────────────────
# POST /predict
# ─────────────────────────────────────────────────────────────
@app.post("/predict", status_code=201)
def predecir(lectura: LecturaInput):
    global predicciones_actuales
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

        # Guardar prediccion actual y llamar optimizador si tenemos las 5
        predicciones_actuales[lectura.intersection_id] = resultado["congestion_level"]

        if len(predicciones_actuales) == 5:
            niveles = [
                predicciones_actuales.get(f"INT-00{i}", "medium")
                for i in range(1, 6)
            ]
            llamar_optimizacion(niveles)

        return {
            "id":               registro_id,
            "intersection_id":  lectura.intersection_id,
            "congestion_level": resultado["congestion_level"],
            "confidence":       resultado["confidence"],
            "probabilities":    resultado["probabilities"],
            "predicted_at":     datos["predicted_at"],
        }

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
            "predicciones":    result.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
