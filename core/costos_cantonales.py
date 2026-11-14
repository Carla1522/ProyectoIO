"""Tarifas municipales por canton.

El escenario del proyecto declara un canton. Este modulo traduce el tramite y el
canton a la tarifa que corresponde a ese GAD, sin reutilizar valores de otra
ciudad. Cuando el canton no tiene tarifario cargado o el tramite no tiene tarifa
propia, se conserva el costo de referencia del catalogo y se devuelve una
advertencia explicita para que la interfaz y el informe lo declaren.

Solo se aplican tarifas para los conceptos publicados en
``parametros_ley.json -> tasas_cantonales``. No se extrapolan valores entre
cantones ni se inventan tarifas para tramites sin fuente.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

CANTON_POR_DEFECTO = "Ambato"


def lista_cantones(parametros: Dict[str, Any]) -> List[str]:
    """Cantones con tarifario declarado, en orden alfabetico."""
    return sorted((parametros.get("tasas_cantonales") or {}).keys())


def datos_canton(canton: Optional[str], parametros: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Devuelve el bloque del canton o ``None`` si no hay datos cargados."""
    if not isinstance(canton, str) or not canton.strip():
        return None
    return (parametros.get("tasas_cantonales") or {}).get(canton.strip())


def tarifas_disponibles(canton: Optional[str], parametros: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    datos = datos_canton(canton, parametros) or {}
    return dict(datos.get("tarifas") or {})


def resolver_tarifa(
    actividad: Any,
    escenario: Dict[str, Any],
    parametros: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Tarifa efectiva de una actividad cantonal.

    Devuelve ``None`` si la actividad no es un tramite cantonal. En caso
    contrario devuelve un diccionario con:

    ``aplica``
        True si se reemplaza el costo del catalogo por la tarifa del canton.
    ``costo``
        Monto resultante (siempre definido).
    ``origen``
        ``cantonal`` (tarifa del GAD) o ``catalogo`` (referencia nacional).
    ``advertencia``
        Texto para mostrar cuando el valor debe confirmarse o no hay datos.
    """
    nivel = str(getattr(actividad, "nivel", "") or "")
    if getattr(actividad, "tipo", "privada") != "tramite" or nivel != "cantonal":
        return None

    catalogo = float(getattr(actividad, "costo", 0.0) or 0.0)
    canton = str(escenario.get("canton") or "").strip()
    area = float(escenario.get("area_m2") or 0.0)
    datos = datos_canton(canton, parametros)

    base: Dict[str, Any] = {
        "canton": canton,
        "aplica": False,
        "costo": catalogo,
        "origen": "catalogo",
        "unidad": "tramite",
        "concepto": "",
        "nota": "",
        "fuente_url": (datos or {}).get("fuente_url", ""),
        "fuente_normativa": (datos or {}).get("fuente_normativa", ""),
        "verificado": bool((datos or {}).get("verificado")),
        "advertencia": None,
    }

    if datos is None:
        base["advertencia"] = (
            f"No hay tarifario cargado para el canton '{canton or 'sin definir'}'. "
            "Se usa el costo de referencia del catalogo; confirma la tasa en el GAD."
        )
        return base

    tarifa = (datos.get("tarifas") or {}).get(getattr(actividad, "id", ""))
    if not isinstance(tarifa, dict):
        base["advertencia"] = (
            f"'{getattr(actividad, 'nombre', 'la actividad')}' no tiene tarifa "
            f"especifica en {canton}: se conserva el costo de referencia del catalogo."
        )
        return base

    unidad = str(tarifa.get("unidad") or "tramite")
    valor = float(tarifa.get("valor") or 0.0)
    if unidad == "m2":
        if area <= 0:
            base["advertencia"] = (
                f"La tasa de {canton} se calcula por m2 y el area declarada es 0. "
                "Indica el area en el escenario para aplicarla; por ahora se usa el "
                "costo de referencia del catalogo."
            )
            return base
        monto = valor * area
        detalle = f"USD {valor:.2f}/m2 x {area:.2f} m2"
    else:
        monto = valor
        rango = tarifa.get("rango")
        detalle = (
            f"USD {valor:.2f} (rango referencial {float(rango[0]):.2f}-{float(rango[1]):.2f})"
            if isinstance(rango, list) and len(rango) == 2
            else f"USD {valor:.2f}"
        )

    base.update(
        {
            "aplica": True,
            "costo": round(monto, 2),
            "origen": "cantonal",
            "unidad": unidad,
            "concepto": str(tarifa.get("concepto") or ""),
            "nota": f"{detalle}. {tarifa.get('nota') or ''}".strip(),
            "advertencia": (
                f"Tarifa de referencia de {canton}; confirmar el tarifario vigente "
                "en la ordenanza municipal antes de presentar el presupuesto."
            ),
        }
    )
    return base


def resumen_canton(canton: Optional[str], parametros: Dict[str, Any]) -> Dict[str, Any]:
    """Datos del canton para mostrar en la interfaz."""
    datos = datos_canton(canton, parametros)
    if datos is None:
        return {
            "canton": canton or "",
            "disponible": False,
            "entidad": "",
            "fuente_url": "",
            "fuente_normativa": "",
            "verificado": False,
            "verificado_en": "",
            "tarifas": {},
            "notas": "Sin tarifario cargado para este canton.",
        }
    return {
        "canton": canton or "",
        "disponible": True,
        "entidad": datos.get("entidad", ""),
        "fuente_url": datos.get("fuente_url", ""),
        "fuente_normativa": datos.get("fuente_normativa", ""),
        "verificado": bool(datos.get("verificado")),
        "verificado_en": datos.get("verificado_en", ""),
        "tarifas": dict(datos.get("tarifas") or {}),
        "notas": datos.get("notas", ""),
        "fuente_tipo": datos.get("fuente_tipo", ""),
    }
