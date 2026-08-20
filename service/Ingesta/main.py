# main.py
# Microservicio de Ingesta - SmartFlow GDL 2026
# Universidad de Guadalajara / CUCEI
# Puerto: 8001

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from models import SensorReading
from database import TrafficReadingDB, get_db, init_db

# ─────────────────────────────────────────────────────────────
# INICIALIZAR APP
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartFlow GDL - Microservicio de Ingesta",
    description="Recibe y persiste lecturas de sensores de trafico urbano",
    version="1.0.0"
)

@app.on_event("startup")
def startup():
    init_db()
    print("Base de datos Supabase inicializada")


# ─────────────────────────────────────────────────────────────
# GET / - verificacion rapida
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "servicio": "ingesta",
        "proyecto": "SmartFlow GDL",
        "estado":   "activo",
        "puerto":   8001,
    }


# ─────────────────────────────────────────────────────────────
# GET /health - estado detallado
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        total = db.query(TrafficReadingDB).count()
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
def recibir_lectura(
    lectura: SensorReading,
    db: Session = Depends(get_db)
):
    try:
        registro = TrafficReadingDB(
            intersection_id   = lectura.intersection_id,
            intersection_name = lectura.intersection_name,
            lat               = lectura.lat,
            lon               = lectura.lon,
            timestamp         = datetime.fromisoformat(lectura.timestamp),
            vehicles_count    = lectura.vehicles_count,
            avg_speed_kmh     = lectura.avg_speed_kmh,
            congestion_level  = lectura.congestion_level,
            incident_flag     = lectura.incident_flag,
            incident_detail   = lectura.incident_detail,
            weather           = lectura.weather,
            hour_of_day       = lectura.hour_of_day,
            day_of_week       = lectura.day_of_week,
            is_peak_hour      = lectura.is_peak_hour,
            historical_avg    = lectura.historical_avg,
        )

        db.add(registro)
        db.commit()
        db.refresh(registro)

        print(f"[{lectura.intersection_id}] Lectura #{registro.id} guardada "
              f"- {lectura.congestion_level.upper()} "
              f"| {lectura.avg_speed_kmh} km/h")

        return {
            "mensaje":         "Lectura guardada en Supabase",
            "id":              registro.id,
            "intersection_id": lectura.intersection_id,
            "congestion":      lectura.congestion_level,
            "timestamp":       lectura.timestamp,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando lectura: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# GET /readings/{intersection_id} - ultimas lecturas
# ─────────────────────────────────────────────────────────────
@app.get("/readings/{intersection_id}")
def obtener_lecturas(
    intersection_id: str,
    limite: int = 10,
    db: Session = Depends(get_db)
):
    lecturas = (
        db.query(TrafficReadingDB)
        .filter(TrafficReadingDB.intersection_id == intersection_id)
        .order_by(TrafficReadingDB.created_at.desc())
        .limit(limite)
        .all()
    )

    if not lecturas:
        raise HTTPException(
            status_code=404,
            detail=f"No hay lecturas para {intersection_id}"
        )

    return {
        "intersection_id": intersection_id,
        "total":           len(lecturas),
        "lecturas": [
            {
                "id":               l.id,
                "timestamp":        str(l.timestamp),
                "vehicles_count":   l.vehicles_count,
                "avg_speed_kmh":    l.avg_speed_kmh,
                "congestion_level": l.congestion_level,
                "incident_flag":    l.incident_flag,
                "weather":          l.weather,
            }
            for l in lecturas
        ]
    }