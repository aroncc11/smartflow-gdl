# train_model.py
# Entrenamiento del modelo Random Forest para prediccion de congestion
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI
#
# 1. Descarga datos de Supabase
# 2. Preprocesa los features
# 3. Entrena Random Forest
# 4. Evalua el modelo (F1-Score, Accuracy, Matriz de Confusion)
# 5. Guarda el modelo en modelo_congestion.pkl

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    accuracy_score
)
from sklearn.preprocessing import LabelEncoder
import joblib
import os


DATABASE_URL = os.environ["DATABASE_URL"]  # definir como variable de entorno; no guardar claves en el codigo

engine = create_engine(DATABASE_URL)

# ─────────────────────────────────────────────────────────────
# PASO 1 — CARGAR DATOS DE SUPABASE
# ─────────────────────────────────────────────────────────────
def cargar_datos():
    print("\n[1/5] Cargando datos de Supabase...")

    query = """
        SELECT
            vehicles_count,
            avg_speed_kmh,
            hour_of_day,
            day_of_week,
            is_peak_hour,
            incident_flag,
            weather,
            historical_avg,
            congestion_level
        FROM traffic_readings
        ORDER BY created_at DESC
    """

    df = pd.read_sql(query, engine)
    print(f"      Registros cargados: {len(df)}")
    print(f"      Distribucion de congestion:")
    print(df["congestion_level"].value_counts())
    return df


# ─────────────────────────────────────────────────────────────
# PASO 2 — PREPROCESAMIENTO
# ─────────────────────────────────────────────────────────────
def preprocesar(df):
    print("\n[2/5] Preprocesando datos...")

    # Convertir booleanos a enteros
    df["is_peak_hour"]  = df["is_peak_hour"].astype(int)
    df["incident_flag"] = df["incident_flag"].astype(int)

    # Codificar clima como numero
    clima_map = {
        "clear":      0,
        "cloudy":     1,
        "rain":       2,
        "heavy_rain": 3,
    }
    df["weather_encoded"] = df["weather"].map(clima_map)

    # Features del modelo
    features = [
        "vehicles_count",
        "avg_speed_kmh",
        "hour_of_day",
        "day_of_week",
        "is_peak_hour",
        "incident_flag",
        "weather_encoded",
        "historical_avg",
    ]

    X = df[features]
    y = df["congestion_level"]

    print(f"      Features: {features}")
    print(f"      Shape X: {X.shape}")

    return X, y


# ─────────────────────────────────────────────────────────────
# PASO 3 — DIVIDIR DATOS
# ─────────────────────────────────────────────────────────────
def dividir_datos(X, y):
    print("\n[3/5] Dividiendo datos 70/15/15...")

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    print(f"      Entrenamiento: {len(X_train)} registros")
    print(f"      Validacion:    {len(X_val)} registros")
    print(f"      Prueba:        {len(X_test)} registros")

    return X_train, X_val, X_test, y_train, y_val, y_test


# ─────────────────────────────────────────────────────────────
# PASO 4 — ENTRENAR MODELO
# ─────────────────────────────────────────────────────────────
def entrenar(X_train, y_train):
    print("\n[4/5] Entrenando Random Forest...")

    modelo = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    modelo.fit(X_train, y_train)
    print("      Modelo entrenado exitosamente")
    return modelo


# ─────────────────────────────────────────────────────────────
# PASO 5 — EVALUAR Y GUARDAR
# ─────────────────────────────────────────────────────────────
def evaluar_y_guardar(modelo, X_val, X_test, y_val, y_test):
    print("\n[5/5] Evaluando modelo...")

    # Validacion
    y_pred_val = modelo.predict(X_val)
    f1_val     = f1_score(y_val, y_pred_val, average="macro")
    acc_val    = accuracy_score(y_val, y_pred_val)

    # Prueba
    y_pred_test = modelo.predict(X_test)
    f1_test     = f1_score(y_test, y_pred_test, average="macro")
    acc_test    = accuracy_score(y_test, y_pred_test)

    print("\n" + "=" * 55)
    print("  RESULTADOS DEL MODELO")
    print("=" * 55)
    print(f"  Validacion  — F1: {f1_val:.4f}  Accuracy: {acc_val:.4f}")
    print(f"  Prueba      — F1: {f1_test:.4f}  Accuracy: {acc_test:.4f}")
    print(f"  Meta del proyecto: F1 >= 0.85")
    print(f"  {'OBJETIVO ALCANZADO' if f1_test >= 0.85 else 'OBJETIVO NO ALCANZADO'}")

    print("\n  Reporte detallado (Test):")
    print(classification_report(y_test, y_pred_test))

    print("\n  Matriz de Confusion (Test):")
    print(confusion_matrix(y_test, y_pred_test))

    print("\n  Importancia de features:")
    features = [
        "vehicles_count", "avg_speed_kmh", "hour_of_day",
        "day_of_week", "is_peak_hour", "incident_flag",
        "weather_encoded", "historical_avg"
    ]
    importancias = sorted(
        zip(features, modelo.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    for feature, importancia in importancias:
        barra = "█" * int(importancia * 50)
        print(f"  {feature:<20} {importancia:.4f} {barra}")

    # Guardar modelo
    ruta_modelo = os.path.join(os.path.dirname(__file__), "modelo_congestion.pkl")
    joblib.dump(modelo, ruta_modelo)
    print(f"\n  Modelo guardado en: {ruta_modelo}")
    print("=" * 55)

    return f1_test


if __name__ == "__main__":
    print("=" * 55)
    print("  SmartFlow GDL - Entrenamiento Random Forest")
    print("=" * 55)

    df                                    = cargar_datos()
    X, y                                  = preprocesar(df)
    X_train, X_val, X_test, y_train, y_val, y_test = dividir_datos(X, y)
    modelo                                = entrenar(X_train, y_train)
    f1                                    = evaluar_y_guardar(modelo, X_val, X_test, y_val, y_test)

    if f1 >= 0.85:
        print("\n  Listo para usar en el microservicio de prediccion.")
    else:
        print("\n  Considera generar mas datos o ajustar hiperparametros.")