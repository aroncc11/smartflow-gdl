"""
Experimento real: mide la reduccion de tiempo de espera que produce el
Algoritmo Genetico desplegado en Railway, usando la propia metrica que el
sistema ya calcula (mejora_porcentaje / ahorro_seg por interseccion),
ponderada por volumen_pico (igual que la funcion de fitness real).

N=30 corridas con escenarios de congestion variados (semilla fija para
reproducibilidad). Imprime el resultado y lo guarda en resultados_ga.json.

Uso:
    pip install requests
    python experimento_ga_real.py
"""
import requests
import json
import random
import statistics as st

URL = "https://servicio-de-optimizacion-production.up.railway.app/optimize"

# Mismos volumenes que genetic_algorithm.py (INTERSECCIONES), en el mismo orden
VOLUMENES = {
    "INT-001": 3500,
    "INT-002": 2800,
    "INT-003": 2100,
    "INT-004": 2400,
    "INT-005": 3200,
}
IDS = list(VOLUMENES.keys())

N_CORRIDAS = 30
SEMILLA = 42
NIVELES = ["low", "medium", "high"]

random.seed(SEMILLA)

resultados = []

for corrida in range(1, N_CORRIDAS + 1):
    niveles_congestion = [random.choice(NIVELES) for _ in IDS]

    resp = requests.post(URL, json={"niveles_congestion": niveles_congestion}, timeout=60)

    if resp.status_code != 201:
        print(f"[Corrida {corrida}] ERROR {resp.status_code}: {resp.text}")
        continue

    data = resp.json()
    tiempos = data["tiempos_optimos"]

    # Promedio ponderado por volumen de mejora_porcentaje (misma ponderacion
    # que usa calcular_fitness en genetic_algorithm.py)
    suma_ponderada = 0
    suma_volumen   = 0
    ahorro_total_seg = 0
    for int_id, t in tiempos.items():
        vol = VOLUMENES[int_id]
        suma_ponderada += t["mejora_porcentaje"] * vol
        suma_volumen   += vol
        ahorro_total_seg += t["ahorro_seg"]

    mejora_ponderada = suma_ponderada / suma_volumen

    registro = {
        "corrida": corrida,
        "niveles_congestion": niveles_congestion,
        "duracion_seg_ga": data["duracion_seg"],
        "fitness": data["fitness"],
        "mejora_ponderada_pct": round(mejora_ponderada, 2),
        "ahorro_total_seg_5_intersecciones": round(ahorro_total_seg, 2),
        "detalle_por_interseccion": {
            k: {"mejora_porcentaje": v["mejora_porcentaje"], "ahorro_seg": v["ahorro_seg"]}
            for k, v in tiempos.items()
        },
    }
    resultados.append(registro)
    print(f"[Corrida {corrida}/{N_CORRIDAS}] niveles={niveles_congestion} "
          f"-> mejora ponderada={mejora_ponderada:.2f}%  "
          f"(AG tardo {data['duracion_seg']}s)")

# ─────────────────────────────────────────────────────────────
# RESUMEN ESTADISTICO
# ─────────────────────────────────────────────────────────────
mejoras = [r["mejora_ponderada_pct"] for r in resultados]
n = len(mejoras)

print("\n" + "=" * 60)
print(f"  RESUMEN — {n} corridas exitosas de {N_CORRIDAS} intentadas")
print("=" * 60)
if n > 0:
    media = st.mean(mejoras)
    print(f"  Media de reduccion de tiempo de espera (ponderada):  {media:.2f}%")
    if n > 1:
        desv = st.stdev(mejoras)
        # Intervalo de confianza 95% aproximado (t de Student, n-1 gl)
        # Para n=30, t_0.975,29 ~= 2.045
        t_critico = 2.045 if n >= 28 else 2.1  # aproximacion razonable
        margen = t_critico * desv / (n ** 0.5)
        print(f"  Desviacion estandar:                                  {desv:.2f}")
        print(f"  Intervalo de confianza 95%:                           [{media - margen:.2f}%, {media + margen:.2f}%]")
    print(f"  Minimo / Maximo observado:                            {min(mejoras):.2f}% / {max(mejoras):.2f}%")

with open("resultados_ga.json", "w", encoding="utf-8") as f:
    json.dump(resultados, f, indent=2, ensure_ascii=False)

print("\nResultados completos guardados en resultados_ga.json")
print("Pega aqui el resumen de arriba (y si puedes, el archivo .json) para meterlo al informe.")
