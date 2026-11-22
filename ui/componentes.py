"""Componentes de interfaz reutilizables (Streamlit).

La interfaz no calcula nada por su cuenta: pide el resultado al motor y se
limita a presentarlo. El unico lugar donde se acepta un plan del copiloto es
la vista de aprobacion, que reconstruye el proyecto y lo valida antes de
reemplazar la tabla actual.

Reglas de esta capa:

* Todo texto dinamico se escapa antes de inyectarse como HTML.
* Los enlaces externos pasan por ``url_segura``.
* El JSON de usuario se valida con ``core.seguridad`` antes de crear el modelo.
* Los editores usan una clave por revision del proyecto para que cargar otro
  archivo no reutilice el estado del editor anterior.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from core.calculos_cpm_pert import CicloError, calcular_cpm
from core.costos_cantonales import lista_cantones, resumen_canton
from core.modelo import (
    Actividad,
    Proyecto,
    cargar_base_ecuador,
    cargar_parametros,
    catalogo_por_id,
    nuevo_id,
)
from core.seguridad import (
    ID_VALIDO,
    ErrorDatos,
    escapar,
    sanitizar_nombre_archivo,
    url_segura,
)
from core.validador import (
    ADVERTENCIA,
    ERROR,
    INFO,
    Problema,
    hay_errores,
    validar,
)
from services import copiloto_ia, importador
from ui.estilos import badge, seccion

COLUMNAS_EDITABLES = [
    "ID", "Actividad", "Tipo", "Predecesoras", "a", "m", "b",
    "Costo USD", "Equipos USD", "IVA", "Trabajadores", "Costo MO/dia", "Entidad",
]


# --------------------------------------------------------------- Estado global
def nuevo_proyecto_sesion(proyecto: Proyecto, reiniciar_chat: bool = False) -> None:
    """Reemplaza el proyecto y aisla los widgets del proyecto anterior."""
    st.session_state["proyecto"] = proyecto
    st.session_state["_proyecto_revision"] = int(
        st.session_state.get("_proyecto_revision", 0)
    ) + 1
    st.session_state.pop("plan_pendiente", None)
    if reiniciar_chat:
        st.session_state["chat"] = []


def revision_actual() -> int:
    return int(st.session_state.get("_proyecto_revision", 0))


# ------------------------------------------------------------------ Escenario
def sidebar_escenario(proyecto: Proyecto) -> Dict[str, Any]:
    parametros = cargar_parametros()
    escenario = dict(proyecto.escenario)
    rev = revision_actual()
    st.sidebar.markdown("#### Escenario")
    st.sidebar.caption("Las tasas y supuestos se recalculan al cambiar un valor.")

    cantones = lista_cantones(parametros)
    canton_actual = str(escenario.get("canton") or "Ambato")
    if canton_actual not in cantones:
        cantones.append(canton_actual)
    escenario["canton"] = st.sidebar.selectbox(
        "Canton",
        cantones,
        index=cantones.index(canton_actual),
        key=f"sc_canton_{rev}",
        help=(
            "Determina las tarifas municipales. Cada canton usa su propio "
            "tarifario; no se trasladan valores entre ciudades."
        ),
    )

    tamanos = ["micro", "pequena", "mediana", "grande"]
    tamano_actual = escenario.get("tamano_empresa", "micro")
    if tamano_actual not in tamanos:
        tamano_actual = "micro"
    escenario["tamano_empresa"] = st.sidebar.selectbox(
        "Tamano de empresa",
        tamanos,
        index=tamanos.index(tamano_actual),
        key=f"sc_tamano_{rev}",
        help="Afecta tasas de ARCSA, ACESS y descuentos PYME.",
    )

    personerias = ["persona_natural", "sas", "compania"]
    etiquetas_personeria = {
        "persona_natural": "Persona natural",
        "sas": "Sociedad (S.A.S.)",
        "compania": "Compania (Cia. Ltda. / S.A.)",
    }
    pers_actual = str(escenario.get("tipo_personeria") or "persona_natural")
    if pers_actual not in personerias:
        pers_actual = "persona_natural"
    escenario["tipo_personeria"] = st.sidebar.selectbox(
        "Personeria juridica",
        personerias,
        index=personerias.index(pers_actual),
        format_func=lambda v: etiquetas_personeria.get(v, v),
        key=f"sc_personeria_{rev}",
        help="Define si requiere constitucion societaria y nombramiento en Supercias.",
    )

    regimenes = ["general", "rimpe_emprendedor", "rimpe_negocio_popular"]
    etiquetas_regimen = {
        "general": "Regimen General",
        "rimpe_emprendedor": "RIMPE Emprendedor",
        "rimpe_negocio_popular": "RIMPE Negocio Popular",
    }
    reg_actual = str(escenario.get("regimen_tributario") or "general")
    if reg_actual not in regimenes:
        reg_actual = "general"
    escenario["regimen_tributario"] = st.sidebar.selectbox(
        "Regimen tributario (SRI)",
        regimenes,
        index=regimenes.index(reg_actual),
        format_func=lambda v: etiquetas_regimen.get(v, v),
        key=f"sc_regimen_{rev}",
        help="Negocio Popular aplica solo a personas naturales hasta USD 20,000; construccion y agro estan excluidos de RIMPE.",
    )

    escenario["area_m2"] = st.sidebar.number_input(
        "Area de construccion / local (m2)",
        min_value=0.0,
        max_value=200000.0,
        value=float(escenario.get("area_m2") or 0.0),
        step=10.0,
        key=f"sc_area_{rev}",
        help="Se usa para las tasas municipales por metro cuadrado en tramites de construccion/planos.",
    )
    escenario["empleados"] = st.sidebar.number_input(
        "Numero de empleados",
        min_value=0,
        max_value=5000,
        value=int(escenario.get("empleados") or 0),
        step=1,
        key=f"sc_empleados_{rev}",
        help="Activa tramites laborales obligatorios (IESS/SUT/Reglamento de Higiene si > 10) y valida dotacion. El costo de nomina se edita por actividad en la tabla.",
    )
    escenario["admin_pct"] = st.sidebar.number_input(
        "Gastos administrativos (%)",
        min_value=0.0,
        max_value=40.0,
        value=float(
            escenario.get(
                "admin_pct", parametros.get("gastos_administrativos", {}).get("pct", 5.0)
            )
        ),
        step=0.5,
        key=f"sc_admin_{rev}",
        help="Supuesto editable sobre los costos directos privados. No es una tasa legal.",
    )
    escenario["aplica_iva"] = st.sidebar.checkbox(
        "Aplicar IVA (15%) a compras y equipos",
        value=bool(escenario.get("aplica_iva", False)),
        key=f"sc_iva_{rev}",
        help="Grava costos directos, equipos y gastos generales asociados. Excluye nomina en relacion de dependencia, actividades con IVA 0% y tasas publicas.",
    )

    panel_canton(escenario["canton"], parametros)

    st.sidebar.divider()
    st.sidebar.caption(
        f"SBU USD {parametros['salario']['sbu']:.2f} ({parametros['salario']['sbu_vigencia']}) · "
        f"aporte patronal {parametros['iess']['aporte_patronal_pct']}% · "
        f"IVA {parametros['impuestos']['iva_pct']}%"
    )
    st.sidebar.caption(
        f"Catalogo normativo revisado: {cargar_base_ecuador().get('ultima_revision', 'sin fecha')}"
    )

    cfg = copiloto_ia.configuracion()
    st.sidebar.divider()
    if cfg["proveedor"] == "local":
        st.sidebar.caption(
            "Copiloto en modo local: reglas y catalogo, sin llamadas externas."
        )
    else:
        estado = "clave configurada" if cfg.get("clave_configurada") else "sin clave"
        st.sidebar.caption(
            f"Copiloto configurado: {cfg['proveedor']} · {cfg['modelo']} ({estado})"
        )

    proyecto.escenario = escenario
    return escenario


def panel_canton(canton: str, parametros: Dict[str, Any]) -> None:
    """Muestra el tarifario del canton y advierte si no hay dato verificado."""
    info = resumen_canton(canton, parametros)
    with st.sidebar.expander("Tarifas del canton"):
        if not info["disponible"]:
            st.warning(
                f"No hay tarifario cargado para {canton}. Los tramites municipales "
                "usan el costo de referencia del catalogo."
            )
            return
        st.caption(f"{info['entidad']} · revisado {info['verificado_en'] or 'sin fecha'}")
        filas = []
        for tarifa in info["tarifas"].values():
            sufijo = "/m2" if tarifa.get("unidad") == "m2" else ""
            rango = tarifa.get("rango")
            referencia = (
                f"{float(rango[0]):.2f}–{float(rango[1]):.2f}"
                if isinstance(rango, list) and len(rango) == 2
                else f"{float(tarifa.get('valor') or 0):.2f}{sufijo}"
            )
            filas.append((str(tarifa.get("concepto") or ""), referencia))
        for concepto, referencia in filas:
            st.markdown(f"- **{concepto}**: USD {referencia}")
        st.caption(
            "Valores de referencia del GAD. Confirma la ordenanza vigente antes "
            "de presentar el presupuesto."
        )
        enlace = url_segura(info.get("fuente_url"))
        if enlace:
            st.markdown(f"[Portal del GAD]({enlace})")


# ------------------------------------------------------------------- Chat IA
def _plan_a_dataframe(plan: Dict[str, Any]) -> pd.DataFrame:
    filas: List[Dict[str, Any]] = []
    for actividad in plan.get("actividades", []):
        if not isinstance(actividad, dict):
            continue
        filas.append(
            {
                "Incluir": True,
                "ID": str(actividad.get("id", "")),
                "Actividad": str(actividad.get("nombre", "")),
                "Tipo": actividad.get("tipo", "privada"),
                "Predecesoras": ", ".join(actividad.get("predecesoras", []) or []),
                "a": float(actividad.get("optimista", 1) or 0),
                "m": float(actividad.get("probable", 1) or 0),
                "b": float(actividad.get("pesimista", 1) or 0),
                "Costo USD": float(actividad.get("costo", 0) or 0),
                "Equipos USD": float(actividad.get("costo_equipos", 0) or 0),
                "IVA": (
                    False
                    if actividad.get("tipo", "privada") == "tramite"
                    else bool(actividad.get("grava_iva", True))
                ),
                "Trabajadores": int(actividad.get("trabajadores", 0) or 0),
                "Costo MO/dia": float(actividad.get("costo_mo_diario", 0) or 0),
            }
        )
    return pd.DataFrame(filas)


def _dataframe_a_plan(tabla: pd.DataFrame, plan: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruye el JSON del plan conservando ids y metadata no editable."""
    originales = [
        a for a in plan.get("actividades", []) if isinstance(a, dict)
    ]
    por_id = {str(a.get("id") or ""): a for a in originales if a.get("id")}
    excluidos = set()
    for indice, fila in tabla.iterrows():
        if not bool(fila.get("Incluir", True)):
            base = por_id.get(str(fila.get("ID") or "")) or (
                originales[indice] if indice < len(originales) else {}
            )
            if base.get("id"):
                excluidos.add(str(base["id"]))

    actividades: List[Dict[str, Any]] = []
    for indice, fila in tabla.iterrows():
        if not bool(fila.get("Incluir", True)):
            continue
        id_fila = str(fila.get("ID") or "").strip()
        base = dict(por_id.get(id_fila) or (originales[indice] if indice < len(originales) else {}))
        ida = str(base.get("id") or id_fila).strip()
        if not ida:
            ida = nuevo_id(str(fila.get("Actividad") or "actividad"), [a["id"] for a in actividades])
        preds = [
            p.strip()
            for p in str(fila.get("Predecesoras") or "").replace(";", ",").split(",")
            if p.strip() and p.strip() not in excluidos
        ]
        tipo_act = str(fila.get("Tipo") or base.get("tipo", "privada"))
        iva_val = fila.get("IVA")
        grava_iva = (
            False
            if tipo_act == "tramite"
            else (True if iva_val is None or (isinstance(iva_val, float) and pd.isna(iva_val)) else bool(iva_val))
        )
        actividades.append(
            {
                **base,
                "id": ida,
                "nombre": str(fila.get("Actividad") or base.get("nombre", ida)),
                "tipo": tipo_act,
                "predecesoras": preds,
                "optimista": float(fila.get("a") or 0),
                "probable": float(fila.get("m") or 0),
                "pesimista": float(fila.get("b") or 0),
                "costo": float(fila.get("Costo USD") or 0),
                "costo_equipos": float(fila.get("Equipos USD") or 0),
                "grava_iva": grava_iva,
                "trabajadores": int(float(fila.get("Trabajadores") or 0)),
                "costo_mo_diario": float(fila.get("Costo MO/dia") or 0),
            }
        )
    return {**plan, "actividades": actividades}


