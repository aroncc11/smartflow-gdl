# experimento_dataset.py
# Experimento reproducible: genera un dataset sintetico (misma logica que
# sensors/dtaset/generar_historico, sin base de datos), entrena el Random Forest
# con el mismo procedimiento de train_model.py y reporta la evaluacion en un
# conjunto de prueba separado.
#
# El unico parametro nuevo es RUIDO: factor que escala la probabilidad de que la
# etiqueta de congestion NO corresponda a la dominante de su banda de velocidad.
#   RUIDO = 1.0 -> etiquetado actual del simulador
#   RUIDO = 0.0 -> etiqueta determinista por banda de velocidad
# Uso:  python experimento_dataset.py            (barrido completo, semilla 42)
import random, json, sys, os
from datetime import datetime, timedelta
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix, classification_report

SEMILLA, DIAS, REG_HORA = 42, 60, 6
RUIDO_ELEGIDO = 0.5          # fijado antes de ver resultados
BARRIDO = [1.0, 0.5, 0.25, 0.0]

INT = [
 dict(id="INT-001", vp=3500, vn=1800, vl=50), dict(id="INT-002", vp=2800, vn=1400, vl=28),
 dict(id="INT-003", vp=2100, vn=1050, vl=45), dict(id="INT-004", vp=2400, vn=1200, vl=25),
 dict(id="INT-005", vp=3200, vn=1600, vl=55)]
FH = {0:.05,1:.04,2:.03,3:.03,4:.04,5:.10,6:.35,7:.85,8:1.0,9:.80,10:.55,11:.60,12:.70,13:.65,14:.55,15:.60,16:.75,17:.90,18:.95,19:1.0,20:.80,21:.55,22:.35,23:.15}
FD = {0:.95,1:1.0,2:1.0,3:.98,4:.95,5:.80,6:.60}
FVC = {"clear":1.0,"cloudy":.95,"rain":.75,"heavy_rain":.55}
FVO = {"clear":1.0,"cloudy":1.0,"rain":.85,"heavy_rain":.65}
CLIMAS = ["clear","cloudy","rain","heavy_rain"]
CLIMA_ENC = {c:i for i,c in enumerate(CLIMAS)}
# (limite inferior de velocidad, clases, pesos del simulador actual)
BANDAS = [(40,["low","medium"],[.93,.07]), (35,["low","medium"],[.80,.20]),
          (20,["low","medium","high"],[.10,.78,.12]), (15,["medium","high"],[.75,.25]),
          (-1,["medium","high"],[.12,.88])]

def etiqueta(v, ruido):
    for lim, clases, w in BANDAS:
        if v > lim:
            d = int(np.argmax(w)); w2 = [x*ruido for x in w]
            w2[d] = 1 - sum(w2[i] for i in range(len(w2)) if i != d)
            return random.choices(clases, weights=w2)[0]

def generar(ruido):
    random.seed(SEMILLA); filas = []
    t = datetime(2026, 1, 1)
    for _ in range(DIAS*24):
        clima = random.choices(CLIMAS, weights=[.5,.25,.2,.05])[0]
        h, dia = t.hour, t.weekday()
        for c in INT:
            for _ in range(REG_HORA):
                inc = random.random() < 0.02
                base = c["vp"] if FH[h] >= .80 else c["vn"]
                veh = base*FH[h]*FD[dia]*FVO[clima]*(1.25 if inc else 1.0)/120
                veh = max(0, round(veh*random.gauss(1, .15)))
                ratio = min(veh/max(c["vp"]/120, 1), 1.0)
                vel = max(5.0, round(c["vl"]*(1-.85*ratio)*FVC[clima]*random.gauss(1, .15), 1))
                filas.append(dict(vehicles_count=veh, avg_speed_kmh=vel, hour_of_day=h, day_of_week=dia,
                    is_peak_hour=int(h in range(7,10) or h in range(17,21)), incident_flag=int(inc),
                    weather_encoded=CLIMA_ENC[clima], historical_avg=round(c["vn"]*FH[h]/120, 1),
                    congestion_level=etiqueta(vel, ruido)))
        t += timedelta(hours=1)
    return pd.DataFrame(filas)

def correr(ruido, guardar=False):
    df = generar(ruido)
    X, y = df.drop(columns="congestion_level"), df["congestion_level"]
    Xtr, Xt, ytr, yt = train_test_split(X, y, test_size=.30, random_state=42, stratify=y)
    Xv, Xte, yv, yte = train_test_split(Xt, yt, test_size=.50, random_state=42, stratify=yt)
    m = RandomForestClassifier(n_estimators=100, max_depth=15, class_weight="balanced", random_state=42, n_jobs=-1).fit(Xtr, ytr)
    pv, pt = m.predict(Xv), m.predict(Xte)
    cl = sorted(y.unique())
    r = dict(ruido=ruido, n_total=len(df), n_train=len(Xtr), n_val=len(Xv), n_test=len(Xte),
        distribucion=y.value_counts().to_dict(),
        f1_val=round(f1_score(yv, pv, average="macro"), 4), f1_test=round(f1_score(yte, pt, average="macro"), 4),
        acc_test=round(accuracy_score(yte, pt), 4), clases=cl,
        matriz_confusion_test=confusion_matrix(yte, pt, labels=cl).tolist(),
        por_clase_test=classification_report(yte, pt, labels=cl, output_dict=True, digits=4))
    if guardar:
        df.to_csv("dataset_experimento.csv", index=False)
        joblib.dump(m, "modelo_congestion_v2_experimento.pkl")
    return r

if __name__ == "__main__":
    res = [correr(r, guardar=(r == RUIDO_ELEGIDO)) for r in BARRIDO]
    for r in res: print(f"ruido={r['ruido']}: F1 prueba={r['f1_test']} (val {r['f1_val']}) acc={r['acc_test']} n_test={r['n_test']}")
    json.dump(dict(semilla=SEMILLA, dias=DIAS, ruido_elegido=RUIDO_ELEGIDO, resultados=res),
              open("resultado_experimento.json", "w"), indent=2, ensure_ascii=False)
