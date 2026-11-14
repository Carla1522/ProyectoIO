"""Motor matematico CPM/PERT.

Implementa ordenamiento topologico, pasada hacia adelante y hacia atras,
holguras, ruta critica y la estimacion probabilistica con distribucion normal.
"""

from __future__ import annotations

import copy
import math
from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List

from core.modelo import Proyecto

EPSILON = 1e-9
TOL = 1e-6  # tolerancia para comparar tiempos flotantes expresados en dias


class CicloError(ValueError):
    """El grafo contiene un ciclo y no puede programarse."""


# --------------------------------------------------------------------- Orden
def orden_topologico(proyecto: Proyecto) -> List[str]:
    """Orden topologico (Kahn). Lanza CicloError si el grafo tiene ciclos."""
    actividades = proyecto.actividades
    ids = set(actividades)
    grado = {ida: 0 for ida in ids}
    sucesores: Dict[str, List[str]] = defaultdict(list)

    for actividad in actividades.values():
        for pred in actividad.predecesoras:
            if pred not in ids:
                continue
            grado[actividad.id] += 1
            sucesores[pred].append(actividad.id)

    cola = deque(sorted([ida for ida, g in grado.items() if g == 0]))
    orden: List[str] = []
    while cola:
        actual = cola.popleft()
        orden.append(actual)
        for sucesor in sorted(sucesores[actual]):
            grado[sucesor] -= 1
            if grado[sucesor] == 0:
                cola.append(sucesor)

    if len(orden) != len(ids):
        pendientes = sorted(ids - set(orden))
        raise CicloError(
            "Existe una dependencia circular entre: " + ", ".join(pendientes)
        )
    return orden


def _sucesores(proyecto: Proyecto) -> Dict[str, List[str]]:
    sucesores: Dict[str, List[str]] = defaultdict(list)
    for actividad in proyecto.actividades.values():
        for pred in actividad.predecesoras:
            if pred in proyecto.actividades:
                sucesores[pred].append(actividad.id)
    return sucesores


# ------------------------------------------------------------------ CPM/PERT
def calcular_cpm(proyecto: Proyecto) -> Dict[str, Any]:
    """Calcula el cronograma completo y devuelve un diccionario con los resultados.

    El motor no modifica el proyecto: no elimina predecesoras ni reordena la
    tabla. Las dependencias que apuntan a IDs inexistentes se ignoran para el
    calculo (no existe arista) pero se devuelven en ``dependencias_huerfanas``
    para que el validador y la interfaz las muestren.
    """
    if not proyecto.actividades:
        return {
            "filas": [],
            "duracion": 0.0,
            "ruta_critica": [],
            "actividades_criticas": [],
            "varianza": 0.0,
            "sigma": 0.0,
            "orden": [],
            "dependencias_huerfanas": {},
        }

    orden = orden_topologico(proyecto)
    actividades = proyecto.actividades
    sucesores = _sucesores(proyecto)

    es: Dict[str, float] = {}
    ef: Dict[str, float] = {}
    for ida in orden:
        actividad = actividades[ida]
        es[ida] = max((ef[p] for p in actividad.predecesoras if p in ef), default=0.0)
        ef[ida] = es[ida] + actividad.duracion

    duracion = max(ef.values(), default=0.0)

    ls: Dict[str, float] = {}
    lf: Dict[str, float] = {}
    for ida in reversed(orden):
        actividad = actividades[ida]
        hijos = [s for s in sucesores.get(ida, []) if s in ls]
        lf[ida] = min((ls[s] for s in hijos), default=duracion)
        ls[ida] = lf[ida] - actividad.duracion

    filas: List[Dict[str, Any]] = []
    for posicion, ida in enumerate(orden, start=1):
        actividad = actividades[ida]
        holgura = ls[ida] - es[ida]
        hijos = [s for s in sucesores.get(ida, []) if s in es]
        holgura_libre = (min((es[s] for s in hijos), default=duracion)) - ef[ida]
        filas.append(
            {
                "id": ida,
                "codigo": f"A{posicion}",
                "nombre": actividad.nombre,
                "tipo": actividad.tipo,
                "entidad": actividad.entidad,
                "categoria": actividad.categoria,
                "predecesoras": ", ".join(actividad.predecesoras),
                "a": actividad.optimista,
                "m": actividad.probable,
                "b": actividad.pesimista,
                "te": round(actividad.duracion, 2),
                "varianza": round(actividad.varianza, 4),
                "sigma": round(actividad.sigma, 4),
                "es": round(es[ida], 2),
                "ef": round(ef[ida], 2),
                "ls": round(ls[ida], 2),
                "lf": round(lf[ida], 2),
                "holgura": round(max(holgura, 0.0), 2),
                "holgura_libre": round(max(holgura_libre, 0.0), 2),
                "critica": holgura <= EPSILON,
                "inicio_semana": round(es[ida] / 5.0, 2),
                "fuente_url": actividad.fuente_url,
            }
        )

    criticas = [fila["id"] for fila in filas if fila["critica"]]
    ruta_critica, varianza_total = _ruta_critica_ponderada(proyecto, es, ef, ls)
    sigma = math.sqrt(varianza_total) if varianza_total > 0 else 0.0

    return {
        "filas": filas,
        "duracion": round(duracion, 2),
        "ruta_critica": ruta_critica,
        "actividades_criticas": criticas,
        "varianza": round(varianza_total, 4),
        "sigma": round(sigma, 4),
        "orden": orden,
        "dependencias_huerfanas": proyecto.dependencias_huerfanas(),
    }


