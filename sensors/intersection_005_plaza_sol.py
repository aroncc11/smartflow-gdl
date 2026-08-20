# intersection_005_plaza_sol.py
# Simulador de Sensor — Av. López Mateos Sur — Mariano Otero
# Sistema Inteligente de Tráfico GDL 2026
# Universidad de Guadalajara / CUCEI

from sensor_base import SensorBase

sensor = SensorBase({
    "id":              "INT-005",
    "nombre":          "Av. López Mateos Sur — Mariano Otero",
    "lat":             20.6475138,
    "lon":            -103.4048619,
    "volumen_pico":    3200,
    "volumen_normal":  1600,
    "velocidad_libre": 55,
})

if __name__ == "__main__":
    sensor.ejecutar()