def vista_aprobacion(plan: Dict[str, Any], proyecto: Proyecto) -> None:
    """Muestra el plan, permite editarlo y exige aprobacion explicita."""
    modo = str(plan.get("modo") or "local")
    proveedor = str(plan.get("proveedor") or "IA")
    etiqueta_modo = {
        "api": f"respuesta generada por IA ({proveedor})",
        "local": "planificador local basado en catalogo",
        "respaldo_local": "respaldo local (la API no respondio)",
    }.get(modo, "plan propuesto")
    seccion(
        "Paso 2: Revisa y aprueba el plan propuesto",
        f"Origen: {etiqueta_modo}. Revisa las actividades, duraciones (a, m, b) y costos "
        "antes de incorporarlas al proyecto. Todos los calculos finales los ejecuta el motor CPM/PERT.",
    )
    tabla = _plan_a_dataframe(plan)
    if tabla.empty:
        st.warning("El plan no contiene actividades.")
        return

    huella = hashlib.sha256(
        json.dumps([a.get("id") for a in plan.get("actividades", [])], sort_keys=True).encode()
    ).hexdigest()[:10]
    editada = st.data_editor(
        tabla,
        num_rows="fixed",
        hide_index=True,
        width="stretch",
        key=f"editor_plan_copiloto_{huella}",
        column_config={
            "Incluir": st.column_config.CheckboxColumn("Incluir", width="small"),
            "ID": st.column_config.TextColumn("ID", width="small", disabled=True),
            "Actividad": st.column_config.TextColumn("Actividad", width="large", required=True),
            "Tipo": st.column_config.SelectboxColumn(
                "Tipo", options=["privada", "tramite"], width="small"
            ),
            "Predecesoras": st.column_config.TextColumn("Predecesoras", width="medium"),
            "a": st.column_config.NumberColumn("a (optimista)", min_value=0.0, step=0.5, format="%.1f"),
            "m": st.column_config.NumberColumn("m (probable)", min_value=0.0, step=0.5, format="%.1f"),
            "b": st.column_config.NumberColumn("b (pesimista)", min_value=0.0, step=0.5, format="%.1f"),
            "Costo USD": st.column_config.NumberColumn("Costo USD", min_value=0.0, step=10.0, format="%.2f"),
            "Equipos USD": st.column_config.NumberColumn("Equipos USD", min_value=0.0, step=10.0, format="%.2f"),
            "IVA": st.column_config.CheckboxColumn("IVA 15%", width="small"),
            "Trabajadores": st.column_config.NumberColumn("Trabajadores", min_value=0, step=1),
            "Costo MO/dia": st.column_config.NumberColumn("Costo MO/dia", min_value=0.0, step=1.0, format="%.2f"),
        },
    )

    plan_editado = _dataframe_a_plan(editada, plan)
    errores: List[Problema] = []
    try:
        candidato = copiloto_ia.aplicar_plan(plan_editado, proyecto_actual=proyecto)
        cpm = calcular_cpm(candidato)
        problemas = validar(candidato, cargar_base_ecuador())
        c1, c2, c3 = st.columns(3)
        c1.metric("Actividades totales", len(candidato.actividades))
        c2.metric("Duracion estimada", f"{cpm['duracion']:.1f} dias")
        c3.metric("Ruta critica", f"{len(cpm['actividades_criticas'])} tareas")
        errores = [p for p in problemas if p.nivel == ERROR]
        if errores:
            st.error(
                f"El plan tiene {len(errores)} error(es) que impiden calcularlo. "
                "Corrige la tabla antes de aprobarlo."
            )
            for problema in errores[:6]:
                st.markdown(
                    f'<div class="ec-item">{badge("error", problema.etiqueta)}'
                    f"{escapar(problema.mensaje)}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption(
                "Estructura valida sin ciclos. Al aprobar, este plan se incorpora formalmente "
                "a tu proyecto y podras explorar su Ruta Critica y Presupuesto en las siguientes pestanas."
            )
    except CicloError as error:
        st.error(f"No se puede aprobar el plan: {escapar(error)}")
        errores = [Problema(ERROR, "ciclo", str(error))]
    except Exception as error:  # un plan malformado nunca debe tumbar la app
        st.error(f"Plan invalido: {type(error).__name__}: {escapar(error)}")
        errores = [Problema(ERROR, "plan_invalido", str(error))]

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            "Aprobar e incorporar plan",
            type="primary",
            width="stretch",
            disabled=bool(errores),
        ):
            nuevo_proyecto_sesion(copiloto_ia.aplicar_plan(plan_editado, proyecto))
            st.session_state["plan_aprobado_exito"] = True
            st.rerun()
    with col2:
        if st.button("Descartar plan", width="stretch"):
            st.session_state.pop("plan_pendiente", None)
            st.rerun()