def _ruta_critica_ponderada(
    proyecto: Proyecto,
    es: Dict[str, float],
    ef: Dict[str, float],
    ls: Dict[str, float],
) -> tuple[List[str], float]:
    """Ruta critica de mayor varianza y su varianza total.

    PERT aproxima la duracion del proyecto por la ruta mas larga y supone
    duraciones independientes. Cuando existen varias rutas criticas, la
    varianza del proyecto se toma de la ruta con mayor varianza (criterio
    conservador). Sumar la varianza de *todas* las actividades con holgura cero
    sobreestima sigma, porque algunas pertenecen a rutas alternas.
    """
    if not ef:
        return [], 0.0

    flotante = {ida: ls[ida] - es[ida] for ida in ef}
    var_acum: Dict[str, float] = {}
    # ef conserva el orden topologico de insercion, por lo que las
    # predecesoras ya tienen su varianza acumulada calculada.
    for ida in ef:
        actividad = proyecto.actividades[ida]
        previas = [
            p
            for p in actividad.predecesoras
            if p in ef and abs(ef[p] - es[ida]) <= TOL and flotante[p] <= TOL
        ]
        var_acum[ida] = actividad.varianza + max(
            (var_acum[p] for p in previas), default=0.0
        )

    sucesores = _sucesores(proyecto)
    terminales = [
        ida for ida in ef if not sucesores.get(ida) and flotante[ida] <= TOL
    ]
    if not terminales:
        terminales = [max(ef, key=lambda ida: ef[ida])]

    actual = max(terminales, key=lambda ida: (ef[ida], var_acum.get(ida, 0.0)))
    cadena: List[str] = [actual]
    visitados = {actual}
    while True:
        actividad = proyecto.actividades[actual]
        candidatas = [
            p
            for p in actividad.predecesoras
            if p in ef
            and p not in visitados
            and abs(ef[p] - es[actual]) <= TOL
            and flotante[p] <= TOL
        ]
        if not candidatas:
            break
        actual = max(candidatas, key=lambda ida: (var_acum.get(ida, 0.0), ef[ida]))
        cadena.append(actual)
        visitados.add(actual)

    cadena.reverse()
    varianza = sum(proyecto.actividades[ida].varianza for ida in cadena)
    return cadena, varianza


