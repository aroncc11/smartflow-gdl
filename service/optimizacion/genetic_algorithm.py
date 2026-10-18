# genetic_algorithm.py
# Algoritmo Genetico para optimizacion de tiempos de semaforo
# SmartFlow GDL 2026 - Universidad de Guadalajara / CUCEI
#
# Usa la libreria DEAP para evolucionar soluciones optimas
# Cromosoma: [t_verde_INT001, t_verde_INT002, t_verde_INT003, t_verde_INT004, t_verde_INT005]
# Objetivo: minimizar tiempo de espera ponderado por volumen vehicular,
# sujeto a un presupuesto de verde COMPARTIDO entre las 5 intersecciones
# (ver nota en calcular_fitness).

import random
from deap import base, creator, tools, algorithms
import numpy as np

# ─────────────────────────────────────────────────────────────
# CONFIGURACION DE INTERSECCIONES
# ─────────────────────────────────────────────────────────────
INTERSECCIONES = [
    {"id": "INT-001", "nombre": "Av. Vallarta - Av. Yaquis",          "volumen_pico": 3500},
    {"id": "INT-002", "nombre": "Av. Lopez Mateos - Av. Americas",    "volumen_pico": 2800},
    {"id": "INT-003", "nombre": "Av. Guadalupe - San Ignacio",        "volumen_pico": 2100},
    {"id": "INT-004", "nombre": "Av. Vallarta - Ninos Heroes",        "volumen_pico": 2400},
    {"id": "INT-005", "nombre": "Av. Lopez Mateos Sur - M. Otero",    "volumen_pico": 3200},
]

# ─────────────────────────────────────────────────────────────
# PARAMETROS DEL ALGORITMO GENETICO
# ─────────────────────────────────────────────────────────────
TIEMPO_VERDE_MIN  = 20    # segundos minimo fase verde
TIEMPO_VERDE_MAX  = 120   # segundos maximo fase verde
TIEMPO_AMARILLO   = 3     # segundos fijos
TIEMPO_CICLO_MAX  = 180   # segundos maximo ciclo total

TAM_POBLACION = 100
NUM_GENERACIONES = 50
PROB_CRUZAMIENTO = 0.85
PROB_MUTACION    = 0.15

N_INTERSECCIONES = len(INTERSECCIONES)

# ─────────────────────────────────────────────────────────────
# PRESUPUESTO COMPARTIDO DE VERDE (NUEVO)
# ─────────────────────────────────────────────────────────────
# Antes, cada interseccion maximizaba su propio verde sin limite real,
# asi que el AG siempre convergia a asignarle 120s a las 5 sin importar
# la congestion de entrada (resultado constante de 56.8% en 30 corridas
# reales de prueba, con desviacion estandar = 0).
#
# En una red de semaforos real existe un limite practico de cuanto verde
# puede repartirse simultaneamente entre intersecciones (coordinacion de
# onda verde, capacidad de la red). Modelamos esto como un presupuesto
# total de verde compartido entre las 5 intersecciones: el promedio de
# verde por interseccion no puede exceder 70s (reduccion de ~42% respecto
# al maximo individual de 120s), forzando al AG a repartir ese presupuesto
# segun la congestion relativa de cada una en lugar de maximizar todas por
# igual.
PRESUPUESTO_VERDE_PROMEDIO = 70   # segundos promedio por interseccion
PENALIZACION_EXCESO = 5000        # peso de la penalizacion por exceder el presupuesto


# ─────────────────────────────────────────────────────────────
# FUNCION DE FITNESS
# Minimiza el tiempo promedio de espera ponderado por volumen,
# sujeto al presupuesto de verde compartido.
# ─────────────────────────────────────────────────────────────
def calcular_fitness(individuo, niveles_congestion: list) -> tuple:
    """
    Calcula el tiempo promedio de espera para una configuracion
    de tiempos de semaforo dada la congestion actual.

    individuo: lista de tiempos de verde para cada interseccion
    niveles_congestion: lista de niveles ["low","medium","high"] por interseccion

    Retorna: (fitness,) — tupla requerida por DEAP
    """
    # Factores de demanda por nivel de congestion
    factor_congestion = {
        "low":    0.4,
        "medium": 0.7,
        "high":   1.0,
    }

    tiempo_espera_total = 0
    volumen_total       = 0
    suma_verde          = 0

    for i, config in enumerate(INTERSECCIONES):
        t_verde  = individuo[i]
        t_rojo   = max(10, TIEMPO_CICLO_MAX - t_verde - TIEMPO_AMARILLO)
        volumen  = config["volumen_pico"]
        factor   = factor_congestion.get(niveles_congestion[i], 0.7)

        # Tiempo de espera = demanda * tiempo rojo / 2
        espera = factor * volumen * (t_rojo / 2)

        tiempo_espera_total += espera * volumen
        volumen_total       += volumen
        suma_verde          += t_verde

    # Promedio ponderado por volumen
    fitness = tiempo_espera_total / max(volumen_total, 1)

    # Penalizacion por exceder el presupuesto compartido de verde.
    # Esto es lo que obliga al AG a repartir el verde segun congestion
    # relativa, en vez de maximizar cada interseccion por separado.
    presupuesto_total = PRESUPUESTO_VERDE_PROMEDIO * N_INTERSECCIONES
    exceso = max(0, suma_verde - presupuesto_total)
    fitness += PENALIZACION_EXCESO * (exceso ** 2)

    return (fitness,)


