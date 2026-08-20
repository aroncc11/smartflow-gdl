# intersection_004_vallarta.py
# Simulador de Sensor — Av. Vallarta — Niños Héroes
# Sistema Inteligente de Tráfico GDL 2026
# Universidad de Guadalajara / CUCEI

from sensor_base import SensorBase

sensor = SensorBase({
    "id":              "INT-004",
    "nombre":          "Av. Vallarta — Niños Héroes",
    "lat":             20.6668608,
    "lon":            -103.3689243,
    "volumen_pico":    2400,
    "volumen_normal":  1200,
    "velocidad_libre": 50,
})

if __name__ == "__main__":
    sensor.ejecutar()