# ------------------------------------------------------------ Probabilidad
def probabilidad_exito(cpm: Dict[str, Any], plazo_objetivo: float) -> Dict[str, Any]:
    """P(T <= plazo) usando el teorema del limite central sobre la ruta critica."""
    duracion = float(cpm["duracion"])
    sigma = float(cpm["sigma"])
    if sigma <= EPSILON:
        probabilidad = 1.0 if plazo_objetivo >= duracion else 0.0
        return {
            "z": float("inf") if plazo_objetivo >= duracion else float("-inf"),
            "probabilidad": probabilidad,
            "plazo": plazo_objetivo,
            "duracion_esperada": duracion,
            "sigma": 0.0,
            "holgura_plazo": round(plazo_objetivo - duracion, 2),
        }
    z = (plazo_objetivo - duracion) / sigma
    return {
        "z": round(z, 4),
        "probabilidad": _normal_cdf(z),
        "plazo": plazo_objetivo,
        "duracion_esperada": duracion,
        "sigma": sigma,
        "holgura_plazo": round(plazo_objetivo - duracion, 2),
    }


def _normal_cdf(z: float) -> float:
    try:  # scipy es la via principal
        from scipy.stats import norm

        return float(norm.cdf(z))
    except Exception:  # pragma: no cover - respaldo sin scipy
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def plazo_para_probabilidad(cpm: Dict[str, Any], probabilidad: float) -> float:
    """Plazo necesario para alcanzar una probabilidad objetivo."""
    probabilidad = min(max(probabilidad, 0.0001), 0.9999)
    duracion = float(cpm["duracion"])
    sigma = float(cpm["sigma"])
    if sigma <= EPSILON:
        return round(duracion, 2)
    try:
        from scipy.stats import norm

        z = float(norm.ppf(probabilidad))
    except Exception:  # pragma: no cover
        z = _z_aproximado(probabilidad)
    return round(duracion + z * sigma, 2)


def _z_aproximado(p: float) -> float:
    # Aproximacion de Acklam suficiente para el respaldo sin scipy
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


