"""Importacion unificada de proyectos desde JSON, Excel (.xlsx), CSV (.csv) y PDF (.pdf).

Todos los formatos pasan por normalizacion de columnas, validacion de limites
(``core.seguridad``) y construccion segura de :class:`core.modelo.Proyecto`.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from core.modelo import Actividad, Proyecto, cargar_base_ecuador, nuevo_id
from core.seguridad import (
    LIMITE_BYTES,
    ErrorDatos,
    cargar_json_bytes,
    validar_proyecto_json,
)

FORMATOS_SOPORTADOS = ("json", "xlsx", "csv", "pdf")
MAX_PAGINAS_PDF = 50

_MAPA_COLUMNAS: Dict[str, str] = {
    "id": "id",
    "identificador": "id",
    "codigo": "codigo",
    "cod": "codigo",
    "actividad": "nombre",
    "nombre": "nombre",
    "tarea": "nombre",
    "descripcion": "nombre",
    "tipo": "tipo",
    "predecesoras": "predecesoras",
    "predecesora": "predecesoras",
    "dependencias": "predecesoras",
    "depende_de": "predecesoras",
    "preds": "predecesoras",
    "a": "optimista",
    "optimista": "optimista",
    "a_optimista": "optimista",
    "t_opt": "optimista",
    "m": "probable",
    "probable": "probable",
    "m_probable": "probable",
    "t_prob": "probable",
    "b": "pesimista",
    "pesimista": "pesimista",
    "b_pesimista": "pesimista",
    "t_pes": "pesimista",
    "te": "te",
    "duracion": "te",
    "dias": "te",
    "costo_usd": "costo",
    "costo": "costo",
    "costo_directo": "costo",
    "costo_directo_usd": "costo",
    "costos_directos": "costo",
    "costo_total_usd": "costo",
    "equipos_usd": "costo_equipos",
    "equipos": "costo_equipos",
    "costo_equipos": "costo_equipos",
    "trabajadores": "trabajadores",
    "personal": "trabajadores",
    "empleados": "trabajadores",
    "costo_mo_dia": "costo_mo_diario",
    "mo_dia": "costo_mo_diario",
    "costo_mo_diario": "costo_mo_diario",
    "iva": "grava_iva",
    "iva_15": "grava_iva",
    "grava_iva": "grava_iva",
    "entidad": "entidad",
    "institucion": "entidad",
}


def _normalizar_clave(texto: Any) -> str:
    crudo = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", crudo).strip("_").lower()


def _limpiar_celda(valor: Any) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).split())


def _numero(valor: Any, defecto: float = 0.0) -> float:
    if valor is None:
        return defecto
    if isinstance(valor, (int, float)):
        return max(float(valor), 0.0)
    texto = str(valor).strip()
    if not texto or texto in ("-", "—"):
        return defecto
    limpio = re.sub(r"[^0-9,.\-]", "", texto)
    if not limpio:
        return defecto
    if "," in limpio and "." in limpio:
        if limpio.rfind(",") > limpio.rfind("."):
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    elif "," in limpio:
        partes = limpio.split(",")
        if len(partes) == 2 and len(partes[1]) <= 2:
            limpio = limpio.replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    try:
        return max(float(limpio), 0.0)
    except ValueError:
        return defecto


def _booleano(valor: Any, defecto: bool = True) -> bool:
    if valor is None or valor == "":
        return defecto
    if isinstance(valor, bool):
        return valor
    texto = _normalizar_clave(valor)
    if texto in ("si", "yes", "true", "1", "s", "y"):
        return True
    if texto in ("no", "false", "0", "n"):
        return False
    return defecto


def _mapear_encabezados(fila: List[Any]) -> Dict[int, str]:
    mapa: Dict[int, str] = {}
    for indice, celda in enumerate(fila):
        clave = _normalizar_clave(celda)
        campo = _MAPA_COLUMNAS.get(clave)
        if campo and campo not in mapa.values():
            mapa[indice] = campo
    return mapa


def _es_fila_encabezado(fila: List[Any]) -> bool:
    mapa = _mapear_encabezados(fila)
    campos = set(mapa.values())
    return "nombre" in campos and bool(
        campos & {"id", "codigo", "optimista", "probable", "pesimista", "te", "costo", "predecesoras"}
    )


def _catalogo_por_nombre() -> Dict[str, Dict[str, Any]]:
    try:
        base = cargar_base_ecuador()
    except Exception:
        return {}
    return {_normalizar_clave(t.get("nombre")): t for t in base.get("tramites", [])}


def _construir_proyecto_desde_filas(
    filas: List[Dict[str, Any]],
    nombre_proyecto: str,
    canton: str = "Ambato",
) -> Tuple[Proyecto, List[str]]:
    if not filas:
        raise ErrorDatos("No se encontraron actividades validas en el archivo.")

    catalogo_nombre = _catalogo_por_nombre()
    try:
        catalogo_id = {t["id"]: t for t in cargar_base_ecuador().get("tramites", [])}
    except Exception:
        catalogo_id = {}

    proyecto = Proyecto(
        nombre=nombre_proyecto or "Proyecto importado",
        escenario={
            "canton": canton or "Ambato",
            "tamano_empresa": "micro",
            "tipo_personeria": "persona_natural",
            "regimen_tributario": "general",
            "area_m2": 0.0,
            "aplica_iva": False,
        },
    )
    advertencias: List[str] = []
    codigos_a_id: Dict[str, str] = {}
    existentes: List[str] = []
    sin_tiempos_pert = 0

    for fila in filas:
        nombre = _limpiar_celda(fila.get("nombre"))
        if not nombre:
            continue
        tipo = _normalizar_clave(fila.get("tipo"))
        if tipo not in ("privada", "tramite"):
            tipo = "privada"

        id_bruto = _limpiar_celda(fila.get("id"))
        codigo_bruto = _limpiar_celda(fila.get("codigo"))
        registro = catalogo_id.get(id_bruto) or (
            catalogo_nombre.get(_normalizar_clave(nombre)) if tipo == "tramite" else None
        )

        if id_bruto:
            ida = id_bruto
        elif registro is not None:
            ida = registro["id"]
        elif codigo_bruto:
            ida = codigo_bruto
        else:
            ida = nuevo_id(nombre, existentes)

        if ida in existentes:
            ida = nuevo_id(nombre, existentes)
        existentes.append(ida)
        if codigo_bruto:
            codigos_a_id[codigo_bruto] = ida

        tiene_pert = any(fila.get(k) not in (None, "") for k in ("optimista", "probable", "pesimista"))
        if tiene_pert:
            a = _numero(fila.get("optimista"), 1.0)
            m = _numero(fila.get("probable"), max(a, 1.0))
            b = _numero(fila.get("pesimista"), max(m, a))
            a, m, b = sorted((a, m, b))
        else:
            te = _numero(fila.get("te"), 1.0)
            a = m = b = te
            sin_tiempos_pert += 1

        preds_raw = [
            p.strip()
            for p in re.split(r"[,;]+", str(fila.get("predecesoras") or ""))
            if p.strip() and p.strip() not in ("-", "—")
        ]

        actividad = (
            Actividad.desde_catalogo(registro, predecesoras=preds_raw)
            if registro is not None and tipo == "tramite"
            else Actividad(id=ida, nombre=nombre, tipo=tipo, predecesoras=preds_raw)
        )
        actividad.id = ida
        actividad.nombre = nombre
        actividad.tipo = tipo
        actividad.optimista = a
        actividad.probable = m
        actividad.pesimista = b
        if fila.get("costo") not in (None, ""):
            actividad.costo = _numero(fila.get("costo"))
        if fila.get("costo_equipos") not in (None, ""):
            actividad.costo_equipos = _numero(fila.get("costo_equipos"))
        if fila.get("trabajadores") not in (None, ""):
            actividad.trabajadores = int(_numero(fila.get("trabajadores")))
        if fila.get("costo_mo_diario") not in (None, ""):
            actividad.costo_mo_diario = _numero(fila.get("costo_mo_diario"))
        if fila.get("entidad") not in (None, "") and _limpiar_celda(fila.get("entidad")) not in ("-", "—"):
            actividad.entidad = _limpiar_celda(fila.get("entidad"))
        actividad.grava_iva = (
            False
            if tipo == "tramite"
            else _booleano(fila.get("grava_iva"), True)
        )
        actividad.origen = "importado"
        proyecto.agregar(actividad)

    for actividad in proyecto.actividades.values():
        actividad.predecesoras = [
            codigos_a_id.get(pred, pred) if pred not in proyecto.actividades else pred
            for pred in actividad.predecesoras
        ]

    if sin_tiempos_pert:
        advertencias.append(
            f"{sin_tiempos_pert} actividad(es) no tenian columnas (a, m, b) y se importaron "
            "con duracion determinista (a = m = b)."
        )

    datos_validados = validar_proyecto_json(proyecto.to_dict())
    return Proyecto.from_dict(datos_validados), advertencias


def _importar_csv(contenido: bytes, nombre_archivo: str) -> Tuple[Proyecto, List[str]]:
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")

    muestra = "\n".join(texto.splitlines()[:10])
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
        delimitador = dialecto.delimiter
    except csv.Error:
        delimitador = ";" if muestra.count(";") > muestra.count(",") else ","

    lector = list(csv.reader(io.StringIO(texto), delimiter=delimitador))
    indice_header = next((i for i, fila in enumerate(lector) if _es_fila_encabezado(fila)), None)
    if indice_header is None:
        raise ErrorDatos(
            "El archivo CSV no contiene columnas reconocibles (ej: ID, Actividad, Predecesoras, a, m, b)."
        )

    mapa = _mapear_encabezados(lector[indice_header])
    filas: List[Dict[str, Any]] = []
    for cruda in lector[indice_header + 1 :]:
        if not any(_limpiar_celda(c) for c in cruda):
            continue
        item = {campo: cruda[idx] for idx, campo in mapa.items() if idx < len(cruda)}
        if _limpiar_celda(item.get("nombre")):
            filas.append(item)

    base_nombre = re.sub(r"\.[^.]+$", "", nombre_archivo).replace("_", " ").strip()
    return _construir_proyecto_desde_filas(filas, base_nombre or "Proyecto CSV")


def _importar_xlsx(contenido: bytes, nombre_archivo: str) -> Tuple[Proyecto, List[str]]:
    from openpyxl import load_workbook

    try:
        libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception as error:
        raise ErrorDatos(f"No se pudo abrir el archivo Excel: {error}") from error

    try:
        nombre_proyecto = re.sub(r"\.[^.]+$", "", nombre_archivo).replace("_", " ").strip()
        canton = "Ambato"
        if "Resumen" in libro.sheetnames:
            for fila in libro["Resumen"].iter_rows(values_only=True):
                texto = _limpiar_celda(fila[0]) if fila else ""
                if texto.startswith("Proyecto:"):
                    nombre_proyecto = texto.split(":", 1)[1].strip() or nombre_proyecto
                elif texto.startswith("Canton del escenario:"):
                    canton = texto.split(":", 1)[1].strip() or canton

        hoja_objetivo = None
        if "Actividades CPM" in libro.sheetnames:
            hoja_objetivo = libro["Actividades CPM"]
        else:
            for nombre_hoja in libro.sheetnames:
                hoja = libro[nombre_hoja]
                if any(_es_fila_encabezado(list(r)) for _, r in zip(range(15), hoja.iter_rows(values_only=True))):
                    hoja_objetivo = hoja
                    break
        if hoja_objetivo is None:
            raise ErrorDatos(
                "No se encontro una tabla de actividades valida en el Excel "
                "(requiere columnas como Actividad, a, m, b o Predecesoras)."
            )

        todas_filas = list(hoja_objetivo.iter_rows(values_only=True))
        indice_header = next((i for i, r in enumerate(todas_filas) if _es_fila_encabezado(list(r))), None)
        if indice_header is None:
            raise ErrorDatos("No se encontraron encabezados validos en el archivo Excel.")

        mapa = _mapear_encabezados(list(todas_filas[indice_header]))
        filas: List[Dict[str, Any]] = []
        for cruda in todas_filas[indice_header + 1 :]:
            if not any(_limpiar_celda(c) for c in cruda):
                continue
            item = {campo: cruda[idx] for idx, campo in mapa.items() if idx < len(cruda)}
            if _limpiar_celda(item.get("nombre")):
                filas.append(item)

        if "Presupuesto" in libro.sheetnames:
            presup_rows = list(libro["Presupuesto"].iter_rows(values_only=True))
            idx_p = next((i for i, r in enumerate(presup_rows) if _es_fila_encabezado(list(r))), None)
            if idx_p is not None:
                mapa_p = _mapear_encabezados(list(presup_rows[idx_p]))
                por_id: Dict[str, Dict[str, Any]] = {}
                for cruda in presup_rows[idx_p + 1 :]:
                    item_p = {campo: cruda[idx] for idx, campo in mapa_p.items() if idx < len(cruda)}
                    clave_id = _limpiar_celda(item_p.get("id") or item_p.get("nombre"))
                    if clave_id:
                        por_id[clave_id] = item_p
                for fila in filas:
                    clave = _limpiar_celda(fila.get("id") or fila.get("nombre"))
                    if clave in por_id:
                        if por_id[clave].get("costo") not in (None, ""):
                            fila["costo"] = por_id[clave]["costo"]
                        if por_id[clave].get("costo_equipos") not in (None, ""):
                            fila["costo_equipos"] = por_id[clave]["costo_equipos"]
    finally:
        libro.close()

    return _construir_proyecto_desde_filas(filas, nombre_proyecto, canton=canton)


def _importar_pdf(contenido: bytes, nombre_archivo: str) -> Tuple[Proyecto, List[str]]:
    try:
        import pdfplumber
    except ImportError as error:
        raise ErrorDatos("Falta la libreria 'pdfplumber' para leer archivos PDF.") from error

    try:
        pdf = pdfplumber.open(io.BytesIO(contenido))
    except Exception as error:
        raise ErrorDatos(f"No se pudo leer el archivo PDF: {error}") from error

    nombre_proyecto = re.sub(r"\.[^.]+$", "", nombre_archivo).replace("_", " ").strip()
    canton = "Ambato"
    filas: List[Dict[str, Any]] = []
    texto_total = ""

    with pdf:
        if len(pdf.pages) > MAX_PAGINAS_PDF:
            raise ErrorDatos(f"El PDF supera el limite permitido de {MAX_PAGINAS_PDF} paginas.")

        for num, pagina in enumerate(pdf.pages):
            texto_pag = pagina.extract_text() or ""
            texto_total += texto_pag
            if num == 0:
                for linea in texto_pag.splitlines():
                    if linea.startswith("Proyecto:"):
                        nombre_proyecto = linea.split(":", 1)[1].strip() or nombre_proyecto
                    elif linea.startswith("Canton del escenario:"):
                        canton = linea.split(":", 1)[1].strip() or canton

            tablas = pagina.extract_tables() or []
            if not tablas:
                tablas = pagina.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"}) or []

            for tabla in tablas:
                if not tabla:
                    continue
                limpia = [[_limpiar_celda(c) for c in fila] for fila in tabla]
                idx_h = next((i for i, r in enumerate(limpia) if _es_fila_encabezado(r)), None)
                if idx_h is None:
                    continue
                mapa = _mapear_encabezados(limpia[idx_h])
                # Evitar tablas secundarias como "Ruta critica" o "Presupuesto" si ya
                # tenemos la tabla principal con duraciones PERT/CPM.
                campos_tabla = set(mapa.values())
                if not (campos_tabla & {"optimista", "probable", "pesimista", "te"}):
                    continue
                for cruda in limpia[idx_h + 1 :]:
                    if not any(cruda) or _es_fila_encabezado(cruda):
                        continue
                    item = {campo: cruda[idx] for idx, campo in mapa.items() if idx < len(cruda)}
                    if _limpiar_celda(item.get("nombre")):
                        filas.append(item)

    if not filas:
        if not texto_total.strip():
            raise ErrorDatos(
                "El PDF parece ser una imagen escaneada sin texto seleccionable; "
                "usa JSON, Excel (.xlsx) o CSV (.csv)."
            )
        raise ErrorDatos(
            "No se encontro una tabla de actividades con duraciones en el PDF."
        )

    proyecto, advertencias = _construir_proyecto_desde_filas(filas, nombre_proyecto, canton=canton)
    advertencias.insert(
        0,
        "Importado desde PDF: verifica en Tabla de Actividades las predecesoras, "
        "tiempos (a, m, b) y costos.",
    )
    return proyecto, advertencias


def plantilla_excel() -> bytes:
    """Genera una plantilla Excel minima lista para llenar e importar."""
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Actividades"
    hoja.append([
        "ID", "Actividad", "Tipo", "Predecesoras", "a", "m", "b",
        "Costo USD", "Equipos USD", "Trabajadores", "Costo MO/dia", "IVA",
    ])
    hoja.append(["A", "Diseno inicial", "privada", "", 2, 4, 6, 500, 0, 1, 25, "SI"])
    hoja.append(["B", "Ejecucion", "privada", "A", 4, 7, 12, 1800, 300, 2, 22, "SI"])
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def importar_archivo(nombre_archivo: str, contenido: bytes) -> Tuple[Proyecto, str, List[str]]:
    """Importa un proyecto desde JSON, XLSX, CSV o PDF aplicando limites de seguridad."""
    if not isinstance(contenido, (bytes, bytearray)) or not contenido:
        raise ErrorDatos("El archivo esta vacio.")
    if len(contenido) > LIMITE_BYTES:
        raise ErrorDatos(f"El archivo supera el limite de {LIMITE_BYTES // 1_000_000} MB.")

    ext = nombre_archivo.rsplit(".", 1)[-1].lower() if "." in nombre_archivo else ""
    if ext not in FORMATOS_SOPORTADOS:
        raise ErrorDatos(
            f"Formato '.{ext}' no soportado. Usa JSON, Excel (.xlsx), CSV (.csv) o PDF (.pdf)."
        )

    raw = bytes(contenido)
    if ext == "json":
        datos = validar_proyecto_json(cargar_json_bytes(raw))
        return Proyecto.from_dict(datos), "json", []
    if ext == "csv":
        proyecto, avisos = _importar_csv(raw, nombre_archivo)
        return proyecto, "csv", avisos
    if ext == "xlsx":
        proyecto, avisos = _importar_xlsx(raw, nombre_archivo)
        return proyecto, "xlsx", avisos

    proyecto, avisos = _importar_pdf(raw, nombre_archivo)
    return proyecto, "pdf", avisos
