# tomtom_calibrar.py
# Calibración del simulador con datos reales de TomTom Traffic API
# SmartFlow GDL 2026 — Universidad de Guadalajara / CUCEI
#
# Instrucciones:
# 1. Pegar tu API Key de TomTom en la variable API_KEY
# 2. Correr: python tomtom_calibrar.py
# 3. Si alguna intersección marca ajustar velocidad_libre en sensor_base.py

import requests 
import json
from datetime import datetime
from sensor_base import SensorBase

# ─────────────────────────────────────────────────────────────
# PEGA TU API KEY DE TOMTOM AQUÍ
# ─────────────────────────────────────────────────────────────
API_KEY = "mYRWE4xG0uEDO85EQPMUeDb9C634u5dU"

# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE INTERSECCIONES
# Coordenadas verificadas en Google Maps Street View
# ─────────────────────────────────────────────────────────────
INTERSECCIONES_CONFIG = [
    {
        "id":              "INT-001",
        "nombre":          "Av. Vallarta — Av. Yaquis",
        "lat":             20.6743,
        "lon":            -103.3937,
        "volumen_pico":    3500,
        "volumen_normal":  1800,
        "velocidad_libre": 50,
    },
    {
        "id":              "INT-002",
        "nombre":          "Av. López Mateos — Av. de las Américas",
        "lat":             20.6963551,
        "lon":            -103.3734237,
        "volumen_pico":    2800,
        "volumen_normal":  1400,
        "velocidad_libre": 60,
    },
    {
        "id":              "INT-003",
        "nombre":          "Av. Guadalupe — San Ignacio",
        "lat":             20.6706347,
        "lon":            -103.4050178,
        "volumen_pico":    2100,
        "volumen_normal":  1050,
        "velocidad_libre": 45,
    },
    {
        "id":              "INT-004",
        "nombre":          "Av. Vallarta — Niños Héroes",
        "lat":             20.6668608,
        "lon":            -103.3689243,
        "volumen_pico":    2400,
        "volumen_normal":  1200,
        "velocidad_libre": 50,
    },
    {
        "id":              "INT-005",
        "nombre":          "Av. López Mateos Sur — Mariano Otero",
        "lat":             20.6475138,
        "lon":            -103.4048619,
        "volumen_pico":    3200,
        "volumen_normal":  1600,
        "velocidad_libre": 55,
    },
]


def obtener_trafico_real(lat: float, lon: float) -> dict:
    """
    Consulta Traffic Flow API de TomTom.
    Devuelve velocidad actual y velocidad libre para las coordenadas dadas.
    """
    url = (
        f"https://api.tomtom.com/traffic/services/4/"
        f"flowSegmentData/absolute/10/json"
        f"?point={lat},{lon}"
        f"&key={API_KEY}"
    )
    response = requests.get(url, timeout=10)
    return response.json()


def comparar():
    print("\n" + "=" * 65)
    print(f"  SmartFlow GDL — Calibración TomTom")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 65)

    ajustes_necesarios = []

    for config in INTERSECCIONES_CONFIG:
        print(f"\n[{config['id']}] {config['nombre']}")
        print(f"  Coords: ({config['lat']}, {config['lon']})")

        try:
            # ── Dato real de TomTom ────────────────────────
            data         = obtener_trafico_real(config["lat"], config["lon"])
            flow         = data.get("flowSegmentData", {})
            vel_real     = flow.get("currentSpeed", 0)
            vel_libre_tt = flow.get("freeFlowSpeed", 0)
            confianza    = flow.get("confidence", 0)

            # ── Dato del simulador ─────────────────────────
            sensor  = SensorBase(config)
            lectura = sensor.generate_reading()
            vel_sim = lectura["avg_speed_kmh"]

            # ── Comparación ────────────────────────────────
            diff  = vel_sim - vel_real
            match = abs(diff) <= 10

            print(f"  TomTom real:    {vel_real} km/h  "
                  f"(velocidad libre: {vel_libre_tt} km/h, "
                  f"confianza: {round(confianza*100)}%)")
            print(f"  Simulador:      {vel_sim} km/h")
            print(f"  Diferencia:     {diff:+.1f} km/h  "
                  f"{'OK' if match else 'Requiere ajuste'}")

            # ── Sugerir ajuste si es necesario ────────────
            if not match:
                nueva_vel = round(vel_libre_tt * 0.95)
                print(f" Cambiar velocidad_libre de "
                      f"{config['velocidad_libre']} a {nueva_vel} km/h")
                ajustes_necesarios.append({
                    "id":        config["id"],
                    "nombre":    config["nombre"],
                    "actual":    config["velocidad_libre"],
                    "sugerido":  nueva_vel,
                })

        except Exception as e:
            print(f" Error consultando TomTom: {e}")

    # ── Resumen final ──────────────────────────────────────
    print("\n" + "=" * 65)
    if ajustes_necesarios:
        print("  AJUSTES NECESARIOS EN sensor_base.py:")
        print("-" * 65)
        for a in ajustes_necesarios:
            print(f"  [{a['id']}] {a['nombre']}")
            print(f"    velocidad_libre: {a['actual']} → {a['sugerido']} km/h")
    else:
        print("Todos los sensores están bien calibrados.")
    print("=" * 65)

    # Guardar resultados en JSON
    with open("calibracion_resultado.json", "w", encoding="utf-8") as f:
        json.dump({
            "fecha":    datetime.now().isoformat(),
            "ajustes":  ajustes_necesarios,
        }, f, ensure_ascii=False, indent=2)
    print("\n Resultados guardados en calibracion_resultado.json")

def aplicar_ajustes():
    import re
    import os

    with open("calibracion_resultado.json", "r", encoding="utf-8") as f:
        resultado = json.load(f)

    ajustes = resultado.get("ajustes", [])

    if not ajustes:
        print("No hay ajustes necesarios.")
        return

    archivos = {
        "INT-001": "intersection_001_vallarta_yaquis.py",
        "INT-002": "intersection_002_lopez.py",
        "INT-003": "intersection_003_guadalupe.py",
        "INT-004": "intersection_004_vallarta.py",
        "INT-005": "intersection_005_plaza_sol.py",
    }

    for ajuste in ajustes:
        int_id   = ajuste["id"]
        nuevo    = ajuste["sugerido"]
        archivo  = archivos.get(int_id)

        if not archivo or not os.path.exists(archivo):
            print(f"[{int_id}] Archivo no encontrado: {archivo}")
            continue

        with open(archivo, "r", encoding="utf-8") as f:
            contenido = f.read()

        contenido_nuevo = re.sub(
            r'"velocidad_libre":\s*\d+',
            f'"velocidad_libre": {nuevo}',
            contenido
        )

        with open(archivo, "w", encoding="utf-8") as f:
            f.write(contenido_nuevo)

        print(f"[{int_id}] {archivo} actualizado -> velocidad_libre: {nuevo} km/h")

    print("\nAjustes aplicados. Vuelve a correr tomtom_calibrar.py para verificar.")

if __name__ == "__main__":
    if API_KEY == "mYRWE4xG0uEDO85EQPMUeDb9C634u5dU":
        print("ERROR: Debes pegar tu API Key de TomTom en la variable API_KEY")
       
    
else:
        comparar()
        print("\nAplicando ajustes automaticamente...")
        aplicar_ajustes()