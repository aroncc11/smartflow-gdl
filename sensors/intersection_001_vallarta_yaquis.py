# intersection_001_vallarta_yaquis.py
# Simulador de Sensor — Av. Vallarta — Av. Yaquis
# Sistema Inteligente de Tráfico GDL 2026
# Universidad de Guadalajara / CUCEI

from sensor_base import SensorBase

sensor = SensorBase({
    "id":              "INT-001",
    "nombre":          "Av. Vallarta — Av. Yaquis",
    "lat":             20.6743,
    "lon":            -103.3937,
    "volumen_pico":    3500,
    "volumen_normal":  1800,
    "velocidad_libre": 50,
})

if __name__ == "__main__":
    sensor.ejecutar()
