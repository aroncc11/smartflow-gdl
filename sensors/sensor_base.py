# sensor_base.py
# Clase base para todos los sensores de trafico urbano
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI
#
# Parametros calibrados con:
#   - INEGI: Estadisticas de vehiculos en circulacion 2024 (Jalisco)
#   - SEMOVI / datos.jalisco.gob.mx: MiBici, GTFS MiTransporte
#   - Jalisco Como Vamos: Reporte Moverse en GDL 2022
#   - TomTom Traffic API: velocidades reales por interseccion
#   - Coordenadas verificadas en Google Maps Street View

from datetime import datetime
import random
import schedule
import time
import requests

# ─────────────────────────────────────────────────────────────
# URL DEL MICROSERVICIO DE INGESTA
# ─────────────────────────────────────────────────────────────
INGESTA_URL = "https://smartflow-gdl-production.up.railway.app/readings"

# ─────────────────────────────────────────────────────────────
# FACTORES HORARIOS - curva bimodal
# Fuente: MiBici SEMOVI (pico tarde 19:00)
#         Jalisco Como Vamos 2022 (pico manana 7-9am)
# ─────────────────────────────────────────────────────────────
FACTORES_HORA = {
    0: 0.05,  1: 0.04,  2: 0.03,  3: 0.03,
    4: 0.04,  5: 0.10,  6: 0.35,  7: 0.85,
    8: 1.00,  9: 0.80, 10: 0.55, 11: 0.60,
   12: 0.70, 13: 0.65, 14: 0.55, 15: 0.60,
   16: 0.75, 17: 0.90, 18: 0.95, 19: 1.00,
   20: 0.80, 21: 0.55, 22: 0.35, 23: 0.15,
}

# ─────────────────────────────────────────────────────────────
# FACTORES POR DIA DE SEMANA
# Fuente: HCM (Highway Capacity Manual)
# 0=Lunes, 6=Domingo
# ─────────────────────────────────────────────────────────────
FACTORES_DIA = {
    0: 0.95,  # Lunes
    1: 1.00,  # Martes
    2: 1.00,  # Miercoles
    3: 0.98,  # Jueves
    4: 0.95,  # Viernes
    5: 0.80,  # Sabado
    6: 0.60,  # Domingo
}

# ─────────────────────────────────────────────────────────────
# FACTORES CLIMATICOS
# Fuente: SMN - temporada de lluvias GDL mayo-octubre
# ─────────────────────────────────────────────────────────────
FACTORES_VELOCIDAD_CLIMA = {
    "clear":      1.00,
    "cloudy":     0.95,
    "rain":       0.75,
    "heavy_rain": 0.55,
}

FACTORES_VOLUMEN_CLIMA = {
    "clear":      1.00,
    "cloudy":     1.00,
    "rain":       0.85,
    "heavy_rain": 0.65,
}

# ─────────────────────────────────────────────────────────────
# TIPOS DE INCIDENTE
# ─────────────────────────────────────────────────────────────
TIPOS_INCIDENTE = [
    "Accidente vehicular",
    "Cierre vial por obra",
    "Manifestacion",
    "Vehiculo descompuesto",
    "Evento masivo cercano",
]


