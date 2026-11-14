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
    nuevo_id,
)
from core.seguridad import (
    ErrorDatos,
    cargar_json_bytes,
    escapar,
    sanitizar_nombre_archivo,
    url_segura,
    validar_proyecto_json,
)
from core.validador import (
    ADVERTENCIA,
    ERROR,
    INFO,
    Problema,
    hay_errores,
    validar,
)
from services import copiloto_ia
from ui.estilos import badge, seccion

COLUMNAS_EDITABLES = [
    "ID", "Actividad", "Tipo", "Predecesoras", "a", "m", "b",
    "Costo USD", "Equipos USD", "Trabajadores", "Costo MO/dia", "Entidad",
]


# --------------------------------------------------------------- Estado global
def nuevo_proyecto_sesion(proyecto: Proyecto, reiniciar_chat: bool = False) -> None:
    """Reemplaza el proyecto y aisla los widgets del proyecto anterior."""
    st.session_state["proyecto"] = proyecto
    st.session_state["_proyecto_revision"] = int(
        st.session_state.get("_proyecto_revision", 0)
    ) + 1
    st.session_state.pop("plan_pendiente", None)
    st.session_state["calculado"] = True
    if reiniciar_chat:
        st.session_state["chat"] = []


def revision_actual() -> int:
    return int(st.session_state.get("_proyecto_revision", 0))


# ------------------------------------------------------------------ Escenario
def sidebar_escenario(proyecto: Proyecto) -> Dict[str, Any]:
    parametros = cargar_parametros()
    escenario = dict(proyecto.escenario)
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
        help="Afecta tasas de ARCSA y descuentos para PYMES.",
    )

    escenario["area_m2"] = st.sidebar.number_input(
        "Area de construccion / local (m2)",
        min_value=0.0,
        max_value=200000.0,
        value=float(escenario.get("area_m2") or 0.0),
        step=10.0,
        help="Se usa para las tasas municipales por metro cuadrado.",
    )
    escenario["empleados"] = st.sidebar.number_input(
        "Numero de empleados",
        min_value=0,
        max_value=5000,
        value=int(escenario.get("empleados") or 0),
        step=1,
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
        help="Supuesto editable sobre los costos directos privados. No es una tasa legal.",
    )
    escenario["aplica_iva"] = st.sidebar.checkbox(
        "Aplicar IVA a la inversion privada",
        value=bool(escenario.get("aplica_iva", False)),
        help="El IVA no se aplica a las tasas y tramites publicos.",
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
                "Actividad": str(actividad.get("nombre", "")),
                "Tipo": actividad.get("tipo", "privada"),
                "Predecesoras": ", ".join(actividad.get("predecesoras", []) or []),
                "a": float(actividad.get("optimista", 1) or 0),
                "m": float(actividad.get("probable", 1) or 0),
                "b": float(actividad.get("pesimista", 1) or 0),
                "Costo USD": float(actividad.get("costo", 0) or 0),
                "Equipos USD": float(actividad.get("costo_equipos", 0) or 0),
                "Trabajadores": int(actividad.get("trabajadores", 0) or 0),
                "Costo MO/dia": float(actividad.get("costo_mo_diario", 0) or 0),
            }
        )
    return pd.DataFrame(filas)


