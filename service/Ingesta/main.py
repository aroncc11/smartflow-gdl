# main.py
# Microservicio de Prediccion IA - SmartFlow GDL 2026
# Universidad de Guadalajara / CUCEI
# Puerto: 8002

import logging
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from predictor import Predictor
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import httpx

logging.basicConfig(level=logging.INFO)


def llamar_optimizacion(niveles: list):
    """
    Cuando se tienen predicciones de las 5 intersecciones
    llama al AG para optimizar semaforos.
    """
    try:
        httpx.post(
            "http://localhost:8003/optimize",
            json={"niveles_congestion": niveles},
            timeout=30
        )
    except Exception:
        logging.exception("Error al llamar al servicio de optimizacion")


# ─────────────────────────────────────────────────────────────
# CONEXION A SUPABASE
# ─────────────────────────────────────────────────────────────
DATABASE_URL = "postgresql+psycopg2://postgres:sMARTFLOWgdl@db.ipcunenaytijdproskxf.supabase.co:5432/postgres"


engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()

# ─────────────────────────────────────────────────────────────
# TABLA PREDICTIONS EN SUPABASE
# ─────────────────────────────────────────────────────────────
class PredictionDB(Base):
    __tablename__ = "predictions"

    id               = Column(Integer, primary_key=True, index=True)
    intersection_id  = Column(String(10), nullable=False)
    reading_id       = Column(BigInteger, nullable=True)
    congestion_level = Column(String(10))
    confidence       = Column(Float)
    prob_low         = Column(Float)
    prob_medium      = Column(Float)
    prob_high        = Column(Float)
    predicted_at     = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────
# INICIALIZAR APP Y MODELO
# ─────────────────────────────────────────────────────────────
app       = FastAPI(
    title="SmartFlow GDL - Microservicio de Prediccion IA",
    description="Predice nivel de congestion vehicular usando Random Forest",
    version="1.0.0"
)
predictor = None
predicciones_actuales = {}


@app.on_event("startup")
def startup():
    global predictor
    init_db()
    predictor = Predictor()
    logging.info("Microservicio de Prediccion IA listo en :8002")


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

    class Config:
        json_schema_extra = {
            "example": {
                "intersection_id": "INT-001",
                "reading_id":      1234,
                "vehicles_count":  25,
                "avg_speed_kmh":   14.8,
                "hour_of_day":     8,
                "day_of_week":     0,
                "is_peak_hour":    True,
                "incident_flag":   False,
                "weather":         "clear",
                "historical_avg":  12.5,
            }
        }


# ─────────────────────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "servicio": "prediccion",
        "proyecto": "SmartFlow GDL",
        "estado":   "activo",
        "puerto":   8002,
        "modelo":   "Random Forest",
    }


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/health")
def health():
    try:
        db    = SessionLocal()
        total = db.query(PredictionDB).count()
        db.close()
        return {
            "estado":           "healthy",
            "timestamp":        datetime.utcnow().isoformat(),
            "modelo":           "Random Forest cargado",
            "total_predicciones": total,
        }
    except Exception as e:
        logging.exception("Error en /health")
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/predict", status_code=201)
def predecir(lectura: LecturaInput):
    """
    Recibe datos de una lectura de sensor y predice
    el nivel de congestion usando el modelo Random Forest.
    """
    try:
        # Realizar prediccion
        resultado = predictor.predecir(lectura.dict())

        # Guardar prediccion en Supabase
        db = SessionLocal()
        registro = PredictionDB(
            intersection_id  = lectura.intersection_id,
            reading_id       = lectura.reading_id,
            congestion_level = resultado["congestion_level"],
            confidence       = resultado["confidence"],
            prob_low         = resultado["probabilities"].get("low", 0),
            prob_medium      = resultado["probabilities"].get("medium", 0),
            prob_high        = resultado["probabilities"].get("high", 0),
            predicted_at     = datetime.utcnow(),
        )
        db.add(registro)
        db.commit()
        db.refresh(registro)
        db.close()

        logging.info(
            "[%s] Prediccion #%s - %s | Confianza: %.2f%%",
            lectura.intersection_id,
            registro.id,
            resultado["congestion_level"].upper(),
            resultado["confidence"] * 100,
        )

        # Guardar prediccion actual
        predicciones_actuales[lectura.intersection_id] = resultado["congestion_level"]

        # Si tenemos las 5 intersecciones llamar al optimizador
        if len(predicciones_actuales) == 5:
            niveles = [
                predicciones_actuales.get(f"INT-00{i}", "medium")
                for i in range(1, 6)
            ]
            llamar_optimizacion(niveles)

        return {
            "id":               registro.id,
            "intersection_id":  lectura.intersection_id,
            "congestion_level": resultado["congestion_level"],
            "confidence":       resultado["confidence"],
            "probabilities":    resultado["probabilities"],
            "predicted_at":     registro.predicted_at.isoformat(),
        }

    except Exception as e:
        logging.exception("Error en /predict")
        raise HTTPException(
            status_code=500,
            detail=f"Error en prediccion: {str(e)}"
        )


@app.get("/predict/{intersection_id}")
def obtener_predicciones(intersection_id: str, limite: int = 10):
    """
    Devuelve las ultimas N predicciones de una interseccion.
    Util para el dashboard y analisis de tendencias.
    """
    try:
        db = SessionLocal()
        predicciones = (
            db.query(PredictionDB)
            .filter(PredictionDB.intersection_id == intersection_id)
            .order_by(PredictionDB.predicted_at.desc())
            .limit(limite)
            .all()
        )
        db.close()

        if not predicciones:
            raise HTTPException(
                status_code=404,
                detail=f"No hay predicciones para {intersection_id}"
            )

        return {
            "intersection_id": intersection_id,
            "total":           len(predicciones),
            "predicciones": [
                {
                    "id":               p.id,
                    "congestion_level": p.congestion_level,
                    "confidence":       p.confidence,
                    "prob_low":         p.prob_low,
                    "prob_medium":      p.prob_medium,
                    "prob_high":        p.prob_high,
                    "predicted_at":     str(p.predicted_at),
                }
                for p in predicciones
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error en /predict/{intersection_id}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=True)