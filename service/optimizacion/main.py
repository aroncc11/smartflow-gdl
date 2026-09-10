# main.py
# Microservicio de Optimizacion GA - SmartFlow GDL 2026
# Universidad de Guadalajara / CUCEI
# Puerto: 8003

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from genetic_algorithm import optimizar_semaforos, INTERSECCIONES

# ─────────────────────────────────────────────────────────────
# CONEXION A SUPABASE
# ─────────────────────────────────────────────────────────────
DATABASE_URL = "postgresql+psycopg2://postgres:sMARTFLOWgdl@db.ipcunenaytijdproskxf.supabase.co:5432/postgres"

engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()


# ─────────────────────────────────────────────────────────────
# TABLA traffic_lights EN SUPABASE
# ─────────────────────────────────────────────────────────────
class TrafficLightDB(Base):
    __tablename__ = "traffic_lights"

    id               = Column(Integer, primary_key=True, index=True)
    intersection_id  = Column(String(10), nullable=False)
    intersection_name= Column(String(100))
    congestion_level = Column(String(10))
    verde_default    = Column(Integer, default=45)
    verde_optimo     = Column(Integer)
    rojo_optimo      = Column(Integer)
    amarillo         = Column(Integer, default=3)
    fitness          = Column(Float)
    optimized_at     = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────
# INICIALIZAR APP
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartFlow GDL - Microservicio de Optimizacion GA",
    description="Optimiza tiempos de semaforo usando Algoritmo Genetico (DEAP)",
    version="1.0.0"
)

@app.on_event("startup")
def startup():
    init_db()
    print("Microservicio de Optimizacion GA listo en :8003")


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
# GET / - verificacion rapida
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "servicio":    "optimizacion",
        "proyecto":    "SmartFlow GDL",
        "estado":      "activo",
        "puerto":      8003,
        "algoritmo":   "Algoritmo Genetico DEAP",
        "parametros": {
            "poblacion":     100,
            "generaciones":  50,
            "cruzamiento":   0.85,
            "mutacion":      0.15,
        }
    }


# ─────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    try:
        db    = SessionLocal()
        total = db.query(TrafficLightDB).count()
        db.close()
        return {
            "estado":             "healthy",
            "timestamp":          datetime.utcnow().isoformat(),
            "total_optimizaciones": total,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ─────────────────────────────────────────────────────────────
# POST /optimize - ejecuta el AG y retorna tiempos optimos
# ─────────────────────────────────────────────────────────────
@app.post("/optimize", status_code=201)
def optimizar(datos: OptimizacionInput):
    """
    Recibe los niveles de congestion actuales de las 5 intersecciones
    y ejecuta el Algoritmo Genetico para calcular los tiempos optimos
    de fase verde en cada semaforo.
    """
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
                detail=f"Nivel invalido: {nivel}. Use low, medium o high"
            )

    try:
        print(f"\nEjecutando AG con niveles: {datos.niveles_congestion}")
        inicio = datetime.utcnow()

        # Ejecutar Algoritmo Genetico
        resultado = optimizar_semaforos(datos.niveles_congestion)

        duracion = (datetime.utcnow() - inicio).total_seconds()
        print(f"AG completado en {duracion:.2f}s | Fitness: {resultado['fitness']:.2f}")

        # Guardar en Supabase
        db = SessionLocal()
        for int_id, tiempos in resultado["tiempos_optimos"].items():
            registro = TrafficLightDB(
                intersection_id   = int_id,
                intersection_name = tiempos["nombre"],
                congestion_level  = tiempos["congestion"],
                verde_default     = tiempos["verde_default"],
                verde_optimo      = tiempos["verde_optimo"],
                rojo_optimo       = tiempos["rojo_optimo"],
                amarillo          = tiempos["amarillo"],
                fitness           = resultado["fitness"],
                optimized_at      = datetime.utcnow(),
            )
            db.add(registro)

        db.commit()
        db.close()

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
# GET /optimize/latest - ultima optimizacion
# ─────────────────────────────────────────────────────────────
@app.get("/optimize/latest")
def ultima_optimizacion():
    """
    Devuelve la ultima optimizacion realizada para cada interseccion.
    Usado por el dashboard para mostrar tiempos actuales.
    """
    db = SessionLocal()

    resultado = {}
    for config in INTERSECCIONES:
        ultimo = (
            db.query(TrafficLightDB)
            .filter(TrafficLightDB.intersection_id == config["id"])
            .order_by(TrafficLightDB.optimized_at.desc())
            .first()
        )
        if ultimo:
            resultado[config["id"]] = {
                "intersection_name": ultimo.intersection_name,
                "congestion_level":  ultimo.congestion_level,
                "verde_default":     ultimo.verde_default,
                "verde_optimo":      ultimo.verde_optimo,
                "rojo_optimo":       ultimo.rojo_optimo,
                "amarillo":          ultimo.amarillo,
                "optimized_at":      str(ultimo.optimized_at),
            }

    db.close()

    if not resultado:
        raise HTTPException(
            status_code=404,
            detail="No hay optimizaciones registradas aun"
        )

    return resultado