# ------------------------------------------------------------- Flujo de caja
def flujo_caja(
    cpm: Dict[str, Any],
    costos_detalle: Iterable[Dict[str, Any]],
    dias_por_semana: int = 5,
    administrativos: float = 0.0,
) -> List[Dict[str, Any]]:
    """Distribuye los costos linealmente a lo largo de la duracion de cada actividad.

    Cada actividad reparte su subtotal entre los dias laborables que realmente
    ocupa, ponderando por el solapamiento de cada dia con [ES, EF]. Asi la suma
    del flujo coincide con el presupuesto y no se pierden ni se duplican
    fracciones de dia cuando la duracion no es entera.
    """
    costos = {fila["id"]: fila.get("subtotal", 0.0) for fila in costos_detalle}
    por_semana: Dict[int, float] = defaultdict(float)

    for fila in cpm["filas"]:
        subtotal = float(costos.get(fila["id"], 0.0))
        if subtotal <= 0:
            continue
        duracion = float(fila["te"])
        inicio = float(fila["es"])
        if duracion <= TOL:
            # Una actividad de duracion cero se imputa completa a su semana.
            por_semana[int(inicio // dias_por_semana)] += subtotal
            continue
        fin = inicio + duracion
        dia = int(math.floor(inicio))
        while dia < fin - TOL:
            solapamiento = min(fin, dia + 1.0) - max(inicio, float(dia))
            if solapamiento > 0:
                por_semana[int(dia // dias_por_semana)] += subtotal * solapamiento / duracion
            dia += 1

    # Los gastos administrativos no pertenecen a una actividad concreta: se
    # prorratean a lo largo de la duracion total para que el flujo sume el
    # presupuesto completo y la conciliacion sea verificable.
    administrativos = max(float(administrativos or 0.0), 0.0)
    duracion_proyecto = float(cpm.get("duracion", 0.0) or 0.0)
    if administrativos > 0 and duracion_proyecto > TOL:
        dia = 0
        while dia < duracion_proyecto - TOL:
            solapamiento = min(duracion_proyecto, dia + 1.0) - float(dia)
            if solapamiento > 0:
                por_semana[int(dia // dias_por_semana)] += (
                    administrativos * solapamiento / duracion_proyecto
                )
            dia += 1

    total_semanas = max(por_semana, default=-1) + 1
    semanas: List[Dict[str, Any]] = []
    acumulado = 0.0
    for semana in range(total_semanas):
        monto = por_semana.get(semana, 0.0)
        acumulado += monto
        semanas.append(
            {
                "semana": semana + 1,
                "costo": round(monto, 2),
                "acumulado": round(acumulado, 2),
            }
        )
    return semanas


# ------------------------------------------------- Simulador "que pasa si"
def simular_reduccion(
    proyecto: Proyecto,
    reducciones: Dict[str, float],
) -> Proyecto:
    """Devuelve una copia del proyecto con actividades acortadas.

    La reduccion se aplica sobre el tiempo esperado ``te`` y se reparte de
    forma proporcional a a, m y b para conservar la forma de la distribucion
    PERT.
    """
    copia = copy.deepcopy(proyecto)
    for ida, dias in reducciones.items():
        actividad = copia.obtener(ida)
        if actividad is None or dias <= 0:
            continue
        te_actual = actividad.te
        if te_actual <= TOL:
            continue
        te_nueva = max(0.25, te_actual - dias)
        factor = te_nueva / te_actual
        actividad.optimista = round(actividad.optimista * factor, 2)
        actividad.probable = round(actividad.probable * factor, 2)
        actividad.pesimista = round(actividad.pesimista * factor, 2)
    return copia


def sugerencias_aceleracion(
    cpm: Dict[str, Any],
    reduccion_dias: float,
    max_sugerencias: int = 3,
) -> List[Dict[str, Any]]:
    """Propone que actividades criticas acortar para ganar los dias pedidos."""
    if reduccion_dias <= 0 or not cpm["filas"]:
        return []
    criticas = [fila for fila in cpm["filas"] if fila["critica"]]
    criticas.sort(key=lambda fila: fila["te"], reverse=True)
    sugerencias: List[Dict[str, Any]] = []
    pendiente = reduccion_dias
    for fila in criticas[:max_sugerencias]:
        if pendiente <= 0:
            break
        recorte = min(pendiente, max(fila["te"] * 0.35, 0.0))
        recorte = round(recorte, 1)
        if recorte <= 0:
            continue
        nueva_duracion = round(fila["te"] - recorte, 1)
        sugerencias.append(
            {
                "id": fila["id"],
                "nombre": fila["nombre"],
                "duracion_actual": fila["te"],
                "recorte_dias": recorte,
                "nueva_duracion": nueva_duracion,
                "mensaje": (
                    f"Reducir '{fila['nombre']}' de {fila['te']:.1f} a {nueva_duracion:.1f} dias "
                    f"(-{recorte:.1f} dias) contratando personal adicional o trabajando un turno extra."
                ),
            }
        )
        pendiente = round(pendiente - recorte, 2)
    return sugerencias


def estadisticas_holgura(cpm: Dict[str, Any]) -> Dict[str, Any]:
    filas = cpm["filas"]
    if not filas:
        return {"criticas": 0, "con_holgura": 0, "holgura_media": 0.0, "holgura_maxima": 0.0}
    holguras = [fila["holgura"] for fila in filas]
    return {
        "criticas": sum(1 for fila in filas if fila["critica"]),
        "con_holgura": sum(1 for fila in filas if not fila["critica"]),
        "holgura_media": round(sum(holguras) / len(holguras), 2),
        "holgura_maxima": round(max(holguras), 2),
    }