# ─────────────────────────────────────────────────────────────
# CONFIGURACION DE DEAP
# ─────────────────────────────────────────────────────────────
def configurar_deap(niveles_congestion: list):
    """
    Configura el toolbox de DEAP con los operadores geneticos.
    Se llama cada vez que se ejecuta la optimizacion.
    """
    # Limpiar creator si ya existe (evita error en multiples llamadas)
    if hasattr(creator, "FitnessMin"):
        del creator.FitnessMin
    if hasattr(creator, "Individual"):
        del creator.Individual

    # Minimizar el fitness (menor espera = mejor)
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()

    # Gen: tiempo de verde aleatorio entre MIN y MAX
    toolbox.register(
        "attr_tiempo",
        random.randint,
        TIEMPO_VERDE_MIN,
        TIEMPO_VERDE_MAX
    )

    # Individuo: lista de N genes (uno por interseccion)
    toolbox.register(
        "individual",
        tools.initRepeat,
        creator.Individual,
        toolbox.attr_tiempo,
        n=N_INTERSECCIONES
    )

    # Poblacion: lista de individuos
    toolbox.register(
        "population",
        tools.initRepeat,
        list,
        toolbox.individual
    )

    # Operadores geneticos
    toolbox.register(
        "evaluate",
        calcular_fitness,
        niveles_congestion=niveles_congestion
    )
    toolbox.register("mate",     tools.cxBlend, alpha=0.5)
    toolbox.register("mutate",   tools.mutGaussian, mu=0, sigma=10, indpb=0.2)
    toolbox.register("select",   tools.selTournament, tournsize=3)

    return toolbox


# ─────────────────────────────────────────────────────────────
# FUNCION PRINCIPAL DE OPTIMIZACION
# ─────────────────────────────────────────────────────────────
def optimizar_semaforos(niveles_congestion: list) -> dict:
    """
    Ejecuta el Algoritmo Genetico y retorna los tiempos optimos.

    niveles_congestion: lista de 5 strings ["low","medium","high",...]
                        en el mismo orden que INTERSECCIONES

    Retorna dict con tiempos optimos por interseccion.
    """
    toolbox = configurar_deap(niveles_congestion)

    # Inicializar poblacion
    poblacion = toolbox.population(n=TAM_POBLACION)

    # Estadisticas
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("min",  np.min)
    stats.register("avg",  np.mean)

    # Ejecutar algoritmo genetico
    poblacion, log = algorithms.eaSimple(
        poblacion,
        toolbox,
        cxpb=PROB_CRUZAMIENTO,
        mutpb=PROB_MUTACION,
        ngen=NUM_GENERACIONES,
        stats=stats,
        verbose=False
    )

    # Obtener mejor individuo
    mejor = tools.selBest(poblacion, k=1)[0]

    # Reparar valores fuera de rango
    tiempos_optimos = [
        max(TIEMPO_VERDE_MIN, min(TIEMPO_VERDE_MAX, int(round(t))))
        for t in mejor
    ]

    # Construir resultado
    resultado = {
        "tiempos_optimos": {},
        "fitness":         mejor.fitness.values[0],
        "generaciones":    NUM_GENERACIONES,
        "log": [
            {"gen": i, "min": round(r["min"], 2), "avg": round(r["avg"], 2)}
             for i, r in enumerate(log)
        ]

    }

    for i, config in enumerate(INTERSECCIONES):
        t_verde = tiempos_optimos[i]
        t_rojo  = max(10, TIEMPO_CICLO_MAX - t_verde - TIEMPO_AMARILLO)
        resultado["tiempos_optimos"][config["id"]] = {
            "nombre":        config["nombre"],
            "congestion":    niveles_congestion[i],
            "verde_default": 45,
            "verde_optimo":  t_verde,
            "rojo_optimo":   t_rojo,
            "amarillo":      TIEMPO_AMARILLO,
            "mejora":        round(((45 - t_verde) / 45) * 100, 1)
                             if t_verde < 45 else 0,
            "espera_default_seg":  round((TIEMPO_CICLO_MAX - 45 - 3) / 2, 1),
            "espera_optima_seg":   round(t_rojo / 2, 1),
            "ahorro_seg":          round(((TIEMPO_CICLO_MAX - 45 - 3) / 2) - (t_rojo / 2), 1),
            "mejora_porcentaje":   round((1 - (t_rojo / (TIEMPO_CICLO_MAX - 45 - 3))) * 100, 1),
        }

    return resultado