def _dataframe_a_plan(tabla: pd.DataFrame, plan: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruye el JSON del plan conservando ids y metadata no editable.

    El ID no se edita en la tabla de aprobacion, pero se conserva para que las
    predecesoras sigan apuntando a la actividad correcta.
    """
    originales = [
        a for a in plan.get("actividades", []) if isinstance(a, dict)
    ]
    actividades: List[Dict[str, Any]] = []
    for indice, fila in tabla.iterrows():
        base = dict(originales[indice]) if indice < len(originales) else {}
        ida = str(base.get("id") or "").strip()
        if not ida:
            ida = nuevo_id(str(fila.get("Actividad") or "actividad"), [a["id"] for a in actividades])
        preds = [
            p.strip()
            for p in str(fila.get("Predecesoras") or "").replace(";", ",").split(",")
            if p.strip()
        ]
        actividades.append(
            {
                **base,
                "id": ida,
                "nombre": str(fila.get("Actividad") or base.get("nombre", ida)),
                "tipo": str(fila.get("Tipo") or base.get("tipo", "privada")),
                "predecesoras": preds,
                "optimista": float(fila.get("a") or 0),
                "probable": float(fila.get("m") or 0),
                "pesimista": float(fila.get("b") or 0),
                "costo": float(fila.get("Costo USD") or 0),
                "costo_equipos": float(fila.get("Equipos USD") or 0),
                "trabajadores": int(float(fila.get("Trabajadores") or 0)),
                "costo_mo_diario": float(fila.get("Costo MO/dia") or 0),
            }
        )
    return {**plan, "actividades": actividades}


def _vista_aprobacion(plan: Dict[str, Any], proyecto: Proyecto) -> None:
    """Muestra el plan, permite editarlo y exige aprobacion explicita."""
    modo = str(plan.get("modo") or "local")
    etiqueta_modo = {
        "api": "respuesta de la API de IA",
        "local": "planificador local (sin IA)",
        "respaldo_local": "respaldo local: la API no respondio",
    }.get(modo, "plan propuesto")
    seccion(
        "Plan propuesto por el copiloto",
        f"Origen: {etiqueta_modo}. Revisa la tabla antes de incorporarla; los calculos "
        "se haran con el motor CPM/PERT, no con el texto de la IA.",
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
            "Actividad": st.column_config.TextColumn("Actividad", width="large", required=True),
            "Tipo": st.column_config.SelectboxColumn(
                "Tipo", options=["privada", "tramite"], width="small"
            ),
            "Predecesoras": st.column_config.TextColumn("Predecesoras", width="medium"),
            "a": st.column_config.NumberColumn("a", min_value=0.0, step=0.5, format="%.1f"),
            "m": st.column_config.NumberColumn("m", min_value=0.0, step=0.5, format="%.1f"),
            "b": st.column_config.NumberColumn("b", min_value=0.0, step=0.5, format="%.1f"),
            "Costo USD": st.column_config.NumberColumn("Costo USD", min_value=0.0, step=10.0, format="%.2f"),
            "Equipos USD": st.column_config.NumberColumn("Equipos USD", min_value=0.0, step=10.0, format="%.2f"),
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
        c1.metric("Actividades", len(candidato.actividades))
        c2.metric("Duracion estimada", f"{cpm['duracion']:.1f} dias")
        c3.metric("Criticas", len(cpm["actividades_criticas"]))
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
                "Sin errores de estructura. Al aprobar, este plan reemplaza la tabla actual "
                "del proyecto y podras seguir editandola en la pestana Actividades."
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
            st.rerun()
    with col2:
        if st.button("Descartar plan", width="stretch"):
            st.session_state.pop("plan_pendiente", None)
            st.rerun()


def panel_copiloto(proyecto: Proyecto, incluir_opcionales: bool = False) -> None:
    seccion(
        "Copiloto de planificacion",
        "Describe el proyecto en una frase. El copiloto propone actividades y tramites; "
        "tu apruebas la tabla final.",
    )

    cfg = copiloto_ia.configuracion()
    col_estado, col_prueba = st.columns([3, 1])
    with col_estado:
        if cfg["proveedor"] == "local":
            st.caption("Modo local activo: no se realizan llamadas a ningun proveedor de IA.")
        else:
            st.caption(
                f"Proveedor configurado: {cfg['proveedor']} · modelo {cfg['modelo']}."
            )
    with col_prueba:
        if st.button("Probar conexion", width="stretch", help="Verifica la clave y el alcance del modelo."):
            resultado = copiloto_ia.probar_conexion()
            if resultado["ok"]:
                st.success(resultado["mensaje"])
            else:
                st.warning(resultado["mensaje"])

    historial = st.session_state.setdefault("chat", [])
    for turno in historial:
        with st.chat_message(turno["role"]):
            st.markdown(turno["content"])

    pregunta = st.chat_input("Ej: Quiero construir un galpon para fabricar muebles en Ambato")
    if pregunta:
        historial.append({"role": "user", "content": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            with st.spinner("Analizando el proyecto y la normativa aplicable..."):
                respuesta = copiloto_ia.conversar(
                    historial, pregunta, proyecto.escenario, incluir_opcionales
                )
            texto = respuesta["mensaje"] or "Listo."
            st.markdown(texto)
            if respuesta.get("preguntas"):
                st.markdown("\n".join(f"- {p}" for p in respuesta["preguntas"]))
            if respuesta.get("supuestos"):
                with st.expander("Supuestos usados"):
                    st.markdown("\n".join(f"- {s}" for s in respuesta["supuestos"]))
            st.caption(
                {
                    "api": f"Respuesta generada por {respuesta.get('proveedor', 'IA')}.",
                    "local": "Generado por el planificador local, sin IA.",
                    "respaldo_local": "Respuesta de respaldo local: la API de IA no respondio.",
                }.get(respuesta.get("modo", "local"), "Plan propuesto.")
            )
            if respuesta.get("error"):
                st.warning(f"Detalle tecnico: {capacidad_texto(respuesta['error'])}")
        historial.append({"role": "assistant", "content": texto})

        if respuesta.get("listo") and respuesta.get("proyecto"):
            plan = dict(respuesta["proyecto"])
            plan["modo"] = respuesta.get("modo", "local")
            st.session_state["plan_pendiente"] = plan
            st.rerun()

    plan = st.session_state.get("plan_pendiente")
    if plan:
        _vista_aprobacion(plan, proyecto)

    if historial and st.button("Reiniciar conversacion"):
        st.session_state["chat"] = []
        st.session_state.pop("plan_pendiente", None)
        st.rerun()


def capacidad_texto(valor: Any, maximo: int = 300) -> str:
    """Recorta un texto tecnico antes de mostrarlo (no se inyecta como HTML)."""
    texto = str(valor or "")
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

    for indice, fila in tabla.iterrows():
        nombre = str(fila.get("Actividad") or "").strip()
        if not nombre:
            continue
        id_original = str(fila.get("ID") or "").strip()
        existente = original.obtener(id_original) if id_original else None
        actividad = (
            Actividad.from_dict(existente.to_dict())
            if existente
            else Actividad(id="", nombre=nombre)
        )
        if not id_original or id_original in mapa.values():
            actividad.id = nuevo_id(nombre, nuevo.actividades.keys())
        else:
            actividad.id = id_original
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
        actividad.costo = _num(fila.get("Costo USD"))
        actividad.costo_equipos = _num(fila.get("Equipos USD"))
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


def tabla_editable(proyecto: Proyecto) -> Proyecto:
    seccion(
        "Actividades del proyecto",
        "Edita duraciones PERT (a / m / b), costos y predecesoras. El ID encadena "
        "dependencias y se conserva aunque no exista: el validador lo reporta.",
    )
    tabla = proyecto_a_dataframe(proyecto)
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
    with st.expander("Guardar / cargar proyecto (JSON)"):
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Descargar proyecto",
                data=json.dumps(proyecto.to_dict(), ensure_ascii=False, indent=2),
                file_name=sanitizar_nombre_archivo(proyecto.nombre),
                mime="application/json",
                width="stretch",
            )
        with col2:
            archivo = st.file_uploader(
                "Cargar proyecto", type=["json"], label_visibility="collapsed"
            )
            if archivo is not None:
                # Evita el bucle de recarga: Streamlit conserva el archivo entre
                # reruns y sin esta huella el proyecto se recargaria sin parar.
                contenido = archivo.getvalue()
                huella = hashlib.sha256(contenido).hexdigest()
                if st.session_state.get("_json_cargado") != huella:
                    try:
                        datos = validar_proyecto_json(cargar_json_bytes(contenido))
                        cargado = Proyecto.from_dict(datos)
                    except (ErrorDatos, ValueError) as error:
                        st.error(f"Archivo invalido: {escapar(error)}")
                    else:
                        st.session_state["_json_cargado"] = huella
                        nuevo_proyecto_sesion(cargado)
                        huerfanas = cargado.dependencias_huerfanas()
                        if huerfanas:
                            total = sum(len(v) for v in huerfanas.values())
                            st.warning(
                                f"Proyecto cargado con {total} dependencia(s) que apuntan a "
                                "IDs inexistentes. Se conservaron; revisalas en la pestana "
                                "Actividades."
                            )
                        else:
                            st.success("Proyecto cargado y validado.")
                        st.rerun()
