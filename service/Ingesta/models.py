# models.py
# Validacion de datos con Pydantic
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI

from pydantic import BaseModel, Field
from typing import Optional

class SensorReading(BaseModel):
    """
    Estructura exacta que debe enviar cada sensor.
    Pydantic valida automaticamente tipos y campos requeridos.
    """
    intersection_id:   str   = Field(..., example="INT-001")
    intersection_name: str   = Field(..., example="Av. Vallarta - Av. Yaquis")
    lat:               float = Field(..., example=20.6743)
    lon:               float = Field(..., example=-103.3937)
    timestamp:         str   = Field(..., example="2026-08-11T00:10:56")
    vehicles_count:    int   = Field(..., ge=0)
    avg_speed_kmh:     float = Field(..., ge=0.0)
    congestion_level:  str   = Field(..., pattern="^(low|medium|high)$")
    incident_flag:     bool
    incident_detail:   Optional[str] = None
    weather:           str   = Field(..., pattern="^(clear|cloudy|rain|heavy_rain)$")
    hour_of_day:       int   = Field(..., ge=0, le=23)
    day_of_week:       int   = Field(..., ge=0, le=6)
    is_peak_hour:      bool
    historical_avg:    float = Field(..., ge=0.0)

    class Config:
        json_schema_extra = {
            "example": {
                "intersection_id":   "INT-001",
                "intersection_name": "Av. Vallarta - Av. Yaquis",
                "lat":               20.6743,
                "lon":              -103.3937,
                "timestamp":         "2026-08-11T00:10:56",
                "vehicles_count":    2,
                "avg_speed_kmh":     44.0,
                "congestion_level":  "low",
                "incident_flag":     False,
                "incident_detail":   None,
                "weather":           "clear",
                "hour_of_day":       0,
                "day_of_week":       0,
                "is_peak_hour":      False,
                "historical_avg":    0.75,
            }
        }