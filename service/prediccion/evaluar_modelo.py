# evaluar_modelo.py
# Evalua el modelo Random Forest DESPLEGADO (modelo_congestion.pkl) contra
# lecturas de traffic_readings que NO se usaron para entrenarlo, y genera
# matriz de confusion, metricas por clase y distribucion de clases.
#
# Uso:
#   set DATABASE_URL=postgresql+pg8000://USUARIO:CLAVE@HOST:5432/postgres
#   python evaluar_modelo.py            (muestra de 50,000 filas)
#   python evaluar_modelo.py 0          (todas las filas)
#
# La URL se toma de la variable de entorno; no se guarda ninguna clave aqui.

import os, sys, json
import joblib
import pandas as pd
from sqlalchemy import create_engine
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score

URL = os.environ.get("DATABASE_URL")
if not URL:
    sys.exit("Falta la variable de entorno DATABASE_URL")

MUESTRA = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
CLIMA = {"clear": 0, "cloudy": 1, "rain": 2, "heavy_rain": 3}
FEATURES = ["vehicles_count", "avg_speed_kmh", "hour_of_day", "day_of_week",
            "is_peak_hour", "incident_flag", "weather_encoded", "historical_avg"]

engine = create_engine(URL)
sql = """SELECT vehicles_count, avg_speed_kmh, hour_of_day, day_of_week,
                is_peak_hour, incident_flag, weather, historical_avg, congestion_level
         FROM traffic_readings"""
if MUESTRA > 0:
    sql += f" ORDER BY random() LIMIT {MUESTRA}"
df = pd.read_sql(sql, engine)
df["is_peak_hour"] = df["is_peak_hour"].astype(int)
df["incident_flag"] = df["incident_flag"].astype(int)
df["weather_encoded"] = df["weather"].map(CLIMA)

modelo = joblib.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_congestion.pkl"))
X, y = df[FEATURES], df["congestion_level"]
pred = modelo.predict(X)
clases = sorted(y.unique())

res = {
    "n_muestras": int(len(df)),
    "distribucion_clases": y.value_counts().to_dict(),
    "f1_macro": round(float(f1_score(y, pred, average="macro")), 4),
    "accuracy": round(float(accuracy_score(y, pred)), 4),
    "clases": clases,
    "matriz_confusion": confusion_matrix(y, pred, labels=clases).tolist(),
    "por_clase": classification_report(y, pred, labels=clases, output_dict=True),
}
print(json.dumps(res, indent=2, ensure_ascii=False))
with open("resultado_evaluacion.json", "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2, ensure_ascii=False)
print("\nGuardado en resultado_evaluacion.json")