# ─────────────────────────────────────────────────────────────
# CLASE BASE
# ─────────────────────────────────────────────────────────────
class SensorBase:
    """
    Clase base para todos los sensores de trafico.
    Cada interseccion crea una instancia pasando su config.

    Config esperada:
        id              - identificador (ej. INT-001)
        nombre          - nombre de la interseccion
        lat             - latitud verificada en Google Maps
        lon             - longitud verificada en Google Maps
        volumen_pico    - vehiculos/hora en hora pico
        volumen_normal  - vehiculos/hora en hora normal
        velocidad_libre - km/h sin congestion (calibrado con TomTom)
    """

    def __init__(self, config: dict):
        self.config        = config
        self._incidente    = {"activo": False, "detalle": None}
        self._clima_actual = self._generar_clima()
        self._hora_clima   = datetime.now().hour
        print(f"Sensor inicializado: [{config['id']}] {config['nombre']}")
        print(f"   Coordenadas: ({config['lat']}, {config['lon']})")
        print(f"   Clima inicial: {self._clima_actual}")

    # ── Clima - cambia solo una vez por hora ────────────────
    def _generar_clima(self) -> str:
        mes = datetime.now().month
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
        hora_actual = datetime.now().hour
        if self._hora_clima != hora_actual:
            self._clima_actual = self._generar_clima()
            self._hora_clima   = hora_actual
            print(f"   [{self.config['id']}] Clima actualizado: {self._clima_actual}")
        return self._clima_actual

    # ── Incidente ───────────────────────────────────────────
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

    # ── Volumen ─────────────────────────────────────────────
    def _calcular_volumen(self, clima: str, incidente: bool) -> int:
        now  = datetime.now()
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

        # Ruido gaussiano +-15% para variabilidad realista
        vehiculos = vehiculos * random.gauss(1.0, 0.15)

        return max(0, round(vehiculos))

    # ── Velocidad (Greenshields) ────────────────────────────
    def _calcular_velocidad(self, vehiculos: int, clima: str) -> float:
        capacidad_30s   = self.config["volumen_pico"] / 120
        ratio           = min(vehiculos / max(capacidad_30s, 1), 1.0)
        velocidad_libre = self.config["velocidad_libre"]
        factor_clima    = FACTORES_VELOCIDAD_CLIMA[clima]

        velocidad = velocidad_libre * (1 - 0.85 * ratio) * factor_clima

        # Ruido gaussiano +-15% para variabilidad realista
        velocidad = velocidad * random.gauss(1.0, 0.15)

        return max(5.0, round(velocidad, 1))

    # ── Congestion con zonas grises ─────────────────────────
    def _calcular_congestion(self, velocidad: float) -> str:
        """
        Congestion con probabilidades en zonas grises.
        Simula la ambiguedad real del trafico urbano.
        Evita sobreentrenamiento del modelo de IA.
        """
        # Zona claramente libre
        if velocidad > 40:
            return random.choices(
                ["low", "medium"],
                weights=[0.93, 0.07]
            )[0]
        # Zona libre con algo de incertidumbre
        elif velocidad > 35:
            return random.choices(
                ["low", "medium"],
                weights=[0.80, 0.20]
            )[0]
        # Zona gris - puede ser cualquiera
        elif velocidad > 20:
            return random.choices(
                ["low", "medium", "high"],
                weights=[0.10, 0.78, 0.12]
            )[0]
        # Zona media-alta
        elif velocidad > 15:
            return random.choices(
                ["medium", "high"],
                weights=[0.75, 0.25]
            )[0]
        # Zona claramente congestionada
        else:
            return random.choices(
                ["medium", "high"],
                weights=[0.12, 0.88]
            )[0]

    # ── Lectura completa ────────────────────────────────────
    def generate_reading(self) -> dict:
        now     = datetime.now()
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

    # ── Enviar al microservicio ─────────────────────────────
    def _enviar(self, lectura: dict):
        try:
            response = requests.post(INGESTA_URL, json=lectura, timeout=5)
            if response.status_code == 201:
                print(f"[{lectura['intersection_id']}] Enviado - "
                      f"{lectura['congestion_level'].upper()} "
                      f"| {lectura['avg_speed_kmh']} km/h "
                      f"| {lectura['vehicles_count']} veh/30s")
            else:
                print(f"[{lectura['intersection_id']}] "
                      f"Error {response.status_code}: {response.text}")
        except requests.exceptions.ConnectionError:
            print(f"[{lectura['intersection_id']}] Sin microservicio - "
                  f"{lectura['congestion_level'].upper()} "
                  f"| {lectura['avg_speed_kmh']} km/h "
                  f"| {lectura['vehicles_count']} veh/30s")
            if lectura["incident_flag"]:
                print(f"   INCIDENTE: {lectura['incident_detail']}")
        except requests.exceptions.Timeout:
            print(f"[{lectura['intersection_id']}] Timeout")

    # ── Imprimir en consola ─────────────────────────────────
    def _imprimir(self, lectura: dict):
        nivel = {
            "low":    "[LOW]",
            "medium": "[MEDIUM]",
            "high":   "[HIGH]"
        }
        clima = {
            "clear":      "[CLEAR]",
            "cloudy":     "[CLOUDY]",
            "rain":       "[RAIN]",
            "heavy_rain": "[HEAVY RAIN]"
        }
        print(f"\n[{lectura['timestamp'][:19]}] "
              f"{lectura['intersection_id']} - {lectura['intersection_name']}")
        print(f"  Vehiculos:  {lectura['vehicles_count']} veh/30s")
        print(f"  Velocidad:  {lectura['avg_speed_kmh']} km/h")
        print(f"  Congestion: {nivel[lectura['congestion_level']]} "
              f"{lectura['congestion_level'].upper()}")
        print(f"  Clima:      {clima[lectura['weather']]} {lectura['weather']}")
        print(f"  Hora pico:  {'Si' if lectura['is_peak_hour'] else 'No'}")
        if lectura["incident_flag"]:
            print(f"  INCIDENTE: {lectura['incident_detail']}")

    # ── Loop principal ──────────────────────────────────────
    def ejecutar(self):
        print("\n" + "=" * 55)
        print(f"  Sensor: {self.config['nombre']}")
        print(f"  ID:     {self.config['id']}")
        print(f"  Coords: ({self.config['lat']}, {self.config['lon']})")
        print(f"  Lectura cada 30s - Ctrl+C para detener")
        print("=" * 55)

        def ciclo():
            lectura = self.generate_reading()
            self._imprimir(lectura)
            self._enviar(lectura)

        ciclo()
        schedule.every(30).seconds.do(ciclo)

        while True:
            schedule.run_pending()
            time.sleep(1)