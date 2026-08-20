# intersection_002_lopez.py
# Simulador de Sensor — Av. López Mateos — Av. de las Américas
# Sistema Inteligente de Tráfico GDL 2026
# Universidad de Guadalajara / CUCEI

from sensor_base import SensorBase

sensor = SensorBase({
    "id":              "INT-002",
    "nombre":          "Av. López Mateos — Av. de las Américas",
    "lat":             20.6963551,
    "lon":            -103.3734237,
    "volumen_pico":    2800,
    "volumen_normal":  1400,
    "velocidad_libre": 60,
})

if __name__ == "__main__":
    sensor.ejecutar()
