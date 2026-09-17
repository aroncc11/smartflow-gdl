# sensor_base.py
# Clase base para todos los sensores de trafico urbano
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI

from datetime import datetime, timezone, timedelta
import random
import schedule
import time
import requests
import os

# ─────────────────────────────────────────────────────────────
# URL DEL MICROSERVICIO DE INGESTA
# ─────────────────────────────────────────────────────────────
INGESTA_URL = os.getenv(
    "INGESTA_URL",
    "https://smartflow-gdl-production.up.railway.app/readings"
)

# ─────────────────────────────────────────────────────────────
# ZONA HORARIA DE GUADALAJARA (UTC-6)
# ─────────────────────────────────────────────────────────────
GDL_TZ = timezone(timedelta(hours=-6))

# ─────────────────────────────────────────────────────────────
# FACTORES HORARIOS - curva bimodal
# ─────────────────────────────────────────────────────────────
FACTORES_HORA = {
    0: 0.05,  1: 0.04,  2: 0.03,  3: 0.03,
    4: 0.04,  5: 0.10,  6: 0.35,  7: 0.85,
    8: 1.00,  9: 0.80, 10: 0.55, 11: 0.60,
   12: 0.70, 13: 0.65, 14: 0.55, 15: 0.60,
   16: 0.75, 17: 0.90, 18: 0.95, 19: 1.00,
   20: 0.80, 21: 0.55, 22: 0.35, 23: 0.15,
}

FACTORES_DIA = {
    0: 0.95, 1: 1.00, 2: 1.00,
    3: 0.98, 4: 0.95, 5: 0.80, 6: 0.60,
}

FACTORES_VELOCIDAD_CLIMA = {
    "clear": 1.00, "cloudy": 0.95,
    "rain":  0.75, "heavy_rain": 0.55,
}

FACTORES_VOLUMEN_CLIMA = {
    "clear": 1.00, "cloudy": 1.00,
    "rain":  0.85, "heavy_rain": 0.65,
}

TIPOS_INCIDENTE = [
    "Accidente vehicular",
    "Cierre vial por obra",
    "Manifestacion",
    "Vehiculo descompuesto",
    "Evento masivo cercano",
]


class SensorBase:

    def __init__(self, config: dict):
        self.config        = config
        self._incidente    = {"activo": False, "detalle": None}
        self._clima_actual = self._generar_clima()
        self._hora_clima   = datetime.now(GDL_TZ).hour
        print(f"Sensor [{config['id']}] {config['nombre']} iniciado")

    def _generar_clima(self) -> str:
        mes = datetime.now(GDL_TZ).month
        temporada_lluvias = mes in range(5, 11)
        if temporada_lluvias:
            return random.choices(
                ["clear", "cloudy", "rain", "heavy_rain"],
                weights=[0.40, 0.25, 0.25, 0.10]
            )[0]
        else:
            return random.choices(
                ["clear", "cloudy", "rain", "heavy_rain"],
                weights=[0.70, 0.20, 0.09, 0.01]
            )[0]

    def _simular_clima(self) -> str:
        hora_actual = datetime.now(GDL_TZ).hour
        if self._hora_clima != hora_actual:
            self._clima_actual = self._generar_clima()
            self._hora_clima   = hora_actual
        return self._clima_actual

    def _simular_incidente(self, clima: str) -> tuple:
        prob = 0.05 if clima == "heavy_rain" else 0.02
        if self._incidente["activo"]:
            if random.random() < 0.15:
                self._incidente["activo"]  = False
                self._incidente["detalle"] = None
        else:
            if random.random() < prob:
                self._incidente["activo"]  = True
                self._incidente["detalle"] = random.choice(TIPOS_INCIDENTE)
        return self._incidente["activo"], self._incidente["detalle"]

    def _calcular_volumen(self, clima: str, incidente: bool) -> int:
        now  = datetime.now(GDL_TZ)
        hora = now.hour
        dia  = now.weekday()

        factor_hora    = FACTORES_HORA[hora]
        factor_dia     = FACTORES_DIA[dia]
        factor_clima   = FACTORES_VOLUMEN_CLIMA[clima]
        factor_inciden = 1.25 if incidente else 1.0

        base = self.config["volumen_pico"] if factor_hora >= 0.80 \
               else self.config["volumen_normal"]

        vehiculos = (base * factor_hora * factor_dia *
                     factor_clima * factor_inciden) / 120
        vehiculos = vehiculos * random.gauss(1.0, 0.15)

        return max(0, round(vehiculos))

    def _calcular_velocidad(self, vehiculos: int, clima: str) -> float:
        capacidad_30s   = self.config["volumen_pico"] / 120
        ratio           = min(vehiculos / max(capacidad_30s, 1), 1.0)
        velocidad_libre = self.config["velocidad_libre"]
        factor_clima    = FACTORES_VELOCIDAD_CLIMA[clima]

        velocidad = velocidad_libre * (1 - 0.85 * ratio) * factor_clima
        velocidad = velocidad * random.gauss(1.0, 0.15)

        return max(5.0, round(velocidad, 1))

    def _calcular_congestion(self, velocidad: float) -> str:
        if velocidad > 40:
            return random.choices(["low", "medium"], weights=[0.93, 0.07])[0]
        elif velocidad > 35:
            return random.choices(["low", "medium"], weights=[0.80, 0.20])[0]
        elif velocidad > 20:
            return random.choices(["low", "medium", "high"], weights=[0.10, 0.78, 0.12])[0]
        elif velocidad > 15:
            return random.choices(["medium", "high"], weights=[0.75, 0.25])[0]
        else:
            return random.choices(["medium", "high"], weights=[0.12, 0.88])[0]

    def generate_reading(self) -> dict:
        now     = datetime.now(GDL_TZ)
        clima   = self._simular_clima()
        inciden, detalle = self._simular_incidente(clima)

        vehiculos  = self._calcular_volumen(clima, inciden)
        velocidad  = self._calcular_velocidad(vehiculos, clima)
        congestion = self._calcular_congestion(velocidad)

        return {
            "intersection_id":   self.config["id"],
            "intersection_name": self.config["nombre"],
            "lat":               self.config["lat"],
            "lon":               self.config["lon"],
            "timestamp":         now.isoformat(),
            "vehicles_count":    vehiculos,
            "avg_speed_kmh":     velocidad,
            "congestion_level":  congestion,
            "incident_flag":     inciden,
            "incident_detail":   detalle,
            "weather":           clima,
            "hour_of_day":       now.hour,
            "day_of_week":       now.weekday(),
            "is_peak_hour":      now.hour in range(7, 10) or
                                 now.hour in range(17, 21),
            "historical_avg":    round(
                self.config["volumen_normal"] *
                FACTORES_HORA[now.hour] / 120, 1
            ),
        }

    def _enviar(self, lectura: dict):
        try:
            response = requests.post(INGESTA_URL, json=lectura, timeout=5)
            if response.status_code != 201:
                print(f"[{lectura['intersection_id']}] Error {response.status_code}")
        except Exception as e:
            print(f"[{lectura['intersection_id']}] Error: {str(e)}")

    def ejecutar(self):
        print(f"Sensor {self.config['id']} enviando a {INGESTA_URL}")

        def ciclo():
            lectura = self.generate_reading()
            self._enviar(lectura)

        ciclo()
        schedule.every(30).seconds.do(ciclo)

        while True:
            schedule.run_pending()
            time.sleep(1)