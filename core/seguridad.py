"""Utilidades de seguridad para la interfaz y la carga de archivos.

Tres frentes:

* Texto que se inyecta con ``unsafe_allow_html``: todo valor dinamico debe pasar
  por :func:`escapar` antes de llegar al HTML.
* Enlaces externos: :func:`url_segura` solo admite http/https y descarta
  esquemas ejecutables (``javascript:``, ``data:``) o credenciales embebidas.
* Archivos JSON: :func:`cargar_json_bytes` y :func:`validar_proyecto_json`
  limitan tamano, profundidad y tipos antes de construir el modelo. Asi un
  archivo manipulado no puede inyectar estructuras invalidas ni valores no
  finitos en el motor de calculo.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, Iterable, List
from urllib.parse import urlsplit

LIMITE_BYTES = 2_000_000
MAX_PROFUNDIDAD = 20
MAX_ACTIVIDADES = 500
MAX_PREDECESORAS = 200
MAX_TEXTO = 4_000

# Se acepta cualquier texto imprimible corto: el editor permite escribir IDs y
# el escapado de HTML ya cubre la salida. Solo se rechazan caracteres de control.
ID_VALIDO = re.compile(r"^[^\x00-\x1f\x7f]{1,64}$")
TAMANOS_EMPRESA = ("micro", "pequena", "mediana", "grande")
CAMPOS_ESCENARIO = {
    "canton",
    "tamano_empresa",
    "area_m2",
    "aplica_iva",
    "empleados",
    "admin_pct",
}


class ErrorDatos(ValueError):
    """El archivo no cumple el esquema esperado o excede los limites."""


# ------------------------------------------------------------------ HTML/URLs
def escapar(valor: Any) -> str:
    """Escapa un valor dinamico para insertarlo en HTML."""
    texto = "" if valor is None else str(valor)
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def url_segura(url: Any) -> str:
    """Devuelve la URL si es http/https valida; en caso contrario, cadena vacia."""
    if not isinstance(url, str):
        return ""
    limpia = url.strip()
    if not limpia or len(limpia) > 2048:
        return ""
    if any(caracter in limpia for caracter in ("\n", "\r", "\t", " ")):
        return ""
    try:
        partes = urlsplit(limpia)
    except ValueError:
        return ""
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return ""
    if partes.username or partes.password:
        return ""
    if "@" in partes.netloc:
        return ""
    return limpia


def sanitizar_nombre_archivo(nombre: Any, defecto: str = "proyecto") -> str:
    """Genera un nombre de archivo sin rutas ni caracteres de control."""
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", str(nombre or "")).strip("_")
    return (base[:60] or defecto) + ".json"


# ---------------------------------------------------------------------- JSON
def _rechazar_constante(valor: str) -> None:
    raise ErrorDatos(f"El archivo contiene un valor no permitido: {valor}.")


def _profundidad(objeto: Any, nivel: int = 1) -> int:
    if nivel > MAX_PROFUNDIDAD:
        raise ErrorDatos("El archivo tiene demasiados niveles de anidamiento.")
    if isinstance(objeto, dict):
        return max((_profundidad(v, nivel + 1) for v in objeto.values()), default=nivel)
    if isinstance(objeto, list):
        return max((_profundidad(v, nivel + 1) for v in objeto), default=nivel)
    return nivel


def cargar_json_bytes(contenido: bytes) -> Dict[str, Any]:
    """Decodifica y valida el contenedor JSON de un proyecto."""
    if not isinstance(contenido, (bytes, bytearray)):
        raise ErrorDatos("El contenido recibido no es un archivo valido.")
    if not contenido:
        raise ErrorDatos("El archivo esta vacio.")
    if len(contenido) > LIMITE_BYTES:
        raise ErrorDatos(
            f"El archivo supera el limite de {LIMITE_BYTES // 1_000_000} MB."
        )
    try:
        texto = bytes(contenido).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ErrorDatos("El archivo no esta codificado en UTF-8.") from error
    try:
        datos = json.loads(texto, parse_constant=_rechazar_constante)
    except json.JSONDecodeError as error:
        raise ErrorDatos(
            f"JSON mal formado en la linea {error.lineno}, columna {error.colno}."
        ) from error
    if not isinstance(datos, dict):
        raise ErrorDatos("La raiz del archivo debe ser un objeto JSON.")
    _profundidad(datos)
    return datos


def _texto(valor: Any, campo: str, maximo: int = MAX_TEXTO, obligatorio: bool = False) -> str:
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise ErrorDatos(f"El campo '{campo}' debe ser texto.")
    limpio = valor.strip()
    if obligatorio and not limpio:
        raise ErrorDatos(f"El campo '{campo}' no puede estar vacio.")
    if len(limpio) > maximo:
        raise ErrorDatos(f"El campo '{campo}' supera {maximo} caracteres.")
    return limpio


def _numero(
    valor: Any,
    campo: str,
    minimo: float = 0.0,
    maximo: float = 1_000_000_000.0,
    defecto: float = 0.0,
) -> float:
    if valor is None or valor == "":
        return defecto
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorDatos(f"El campo '{campo}' debe ser numerico.")
    numero = float(valor)
    if not math.isfinite(numero):
        raise ErrorDatos(f"El campo '{campo}' debe ser un numero finito.")
    if numero < minimo or numero > maximo:
        raise ErrorDatos(
            f"El campo '{campo}' esta fuera del rango permitido "
            f"({minimo:g} a {maximo:g})."
        )
    return numero


def _identificador(valor: Any, campo: str) -> str:
    texto = _texto(valor, campo, maximo=64, obligatorio=True)
    if not ID_VALIDO.match(texto):
        raise ErrorDatos(
            f"El identificador '{texto[:30]}' no es valido: no puede contener "
            "caracteres de control ni superar 64 caracteres."
        )
    return texto


def _lista_textos(valor: Any, campo: str, maximo: int) -> List[str]:
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise ErrorDatos(f"El campo '{campo}' debe ser una lista.")
    if len(valor) > maximo:
        raise ErrorDatos(f"El campo '{campo}' supera {maximo} elementos.")
    return [str(elemento).strip()[:200] for elemento in valor if str(elemento).strip()]


def _escenario(valor: Any) -> Dict[str, Any]:
    if valor is None:
        return {}
    if not isinstance(valor, dict):
        raise ErrorDatos("El campo 'escenario' debe ser un objeto.")
    limpio: Dict[str, Any] = {}
    for clave, dato in valor.items():
        if clave not in CAMPOS_ESCENARIO:
            continue
        if clave == "canton":
            limpio[clave] = _texto(dato, "escenario.canton", maximo=80)
        elif clave == "tamano_empresa":
            tamano = _texto(dato, "escenario.tamano_empresa", maximo=20)
            limpio[clave] = tamano if tamano in TAMANOS_EMPRESA else "micro"
        elif clave == "aplica_iva":
            if not isinstance(dato, bool):
                raise ErrorDatos("El campo 'escenario.aplica_iva' debe ser booleano.")
            limpio[clave] = dato
        elif clave == "area_m2":
            limpio[clave] = _numero(dato, "escenario.area_m2", 0.0, 1_000_000.0)
        elif clave == "empleados":
            limpio[clave] = int(_numero(dato, "escenario.empleados", 0, 100_000))
        elif clave == "admin_pct":
            limpio[clave] = _numero(dato, "escenario.admin_pct", 0.0, 100.0)
    return limpio


def validar_proyecto_json(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza el JSON de un proyecto y rechaza contenido invalido.

    Devuelve un diccionario con la misma forma que ``Proyecto.to_dict`` pero con
    tipos garantizados. No conoce el modelo de dominio para evitar importaciones
    circulares.
    """
    if not isinstance(datos, dict):
        raise ErrorDatos("La raiz del archivo debe ser un objeto JSON.")

    actividades_brutas = datos.get("actividades", [])
    if actividades_brutas is None:
        actividades_brutas = []
    if not isinstance(actividades_brutas, list):
        raise ErrorDatos("El campo 'actividades' debe ser una lista.")
    if len(actividades_brutas) > MAX_ACTIVIDADES:
        raise ErrorDatos(f"El proyecto supera {MAX_ACTIVIDADES} actividades.")

    actividades: List[Dict[str, Any]] = []
    vistos: set[str] = set()
    for indice, bruto in enumerate(actividades_brutas, start=1):
        if not isinstance(bruto, dict):
            raise ErrorDatos(f"La actividad #{indice} debe ser un objeto JSON.")
        ida = _identificador(bruto.get("id"), f"actividades[{indice}].id")
        if ida in vistos:
            raise ErrorDatos(f"El identificador '{ida}' esta repetido.")
        vistos.add(ida)
        tipo = _texto(bruto.get("tipo"), "tipo", maximo=20) or "privada"
        costos_tamano = bruto.get("costos_por_tamano")
        if costos_tamano is not None and not isinstance(costos_tamano, dict):
            raise ErrorDatos("El campo 'costos_por_tamano' debe ser un objeto.")
        actividades.append(
            {
                "id": ida,
                "nombre": _texto(
                    bruto.get("nombre"), f"actividades[{indice}].nombre",
                    maximo=300, obligatorio=True,
                ),
                "tipo": tipo if tipo in ("privada", "tramite") else "privada",
                "descripcion": _texto(bruto.get("descripcion"), "descripcion"),
                "predecesoras": [
                    _identificador(p, "predecesora")
                    for p in _lista_textos(
                        bruto.get("predecesoras"), "predecesoras", MAX_PREDECESORAS
                    )
                ],
                "optimista": _numero(bruto.get("optimista"), "optimista", 0, 100_000),
                "probable": _numero(bruto.get("probable"), "probable", 0, 100_000),
                "pesimista": _numero(bruto.get("pesimista"), "pesimista", 0, 100_000),
                "costo": _numero(bruto.get("costo"), "costo", 0, 1_000_000_000),
                "costo_equipos": _numero(bruto.get("costo_equipos"), "costo_equipos", 0),
                "costo_nota": _texto(bruto.get("costo_nota"), "costo_nota", 1_000),
                "entidad": _texto(bruto.get("entidad"), "entidad", 300),
                "categoria": _texto(bruto.get("categoria"), "categoria", 100),
                "nivel": _texto(bruto.get("nivel"), "nivel", 30),
                "fuente_normativa": _texto(bruto.get("fuente_normativa"), "fuente_normativa", 500),
                "fuente_url": url_segura(bruto.get("fuente_url")),
                "requisitos": _lista_textos(bruto.get("requisitos"), "requisitos", 60),
                "costo_base": (
                    None
                    if bruto.get("costo_base") in (None, "")
                    else _numero(bruto.get("costo_base"), "costo_base", 0)
                ),
                "costo_por_m2": _numero(bruto.get("costo_por_m2"), "costo_por_m2", 0),
                "costos_por_tamano": {
                    str(clave): _numero(valor, f"costos_por_tamano.{clave}", 0)
                    for clave, valor in (costos_tamano or {}).items()
                },
                "costo_descuento_pyme": (
                    None
                    if bruto.get("costo_descuento_pyme") in (None, "")
                    else _numero(bruto.get("costo_descuento_pyme"), "costo_descuento_pyme", 0)
                ),
                "trabajadores": int(_numero(bruto.get("trabajadores"), "trabajadores", 0, 100_000)),
                "costo_mo_diario": _numero(bruto.get("costo_mo_diario"), "costo_mo_diario", 0, 100_000),
                "origen": _texto(bruto.get("origen"), "origen", 30) or "manual",
                "notas": _texto(bruto.get("notas"), "notas", 2_000),
            }
        )

    return {
        "nombre": _texto(datos.get("nombre"), "nombre", 200) or "Proyecto sin titulo",
        "descripcion": _texto(datos.get("descripcion"), "descripcion"),
        "escenario": _escenario(datos.get("escenario")),
        "actividades": actividades,
    }


def es_identificador_valido(valor: Any) -> bool:
    return isinstance(valor, str) and bool(ID_VALIDO.match(valor.strip()))


def ids_desconocidos(referencias: Iterable[str], existentes: Iterable[str]) -> List[str]:
    """Referencias que no existen en el conjunto dado, sin duplicados."""
    disponibles = set(existentes)
    return sorted({r for r in referencias if r not in disponibles})
