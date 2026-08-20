# intersection_003_guadalupe.py
# Simulador de Sensor — Av. Guadalupe — San Ignacio
# Sistema Inteligente de Tráfico GDL 2026
# Universidad de Guadalajara / CUCEI

from sensor_base import SensorBase

sensor = SensorBase({
    "id":              "INT-003",
    "nombre":          "Av. Guadalupe — San Ignacio",
    "lat":             20.6706347,
    "lon":            -103.4050178,
    "volumen_pico":    2100,
    "volumen_normal":  1050,
    "velocidad_libre": 45,
})

if __name__ == "__main__":
    sensor.ejecutar()
