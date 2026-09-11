# run_all_sensors.py
# Corre los 5 sensores simultaneamente usando threads
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI
# Este archivo se usa para despliegue en Railway
 
import threading
import os
from sensor_base import SensorBase
 
# URL del microservicio de ingesta en Railway
# Se puede sobreescribir con variable de entorno
INGESTA_URL = os.getenv(
    "INGESTA_URL",
    "https://smartflow-gdl-production.up.railway.app/readings"
)
 
# Sobreescribir la URL en sensor_base
import sensor_base
sensor_base.INGESTA_URL = INGESTA_URL
 
# ─────────────────────────────────────────────────────────────
# CONFIGURACION DE LAS 5 INTERSECCIONES
# ─────────────────────────────────────────────────────────────
INTERSECCIONES = [
    {
        "id":              "INT-001",
        "nombre":          "Av. Vallarta - Av. Yaquis",
        "lat":             20.6743,
        "lon":            -103.3937,
        "volumen_pico":    3500,
        "volumen_normal":  1800,
        "velocidad_libre": 50,
    },
    {
        "id":              "INT-002",
        "nombre":          "Av. Lopez Mateos - Av. de las Americas",
        "lat":             20.6963551,
        "lon":            -103.3734237,
        "volumen_pico":    2800,
        "volumen_normal":  1400,
        "velocidad_libre": 28,
    },
    {
        "id":              "INT-003",
        "nombre":          "Av. Guadalupe - San Ignacio",
        "lat":             20.6706347,
        "lon":            -103.4050178,
        "volumen_pico":    2100,
        "volumen_normal":  1050,
        "velocidad_libre": 45,
    },
    {
        "id":              "INT-004",
        "nombre":          "Av. Vallarta - Ninos Heroes",
        "lat":             20.6668608,
        "lon":            -103.3689243,
        "volumen_pico":    2400,
        "volumen_normal":  1200,
        "velocidad_libre": 25,
    },
    {
        "id":              "INT-005",
        "nombre":          "Av. Lopez Mateos Sur - Mariano Otero",
        "lat":             20.6475138,
        "lon":            -103.4048619,
        "volumen_pico":    3200,
        "volumen_normal":  1600,
        "velocidad_libre": 55,
    },
]
 
 
def correr_sensor(config: dict):
    """Corre un sensor en su propio thread."""
    sensor = SensorBase(config)
    sensor.ejecutar()
 
 
if __name__ == "__main__":
    print("=" * 55)
    print("  SmartFlow GDL - Iniciando 5 sensores")
    print(f"  Enviando a: {INGESTA_URL}")
    print("=" * 55)
 
    threads = []
    for config in INTERSECCIONES:
        t = threading.Thread(
            target=correr_sensor,
            args=(config,),
            daemon=True,
            name=f"sensor-{config['id']}"
        )
        threads.append(t)
        t.start()
        print(f"Sensor {config['id']} iniciado en thread {t.name}")
 
    print("\nTodos los sensores corriendo. Ctrl+C para detener.")
 
    # Mantener el proceso principal vivo
    for t in threads:
        t.join()