def panel_copiloto(proyecto: Proyecto, incluir_opcionales: bool = False) -> None:
    seccion(
        "Copiloto de planificacion (IA)",
        "Describe tu proyecto en una frase. El copiloto te hara preguntas clave y propondra "
        "las tareas operativas y los tramites de ley del Ecuador.",
    )

    cfg = copiloto_ia.configuracion()
    col_estado, col_prueba = st.columns([3.2, 1])
    with col_estado:
        if cfg["proveedor"] == "local":
            st.caption("Modo local activo (sin llamadas a IA externa).")
        else:
            st.caption(
                f"Proveedor activo: **{cfg['proveedor']}** · modelo `{cfg['modelo']}` (IA conectada)."
            )
    resultado_conexion = None
    with col_prueba:
        if st.button("Probar conexion", width="stretch", help="Verifica la clave y el modelo."):
            resultado_conexion = copiloto_ia.probar_conexion()
    if resultado_conexion is not None:
        if resultado_conexion["ok"]:
            st.success(resultado_conexion["mensaje"])
        else:
            st.warning(resultado_conexion["mensaje"])

    historial = st.session_state.setdefault("chat", [])

    # Si el chat esta vacio, mostramos una guia sobria y ejemplos para iniciar
    sugerencia_seleccionada = None
    if not historial:
        st.markdown(
            '<div class="ec-card">'
            '<div class="ec-card-titulo">Asistente normativo y de planificacion</div>'
            "<p>Describe tu proyecto en lenguaje natural (giro, ciudad, area aproximada y personal). "
            "El copiloto estructura actividades privadas, enlaza los tramites obligatorios del Ecuador "
            "y entrega una tabla editable lista para calcular ruta critica y presupuesto.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption("O inicia con una plantilla rapida por sector:")
        cs1, cs2, cs3, cs4 = st.columns(4)
        with cs1:
            if st.button("Ferreteria en Ambato", width="stretch"):
                sugerencia_seleccionada = "Quiero abrir una ferreteria comercial en Ambato con local arrendado"
        with cs2:
            if st.button("Consultorio medico", width="stretch"):
                sugerencia_seleccionada = "Quiero abrir un consultorio medico o clinica privada en Quito"
        with cs3:
            if st.button("Hostal turistico", width="stretch"):
                sugerencia_seleccionada = "Quiero abrir un hostal turistico de 200 m2 en Ambato"
        with cs4:
            if st.button("Taller industrial", width="stretch"):
                sugerencia_seleccionada = "Quiero abrir un taller de carpinteria para fabricar muebles en Ambato"

    # Mostrar todos los mensajes anteriores en orden cronologico
    for turno in historial:
        with st.chat_message(turno["role"]):
            st.markdown(turno["content"])
            if turno.get("caption"):
                st.caption(turno["caption"])
            if turno.get("error"):
                st.warning(f"Detalle tecnico: {capacidad_texto(turno['error'])}")

    pregunta_input = st.chat_input("Escribe tu proyecto o responde las preguntas del copiloto...")
    pregunta = pregunta_input or sugerencia_seleccionada

    if pregunta:
        historial.append({"role": "user", "content": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            with st.spinner("El Copiloto normativo esta analizando tu proyecto..."):
                respuesta = copiloto_ia.conversar(
                    historial, pregunta, proyecto.escenario, incluir_opcionales
                )
            texto = respuesta.get("mensaje") or "Listo."
            if respuesta.get("preguntas"):
                texto += "\n\n" + "\n".join(f"- {p}" for p in respuesta["preguntas"])
            if respuesta.get("supuestos"):
                texto += "\n\n*Supuestos normativos considerados:*\n" + "\n".join(f"- {s}" for s in respuesta["supuestos"])
            caption_modo = {
                "api": f"Respuesta generada por {respuesta.get('proveedor', 'IA')}.",
                "local": "Generado por el planificador local, sin IA.",
                "respaldo_local": "Respuesta de respaldo local: la API de IA no respondio.",
            }.get(respuesta.get("modo", "local"), "Plan propuesto.")
            st.markdown(texto)
            st.caption(caption_modo)
            if respuesta.get("error"):
                st.warning(f"Detalle tecnico: {capacidad_texto(respuesta['error'])}")
        historial.append(
            {
                "role": "assistant",
                "content": texto,
                "caption": caption_modo,
                "error": respuesta.get("error"),
            }
        )

        if respuesta.get("listo") and respuesta.get("proyecto"):
            plan = dict(respuesta["proyecto"])
            plan["modo"] = respuesta.get("modo", "local")
            plan["proveedor"] = respuesta.get("proveedor", "")
            st.session_state["plan_pendiente"] = plan

        st.rerun()

    if historial and st.button("Reiniciar conversacion", help="Borra el historial del chat"):
        st.session_state["chat"] = []
        st.session_state.pop("plan_pendiente", None)
        st.rerun()


def capacidad_texto(valor: Any, maximo: int = 300) -> str:
    """Recorta y sanitiza un texto tecnico antes de mostrarlo (evita fugar claves)."""
    texto = str(valor or "")
    texto = re.sub(r"(AIza[0-9A-Za-z-_]{20,})", "[REDACTED_API_KEY]", texto)
    texto = re.sub(r"(sk-[0-9A-Za-z-_]{20,})", "[REDACTED_API_KEY]", texto)
    return texto[:maximo] + ("..." if len(texto) > maximo else "")


# ------------------------------------------------------------ Tabla editable
def proyecto_a_dataframe(proyecto: Proyecto) -> pd.DataFrame:
    filas = []
    for actividad in proyecto.actividades.values():
        filas.append(
            {
                "ID": actividad.id,
                "Actividad": actividad.nombre,
                "Tipo": actividad.tipo,
                "Predecesoras": ", ".join(actividad.predecesoras),
                "a": actividad.optimista,
                "m": actividad.probable,
                "b": actividad.pesimista,
                "Costo USD": round(actividad.costo, 2),
                "Equipos USD": round(actividad.costo_equipos, 2),
                "IVA": False if actividad.tipo == "tramite" else bool(actividad.grava_iva),
                "Trabajadores": actividad.trabajadores,
                "Costo MO/dia": round(actividad.costo_mo_diario, 2),
                "Entidad": actividad.entidad or "—",
            }
        )
    return pd.DataFrame(filas, columns=COLUMNAS_EDITABLES)


def _parsear_preds(texto: Any) -> List[str]:
    if texto is None:
        return []
    if isinstance(texto, float) and pd.isna(texto):
        return []
    partes = str(texto).replace(";", ",").split(",")
    return [parte.strip() for parte in partes if parte.strip()]


def _num(valor: Any, defecto: float = 0.0) -> float:
    try:
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            return defecto
        numero = float(valor)
        return numero if math.isfinite(numero) else defecto
    except (TypeError, ValueError):
        return defecto


def proyecto_desde_dataframe(original: Proyecto, tabla: pd.DataFrame) -> Proyecto:
    """Reconstruye el proyecto conservando metadatos y dependencias declaradas.

    A diferencia de la version anterior, una predecesora que no coincide con
    ningun ID se conserva: el validador la marca como error para que el usuario
    corrija el identificador en lugar de perder la relacion.
    """
    nuevo = Proyecto(
        nombre=original.nombre,
        descripcion=original.descripcion,
        escenario=dict(original.escenario),
    )
    mapa: Dict[str, str] = {}
    ids_por_fila: Dict[Any, str] = {}
    lista_original = list(original.actividades.values())
    cat = catalogo_por_id()

    ids_tabla = set(str(row.get("ID") or "").strip() for _, row in tabla.iterrows())

    for pos, (indice, fila) in enumerate(tabla.iterrows()):
        nombre = str(fila.get("Actividad") or "").strip()
        if not nombre:
            continue
        id_original = str(fila.get("ID") or "").strip()
        existente = original.obtener(id_original) if id_original else None

        # Si no se encontro por ID directo, verificar si fue renombrado desde la fila original (Bug 7)
        if existente is None and pos < len(lista_original):
            act_orig = lista_original[pos]
            if act_orig.id not in ids_tabla:
                existente = act_orig
                if act_orig.id not in mapa:
                    mapa[act_orig.id] = id_original

        # Si sigue sin encontrarse, verificar si coincide con un tramite del catalogo (Bug 7)
        if existente is None and id_original in cat:
            existente = Actividad.desde_catalogo(cat[id_original])

        actividad = (
            Actividad.from_dict(existente.to_dict())
            if existente
            else Actividad(id="", nombre=nombre)
        )
        if not id_original or id_original in mapa.values():
            actividad.id = nuevo_id(nombre, nuevo.actividades.keys())
        else:
            actividad.id = id_original

        # Bug 5: Solo registrar en el mapa la primera aparicion del id_original
        if id_original and id_original not in mapa:
            mapa[id_original] = actividad.id
        ids_por_fila[indice] = actividad.id

        actividad.nombre = nombre
        actividad.tipo = (
            str(fila.get("Tipo") or "privada")
            if str(fila.get("Tipo") or "privada") in ("privada", "tramite")
            else "privada"
        )
        actividad.optimista = _num(fila.get("a"))
        actividad.probable = _num(fila.get("m"))
        actividad.pesimista = _num(fila.get("b"))
        nuevo_costo = _num(fila.get("Costo USD"))
        nuevo_equipos = _num(fila.get("Equipos USD"))
        if existente and (actividad.costo != nuevo_costo or actividad.costo_equipos != nuevo_equipos):
            actividad.costo_manual = True
        actividad.costo = nuevo_costo
        actividad.costo_equipos = nuevo_equipos
        iva_val = fila.get("IVA")
        if actividad.tipo == "tramite":
            actividad.grava_iva = False
        elif iva_val is None or (isinstance(iva_val, float) and pd.isna(iva_val)):
            actividad.grava_iva = True
        else:
            actividad.grava_iva = bool(iva_val)
        actividad.trabajadores = int(_num(fila.get("Trabajadores")))
        actividad.costo_mo_diario = _num(fila.get("Costo MO/dia"))
        nuevo.agregar(actividad)

    for indice, fila in tabla.iterrows():
        id_nuevo = ids_por_fila.get(indice)
        actividad = nuevo.obtener(id_nuevo) if id_nuevo else None
        if actividad is None:
            continue
        actividad.predecesoras = [
            mapa.get(pred, pred) for pred in _parsear_preds(fila.get("Predecesoras"))
        ]

    return nuevo


def _siguiente_id_pert(proyecto: Proyecto) -> str:
    existentes = set(proyecto.actividades)
    for codigo in range(ord("A"), ord("Z") + 1):
        letra = chr(codigo)
        if letra not in existentes:
            return letra
    indice = 1
    while f"act_{indice}" in existentes:
        indice += 1
    return f"act_{indice}"


def formulario_actividad_manual(proyecto: Proyecto, key_prefix: str = "manual") -> None:
    """Formulario guiado para planificacion manual PERT (a, m, b y predecesoras)."""
    rev = revision_actual()
    sugerido = _siguiente_id_pert(proyecto)
    col_id, col_nombre, col_tipo = st.columns([0.8, 2.2, 1])
    with col_id:
        ida = st.text_input(
            "ID",
            value=sugerido,
            max_chars=64,
            key=f"{key_prefix}_id_{rev}",
            help="Identificador corto (ej. A, B, C o diseno_base).",
        ).strip()
    with col_nombre:
        nombre = st.text_input(
            "Actividad",
            value="",
            placeholder=f"Ej: Actividad {sugerido} o Levantamiento inicial",
            key=f"{key_prefix}_nombre_{rev}",
        ).strip()
    with col_tipo:
        tipo = st.selectbox(
            "Tipo",
            ["privada", "tramite"],
            key=f"{key_prefix}_tipo_{rev}",
        )

    col_pred, col_a, col_m, col_b = st.columns([2.1, 0.7, 0.7, 0.7])
    opciones_pred = list(proyecto.actividades.keys())
    with col_pred:
        preds_sel = st.multiselect(
            "Predecesoras",
            opciones_pred,
            format_func=lambda pid: f"{pid} · {proyecto.actividades[pid].nombre}",
            key=f"{key_prefix}_preds_{rev}",
            placeholder="Ninguna (actividad inicial)",
        )
    with col_a:
        opt = st.number_input("a (opt.)", min_value=0.0, value=1.0, step=0.5, key=f"{key_prefix}_a_{rev}")
    with col_m:
        prob = st.number_input("m (prob.)", min_value=0.0, value=2.0, step=0.5, key=f"{key_prefix}_m_{rev}")
    with col_b:
        pes = st.number_input("b (pes.)", min_value=0.0, value=4.0, step=0.5, key=f"{key_prefix}_b_{rev}")

    if 0 <= opt <= prob <= pes:
        te = (opt + 4 * prob + pes) / 6.0
        var = ((pes - opt) / 6.0) ** 2
        st.caption(f"Vista previa PERT: `te = {te:.2f} dias` · `varianza = {var:.4f}`")
    else:
        st.warning("Debe cumplirse `0 <= a <= m <= b` para calcular tiempos PERT.")

    with st.expander("Costos, personal e IVA (opcional)"):
        c1, c2, c3, c4, c5 = st.columns([1, 1, 0.9, 1, 0.7])
        with c1:
            costo = st.number_input("Costo directo USD", min_value=0.0, value=0.0, step=10.0, key=f"{key_prefix}_costo_{rev}")
        with c2:
            equipos = st.number_input("Equipos USD", min_value=0.0, value=0.0, step=10.0, key=f"{key_prefix}_eq_{rev}")
        with c3:
            trab = st.number_input("Trabajadores", min_value=0, value=0, step=1, key=f"{key_prefix}_trab_{rev}")
        with c4:
            mo_dia = st.number_input("MO/dia USD", min_value=0.0, value=0.0, step=1.0, key=f"{key_prefix}_mo_{rev}")
        with c5:
            grava_iva = st.checkbox(
                "IVA 15%",
                value=(tipo == "privada"),
                disabled=(tipo == "tramite"),
                key=f"{key_prefix}_iva_{rev}",
            )
        preds_extra = st.text_input(
            "Predecesoras adicionales por ID (opcional, separadas por coma)",
            value="",
            key=f"{key_prefix}_preds_extra_{rev}",
        )

    if st.button("Agregar actividad al cronograma", type="primary", width="stretch", key=f"{key_prefix}_btn_{rev}"):
        if not ida or not ID_VALIDO.match(ida):
            st.error("Ingresa un ID valido (1 a 64 caracteres, sin saltos de linea).")
            return
        if ida in proyecto.actividades:
            st.error(f"Ya existe una actividad con el ID '{escapar(ida)}'.")
            return
        if not (0 <= opt <= prob <= pes):
            st.error("Los tiempos PERT deben cumplir 0 <= optimista <= probable <= pesimista.")
            return
        preds = list(dict.fromkeys(list(preds_sel) + _parsear_preds(preds_extra)))
        proyecto.agregar(
            Actividad(
                id=ida,
                nombre=nombre or f"Actividad {ida}",
                tipo=tipo,
                predecesoras=preds,
                optimista=float(opt),
                probable=float(prob),
                pesimista=float(pes),
                costo=float(costo),
                costo_equipos=float(equipos),
                trabajadores=int(trab),
                costo_mo_diario=float(mo_dia),
                grava_iva=False if tipo == "tramite" else bool(grava_iva),
                origen="manual",
            )
        )
        st.session_state["_proyecto_revision"] = rev + 1
        st.rerun()


def tabla_editable(proyecto: Proyecto) -> Proyecto:
    seccion(
        "Actividades del proyecto",
        "Edita duraciones PERT (a / m / b), costos y predecesoras. El ID encadena "
        "dependencias y se conserva aunque no exista: el validador lo reporta.",
    )
    tabla = proyecto_a_dataframe(proyecto)
    # Evitar StreamlitValueBelowMinError asegurando valores numericos no negativos (Bug 9)
    for col in ("a", "m", "b", "Costo USD", "Equipos USD", "Trabajadores", "Costo MO/dia"):
        if col in tabla.columns:
            tabla[col] = tabla[col].apply(lambda x: max(float(x or 0.0), 0.0))
    editada = st.data_editor(
        tabla,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"editor_actividades_{revision_actual()}",
        column_config={
            "ID": st.column_config.TextColumn("ID", width="small", help="Identificador unico"),
            "Actividad": st.column_config.TextColumn("Actividad", width="large", required=True),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["privada", "tramite"], width="small"),
            "Predecesoras": st.column_config.TextColumn("Predecesoras", width="medium", help="IDs separados por coma"),
            "a": st.column_config.NumberColumn("a", min_value=0.0, step=0.5, format="%.1f"),
            "m": st.column_config.NumberColumn("m", min_value=0.0, step=0.5, format="%.1f"),
            "b": st.column_config.NumberColumn("b", min_value=0.0, step=0.5, format="%.1f"),
            "Costo USD": st.column_config.NumberColumn(
                "Costo directo USD", min_value=0.0, step=10.0, format="%.2f",
                help="Materiales, compras y servicios de la actividad.",
            ),
            "Equipos USD": st.column_config.NumberColumn(
                "Equipos USD", min_value=0.0, step=10.0, format="%.2f",
                help="Maquinaria, herramientas y equipos alquilados.",
            ),
            "IVA": st.column_config.CheckboxColumn(
                "IVA 15%", width="small",
                help="Grava IVA 15% sobre costos directos y equipos (desmarcar si es tarifa 0%).",
            ),
            "Trabajadores": st.column_config.NumberColumn("Trabajadores", min_value=0, step=1),
            "Costo MO/dia": st.column_config.NumberColumn("Costo MO/dia", min_value=0.0, step=1.0, format="%.2f"),
            "Entidad": st.column_config.TextColumn("Entidad", disabled=True, width="medium"),
        },
    )
    return proyecto_desde_dataframe(proyecto, editada)


# ------------------------------------------------------------------ Catalogo
def panel_catalogo(proyecto: Proyecto) -> None:
    base = cargar_base_ecuador()
    catalogo = {tramite["id"]: tramite for tramite in base["tramites"]}
    disponibles = {ida: tramite for ida, tramite in catalogo.items() if ida not in proyecto.actividades}

    with st.expander(f"Catalogo normativo · {len(disponibles)} tramites disponibles"):
        st.caption(
            f"Version {base.get('version', '')} · revision {base.get('ultima_revision', '')}. "
            "Cada ficha declara si el valor es oficial, estimado, de mercado o un rango, "
            "y si la fuente es un enlace directo o el portal institucional."
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            niveles = sorted({t.get("nivel", "") for t in base["tramites"] if t.get("nivel")})
            filtro_nivel = st.multiselect("Nivel", niveles, key="filtro_nivel_catalogo")
        with col2:
            categorias = sorted({t.get("categoria", "") for t in base["tramites"] if t.get("categoria")})
            filtro_categoria = st.multiselect("Categoria", categorias, key="filtro_categoria_catalogo")
        with col3:
            filtro_valor = st.multiselect(
                "Tipo de valor",
                ["oficial", "estimacion", "rango", "mercado"],
                key="filtro_valor_catalogo",
            )

        opciones = [
            ida
            for ida, tramite in disponibles.items()
            if (not filtro_nivel or tramite.get("nivel") in filtro_nivel)
            and (not filtro_categoria or tramite.get("categoria") in filtro_categoria)
            and (not filtro_valor or tramite.get("valor_tipo") in filtro_valor)
        ]
        seleccion = st.multiselect(
            "Tramites a incorporar",
            opciones,
            format_func=lambda ida: f"{disponibles[ida]['nombre']} · {disponibles[ida]['entidad']}",
            key="seleccion_catalogo",
        )
        if st.button("Incorporar seleccionados", disabled=not seleccion):
            for ida in seleccion:
                proyecto.agregar(Actividad.desde_catalogo(disponibles[ida]))
            st.success(f"Se incorporaron {len(seleccion)} tramites al proyecto.")
            st.rerun()

        if disponibles:
            elegido = st.selectbox(
                "Ficha del tramite",
                list(disponibles),
                format_func=lambda ida: disponibles[ida]["nombre"],
                key="ficha_catalogo",
            )
            tramite = disponibles[elegido]
            valor_tipo = tramite.get("valor_tipo", "")
            estado = (
                badge("ok", "Valor oficial")
                if valor_tipo == "oficial"
                else badge("advertencia", {
                    "estimacion": "Valor estimado",
                    "rango": "Valor en rango",
                    "mercado": "Precio de mercado",
                }.get(valor_tipo, "Valor de referencia"))
            )
            nivel = tramite.get("nivel", "")
            st.markdown(
                f'{estado}<span class="ec-tenue" style="font-size:0.78rem;color:#5E6A75">'
                f'{escapar(nivel)} · {escapar(tramite.get("categoria", ""))} · fuente: '
                f'{escapar(tramite.get("fuente_tipo", "sin declarar"))}</span>',
                unsafe_allow_html=True,
            )
            enlace = url_segura(tramite.get("fuente_url"))
            st.markdown(
                f"**{escapar(tramite['nombre'])}**  \n"
                f"{escapar(tramite['entidad'])} · PERT {tramite['optimista']}/"
                f"{tramite['probable']}/{tramite['pesimista']} dias  \n"
                f"Costo de referencia: USD {tramite['costo']:.2f}. "
                f"{escapar(tramite.get('costo_nota', ''))}  \n"
                f"Normativa: {escapar(tramite.get('fuente_normativa', ''))}  \n"
                f"Revisado: {escapar(tramite.get('verificado_en', 'sin fecha'))}  \n"
                + (f"[Fuente institucional]({enlace})" if enlace else "Fuente sin enlace verificado.")
            )
            if tramite.get("fuente_detalle"):
                st.caption(tramite["fuente_detalle"])
            if tramite.get("requisitos"):
                st.markdown("**Requisitos:** " + "; ".join(escapar(r) for r in tramite["requisitos"]))
            if tramite.get("predecesoras"):
                st.markdown("**Predecesoras legales:** " + ", ".join(tramite["predecesoras"]))
            if st.button("Agregar este tramite", key=f"agregar_{elegido}"):
                proyecto.agregar(Actividad.desde_catalogo(tramite))
                st.rerun()


# --------------------------------------------------------------- Validacion
def mostrar_problemas(problemas: List[Problema]) -> None:
    errores = [p for p in problemas if p.nivel == ERROR]
    advertencias = [p for p in problemas if p.nivel == ADVERTENCIA]
    infos = [p for p in problemas if p.nivel == INFO]

    if not problemas:
        st.markdown(
            f'<div class="ec-item">{badge("ok", "Validacion limpia")}'
            "Sin ciclos, dependencias rotas ni reglas legales incumplidas.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'{badge("error", f"{len(errores)} errores")}'
        f'{badge("advertencia", f"{len(advertencias)} advertencias")}'
        f'{badge("info", f"{len(infos)} observaciones")}',
        unsafe_allow_html=True,
    )

    titulos = {"error": "Errores", "advertencia": "Advertencias", "info": "Observaciones"}
    for grupo, nivel in (
        (errores, "error"),
        (advertencias, "advertencia"),
        (infos, "info"),
    ):
        if not grupo:
            continue
        with st.expander(f"{titulos[nivel]} ({len(grupo)})", expanded=nivel == "error"):
            for problema in grupo:
                st.markdown(
                    f'<div class="ec-item">{badge(nivel, problema.etiqueta)}'
                    f"{escapar(problema.mensaje)}</div>",
                    unsafe_allow_html=True,
                )

    if hay_errores(problemas):
        st.error(
            "Corrige los errores antes de calcular: el motor CPM no puede programar "
            "un grafo invalido. Las dependencias con IDs inexistentes se conservan "
            "hasta que decidas corregirlas o eliminarlas."
        )


# ------------------------------------------------------------ Persistencia
def panel_guardar_cargar(proyecto: Proyecto) -> None:
    with st.sidebar.expander("Guardar / cargar proyecto"):
        st.download_button(
            "Descargar proyecto (JSON)",
            data=json.dumps(proyecto.to_dict(), ensure_ascii=False, indent=2),
            file_name=sanitizar_nombre_archivo(proyecto.nombre),
            mime="application/json",
            width="stretch",
        )
        st.download_button(
            "Descargar plantilla (.xlsx)",
            data=importador.plantilla_excel(),
            file_name="plantilla_ecuaproject.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        st.caption("Importa `.json`, `.xlsx`, `.csv` o `.pdf` (max. 2 MB).")
        archivo = st.file_uploader(
            "Cargar proyecto",
            type=["json", "xlsx", "csv", "pdf"],
            label_visibility="collapsed",
        )
        if archivo is not None:
            # Evita el bucle de recarga: Streamlit conserva el archivo entre
            # reruns y sin esta huella el proyecto se recargaria sin parar.
            contenido = archivo.getvalue()
            huella = hashlib.sha256(contenido).hexdigest()
            if st.session_state.get("_json_cargado") != huella:
                try:
                    cargado, formato, avisos = importador.importar_archivo(
                        archivo.name, contenido
                    )
                except (ErrorDatos, ValueError) as error:
                    st.error(f"Archivo invalido: {escapar(error)}")
                else:
                    st.session_state["_json_cargado"] = huella
                    st.session_state["modo_manual"] = False
                    nuevo_proyecto_sesion(cargado)
                    huerfanas = cargado.dependencias_huerfanas()
                    if huerfanas:
                        total = sum(len(v) for v in huerfanas.values())
                        avisos.append(
                            f"Hay {total} dependencia(s) que apuntan a IDs inexistentes; "
                            "revisalas en Tabla de Actividades."
                        )
                    st.session_state["proyecto_cargado_msg"] = (
                        f"Proyecto importado ({formato.upper()}): {cargado.nombre} "
                        f"({len(cargado.actividades)} actividades)."
                    )
                    st.session_state["proyecto_cargado_avisos"] = avisos
                    st.rerun()
