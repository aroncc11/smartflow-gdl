# predictor.py
# Clase que carga el modelo Random Forest y realiza predicciones
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI

import joblib
import numpy as np
import os
import pandas as pd

# ─────────────────────────────────────────────────────────────
# MAPEO DE CLIMA A NUMERO
# Debe coincidir exactamente con train_model.py
# ─────────────────────────────────────────────────────────────
CLIMA_MAP = {
    "clear":      0,
    "cloudy":     1,
    "rain":       2,
    "heavy_rain": 3,
}


class Predictor:
    """
    Carga el modelo Random Forest entrenado y expone
    el metodo predecir() para clasificar niveles de congestion.
    """

    def __init__(self):
        ruta_modelo = os.path.join(
            os.path.dirname(__file__), "modelo_congestion.pkl"
        )

        if not os.path.exists(ruta_modelo):
            raise FileNotFoundError(
                f"Modelo no encontrado en {ruta_modelo}. "
                f"Corre train_model.py primero."
            )

        self.modelo = joblib.load(ruta_modelo)
        print(f"Modelo cargado: {ruta_modelo}")
        print(f"Clases: {self.modelo.classes_}")

    def predecir(self, lectura: dict) -> dict:
        """
        Recibe una lectura del sensor y devuelve la prediccion.

        Parametros esperados en lectura:
            vehicles_count  — conteo de vehiculos
            avg_speed_kmh   — velocidad promedio
            hour_of_day     — hora del dia (0-23)
            day_of_week     — dia de semana (0-6)
            is_peak_hour    — hora pico (bool)
            incident_flag   — incidente activo (bool)
            weather         — clima (clear/cloudy/rain/heavy_rain)
            historical_avg  — promedio historico

        Retorna:
            congestion_level — low / medium / high
            confidence       — nivel de confianza (0.0 - 1.0)
            probabilities    — probabilidades por clase
        """
        # Construir vector de features
      

        features = pd.DataFrame([{
            "vehicles_count":  lectura["vehicles_count"],
            "avg_speed_kmh":   lectura["avg_speed_kmh"],
            "hour_of_day":     lectura["hour_of_day"],
            "day_of_week":     lectura["day_of_week"],
            "is_peak_hour":    int(lectura["is_peak_hour"]),
            "incident_flag":   int(lectura["incident_flag"]),
            "weather_encoded": CLIMA_MAP.get(lectura["weather"], 0),
            "historical_avg":  lectura["historical_avg"],
        }])

        # Prediccion
        prediccion   = self.modelo.predict(features)[0]
        probabilidades = self.modelo.predict_proba(features)[0]
        confianza    = float(max(probabilidades))

        # Mapear probabilidades a clases
        clases = self.modelo.classes_
        prob_dict = {
            clase: round(float(prob), 4)
            for clase, prob in zip(clases, probabilidades)
        }

        return {
            "congestion_level": prediccion,
            "confidence":       round(confianza, 4),
            "probabilities":    prob_dict,
        }
