# database.py
# Conexion a Supabase (PostgreSQL en nube)
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI

from sqlalchemy import (
    create_engine, Column, Integer, Float,
    String, Boolean, DateTime
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# CONEXION A SUPABASE
# ─────────────────────────────────────────────────────────────
# AHORA

DATABASE_URL = "postgresql+pg8000://postgres:sMARTFLOWgdl@db.ipcunenaytijdproskxf.supabase.co:5432/postgres"
engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()


# ─────────────────────────────────────────────────────────────
# TABLA traffic_readings
# ─────────────────────────────────────────────────────────────
class TrafficReadingDB(Base):
    __tablename__ = "traffic_readings"

    id               = Column(Integer, primary_key=True, index=True)
    intersection_id  = Column(String(10), nullable=False)
    intersection_name= Column(String(100))
    lat              = Column(Float)
    lon              = Column(Float)
    timestamp        = Column(DateTime)
    vehicles_count   = Column(Integer)
    avg_speed_kmh    = Column(Float)
    congestion_level = Column(String(10))
    incident_flag    = Column(Boolean, default=False)
    incident_detail  = Column(String(200), nullable=True)
    weather          = Column(String(20))
    hour_of_day      = Column(Integer)
    day_of_week      = Column(Integer)
    is_peak_hour     = Column(Boolean)
    historical_avg   = Column(Float)
    created_at       = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
# CREAR TABLAS SI NO EXISTEN
# ─────────────────────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────
# SESION DE BASE DE DATOS
# ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()