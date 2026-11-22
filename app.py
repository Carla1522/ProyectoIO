"""ECUAPROJECT - Sistema de planificacion y presupuestacion de proyectos.

Aplicacion Streamlit que integra:

* un copiloto que entrevista y propone un plan editable,
* un catalogo normativo ecuatoriano con fuentes y nivel de verificacion,
* un motor CPM/PERT con ruta critica, holguras y probabilidad de cumplimiento,
* un presupuesto separado por naturaleza del costo y por canton,
* exportacion de informes a Excel y PDF.

La interfaz solo presenta resultados: todos los calculos provienen de
``core.calculos_cpm_pert`` y ``core.modelo``.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.calculos_cpm_pert import (
    CicloError,
    calcular_cpm,
    estadisticas_holgura,
    flujo_caja,
    plazo_para_probabilidad,
    probabilidad_exito,
    simular_reduccion,
    sugerencias_aceleracion,
)
from core.costos_cantonales import resumen_canton
from core.modelo import Actividad, Proyecto, cargar_base_ecuador, cargar_parametros
from core.seguridad import escapar, sanitizar_nombre_archivo, url_segura
from core.validador import ERROR, hay_errores, tramites_obligatorios_faltantes, validar
from services import copiloto_ia, exportador
from ui import componentes, graficos
from ui.estilos import aplicar_estilos, badge, barra_meta, encabezado, seccion

st.set_page_config(
    page_title="ECUAPROJECT · Planificacion CPM/PERT",
    layout="wide",
    initial_sidebar_state="expanded",
)
aplicar_estilos()

PARAMETROS = cargar_parametros()
BASE_ECUADOR = cargar_base_ecuador()


# ------------------------------------------------------------------- Estado
def proyecto_demo() -> Proyecto:
    plan = copiloto_ia.plan_local(
        "Quiero construir un galpon para fabricar muebles en Ambato",
        {"canton": "Ambato", "tamano_empresa": "micro", "area_m2": 300, "empleados": 8},
    )
    plan["proyecto"]["nombre"] = "Planta de Muebles en Ambato (Demo)"
    return copiloto_ia.aplicar_plan(plan["proyecto"])


def proyecto_pert_basico() -> Proyecto:
    proyecto = Proyecto(
        nombre="Planificacion manual PERT (Ejemplo A-E)",
        descripcion="Red PERT clasica de 5 actividades lista para editar.",
    )
    for ida, nombre, preds, a, m, b in (
        ("A", "Definicion y diseno inicial", [], 2.0, 4.0, 6.0),
        ("B", "Adquisicion de insumos", ["A"], 3.0, 5.0, 9.0),
        ("C", "Permisos y documentacion", ["A"], 1.0, 3.0, 8.0),
        ("D", "Ejecucion principal", ["B", "C"], 4.0, 6.0, 10.0),
        ("E", "Pruebas y entrega final", ["D"], 1.0, 2.0, 4.0),
    ):
        proyecto.agregar(
            Actividad(
                id=ida,
                nombre=nombre,
                predecesoras=preds,
                optimista=a,
                probable=m,
                pesimista=b,
                origen="manual",
            )
        )
    return proyecto


def inicializar_estado() -> None:
    st.session_state.setdefault("_proyecto_revision", 0)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("modo_manual", False)
    if "proyecto" not in st.session_state:
        st.session_state["proyecto"] = Proyecto(nombre="Nuevo proyecto", descripcion="")


inicializar_estado()

# --------------------------------------------------------------- Navegacion
st.sidebar.markdown("#### Proyecto")
if st.sidebar.button("Nuevo proyecto con IA", width="stretch"):
    st.session_state["modo_manual"] = False
    componentes.nuevo_proyecto_sesion(Proyecto(nombre="Nuevo proyecto"), reiniciar_chat=True)
    st.rerun()
if st.sidebar.button("Planificacion manual (PERT)", width="stretch"):
    st.session_state["modo_manual"] = True
    componentes.nuevo_proyecto_sesion(
        Proyecto(nombre="Planificacion manual PERT"), reiniciar_chat=True
    )
    st.rerun()
if st.sidebar.button("Cargar proyecto de ejemplo", width="stretch"):
    st.session_state["modo_manual"] = False
    componentes.nuevo_proyecto_sesion(proyecto_demo(), reiniciar_chat=True)
    st.session_state["proyecto_cargado_msg"] = (
        "Proyecto de ejemplo cargado (34 actividades). Revisa las pestanas "
        "Cronograma y Red, Presupuesto y Costos, Tabla de Actividades y Riesgo PERT."
    )
    st.rerun()
componentes.panel_guardar_cargar(st.session_state["proyecto"])

st.sidebar.divider()
proyecto: Proyecto = st.session_state["proyecto"]
escenario = componentes.sidebar_escenario(proyecto)

st.sidebar.divider()
st.sidebar.caption(
    "Las tasas y plazos provienen del catalogo normativo. Los valores marcados como "
    "estimacion deben confirmarse en la fuente oficial antes de presentar un "
    "presupuesto definitivo."
)

cfg_ia = copiloto_ia.configuracion()
contexto = (
    f"{escenario.get('canton', '')} · {len(proyecto.actividades)} actividades · "
    + ("IA conectada" if cfg_ia["proveedor"] != "local" else "Modo local")
)
es_inicio_vacio = (
    not proyecto.actividades
    and (proyecto.nombre or "").strip()
    in ("", "Nuevo proyecto", "Proyecto en blanco", "Proyecto sin titulo", "Planificacion manual PERT")
)
titulo_encabezado = (
    "Planificacion manual PERT"
    if es_inicio_vacio and st.session_state.get("modo_manual")
    else (
        "Planificacion, Cronograma y Presupuesto en Ecuador"
        if es_inicio_vacio
        else (proyecto.nombre or "Proyecto sin titulo")
    )
)
encabezado(
    titulo_encabezado,
    "Motor CPM/PERT, catalogo normativo de tramites y presupuesto laboral-tributario",
    contexto,
)

# --------------------------------------------------------- Calculo unico
problemas = validar(proyecto, BASE_ECUADOR, PARAMETROS)
cpm = None
error_calculo = None
if proyecto.actividades and not hay_errores(problemas):
    try:
        cpm = calcular_cpm(proyecto)
    except CicloError as error:
        cpm = None
        error_calculo = str(error)

costos = proyecto.resumen_costos(PARAMETROS, escenario)
flujo = (
    flujo_caja(cpm, costos["detalle"], administrativos=costos["administrativos"])
    if cpm
    else []
)

ETIQUETAS_PERSONERIA = {
    "persona_natural": "Persona natural",
    "sas": "S.A.S.",
    "compania": "Cia. Ltda. / S.A.",
}
ETIQUETAS_REGIMEN = {
    "general": "Regimen General",
    "rimpe_emprendedor": "RIMPE Emprendedor",
    "rimpe_negocio_popular": "RIMPE Negocio Popular",
}
pers_lbl = ETIQUETAS_PERSONERIA.get(str(escenario.get("tipo_personeria") or "persona_natural"), "Persona natural")
reg_lbl = ETIQUETAS_REGIMEN.get(str(escenario.get("regimen_tributario") or "general"), "Regimen General")

barra_meta(
    [
        ("Canton", str(escenario.get("canton", "sin definir"))),
        ("Perfil fiscal", f"{pers_lbl} · {reg_lbl}"),
        (
            "Actividades",
            f"{len(proyecto.actividades)} "
            f"({sum(1 for a in proyecto.actividades.values() if a.tipo == 'tramite')} tramites)"
            if proyecto.actividades
            else "0 (listo para planificar)",
        ),
        ("Plazo estimado", f"{cpm['duracion']:.1f} dias" if cpm else "Por definir"),
        ("Presupuesto", f"USD {costos['total']:,.2f}"),
    ]
)

msg_cargado = st.session_state.pop("proyecto_cargado_msg", "")
if msg_cargado:
    st.success(msg_cargado)
for aviso_cargado in st.session_state.pop("proyecto_cargado_avisos", []):
    st.warning(aviso_cargado)

etiqueta_tab_inicio = (
    "Planificacion manual" if st.session_state.get("modo_manual") else "Copiloto IA"
)
tab_copiloto, tab_cronograma, tab_presupuesto, tab_tabla, tab_probabilidad = st.tabs(
    [
        etiqueta_tab_inicio,
        "Cronograma y Red",
        "Presupuesto y Costos",
        "Tabla de Actividades",
        "Riesgo PERT",
    ]
)


# ------------------------------------------------------- 1. Planificacion / Copiloto
with tab_copiloto:
    if st.session_state.get("modo_manual"):
        col_form, col_estado = st.columns([1.85, 1], gap="large")
        with col_form:
            seccion(
                "Planificacion manual PERT",
                "Ingresa actividades una por una con sus predecesoras y tiempos (a, m, b). "
                "Luego explora la red, holguras, riesgo y costos en las pestanas superiores.",
            )
            componentes.formulario_actividad_manual(proyecto, key_prefix="inicio_manual")
            if proyecto.actividades:
                st.divider()
                seccion("Actividades registradas", "Edita o elimina filas en Tabla de Actividades.")
                resumen_manual = pd.DataFrame(
                    [
                        {
                            "ID": a.id,
                            "Actividad": a.nombre,
                            "Predecesoras": ", ".join(a.predecesoras) or "-",
                            "a": a.optimista,
                            "m": a.probable,
                            "b": a.pesimista,
                            "te": round(a.te, 2),
                            "Varianza": round(a.varianza, 4),
                        }
                        for a in proyecto.actividades.values()
                    ]
                )
                st.dataframe(resumen_manual, width="stretch", hide_index=True)
        with col_estado:
            seccion("Estado y accesos")
            if cpm:
                st.metric("Duracion esperada PERT", f"{cpm['duracion']:.2f} dias")
                st.metric("Desviacion estandar (sigma)", f"{cpm['sigma']:.2f} dias")
                st.caption(
                    f"Ruta critica: {' -> '.join(cpm['ruta_critica'])}"
                )
            elif not proyecto.actividades:
                st.markdown(
                    '<div class="ec-card">'
                    '<div class="ec-card-titulo">Modo manual PERT</div>'
                    "<p>Ideal para armar redes desde cero (actividades A, B, C...) o ejercicios "
                    "de Investigacion de Operaciones sin depender de la IA.</p>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Cargar ejemplo PERT basico (A-E)", width="stretch", key="pert_basico_inicio"):
                    componentes.nuevo_proyecto_sesion(proyecto_pert_basico(), reiniciar_chat=True)
                    st.rerun()
            else:
                componentes.mostrar_problemas(problemas)

            if proyecto.actividades and st.button(
                "Vaciar actividades", width="stretch", key="vaciar_manual"
            ):
                componentes.nuevo_proyecto_sesion(
                    Proyecto(nombre=proyecto.nombre, escenario=dict(proyecto.escenario)),
                    reiniciar_chat=True,
                )
                st.rerun()

            if st.button("Cambiar a Copiloto IA", width="stretch", key="ir_ia"):
                st.session_state["modo_manual"] = False
                st.rerun()
    else:
        if st.session_state.pop("plan_aprobado_exito", False):
            st.success(
                "Plan aprobado e incorporado con exito. Tus actividades y tramites ya estan en el sistema. "
                "Pasa a las pestañas superiores: Cronograma y Red, Presupuesto y Costos, o Tabla de Actividades."
            )

        col_chat, col_apoyo = st.columns([1.85, 1], gap="large")
        with col_chat:
            componentes.panel_copiloto(
                proyecto, incluir_opcionales=escenario.get("empleados", 0) > 0
            )
        with col_apoyo:
            seccion("Flujo y estado del proyecto")
            if not proyecto.actividades:
                st.markdown(
                    '<div class="ec-card">'
                    '<div class="ec-card-titulo">Como funciona</div>'
                    '<div class="ec-paso"><span class="ec-paso-num">1</span>'
                    "<span><strong>Describe tu proyecto</strong> en el copiloto o elige un sector de inicio.</span></div>"
                    '<div class="ec-paso"><span class="ec-paso-num">2</span>'
                    "<span><strong>Revisa y aprueba</strong> las actividades, tiempos PERT y tramites del Ecuador.</span></div>"
                    '<div class="ec-paso"><span class="ec-paso-num">3</span>'
                    "<span><strong>Evalua resultados</strong> en Cronograma, Presupuesto y Riesgo PERT, y exporta a Excel/PDF.</span></div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                tramites = sum(1 for a in proyecto.actividades.values() if a.tipo == "tramite")
                st.markdown(f"**{len(proyecto.actividades)} actividades** · {tramites} tramites publicos")

                etiquetas = copiloto_ia.detectar_etiquetas(
                    f"{proyecto.nombre} {proyecto.descripcion}"
                )
                if escenario.get("tipo_personeria") in ("sas", "compania"):
                    etiquetas.append("persona_juridica")
                faltantes = tramites_obligatorios_faltantes(proyecto, etiquetas, BASE_ECUADOR)
                if faltantes:
                    with st.expander(f"Tramites obligatorios sugeridos ({len(faltantes)})"):
                        for tramite in faltantes:
                            st.markdown(
                                f"- **{escapar(tramite['nombre'])}** · {escapar(tramite['entidad'])}"
                            )
                else:
                    st.caption("No hay tramites obligatorios pendientes para este perfil de proyecto.")

            if st.button(
                "Armar plan base con el catalogo",
                width="stretch",
                help="Genera actividades privadas y tramites aplicables segun la descripcion y escenario actual.",
            ):
                with st.spinner("Ensamblando actividades y tramites..."):
                    plan = copiloto_ia.plan_local(
                        proyecto.descripcion or proyecto.nombre,
                        escenario,
                        BASE_ECUADOR,
                        incluir_opcionales=escenario.get("empleados", 0) > 0,
                    )
                    st.session_state["plan_pendiente"] = plan["proyecto"] | {
                        "modo": "local",
                        "proveedor": "local",
                    }
                st.rerun()

            if st.button("Planificar manualmente (PERT)", width="stretch", key="ir_manual_panel"):
                st.session_state["modo_manual"] = True
                st.rerun()

            if not proyecto.actividades:
                if st.button("Explorar proyecto de ejemplo", width="stretch", key="demo_inicio"):
                    st.session_state["modo_manual"] = False
                    componentes.nuevo_proyecto_sesion(proyecto_demo(), reiniciar_chat=True)
                    st.session_state["proyecto_cargado_msg"] = (
                        "Proyecto de ejemplo cargado (34 actividades). Revisa las pestanas "
                        "Cronograma y Red, Presupuesto y Costos, Tabla de Actividades y Riesgo PERT."
                    )
                    st.rerun()

        plan_pendiente = st.session_state.get("plan_pendiente")
        if plan_pendiente:
            st.divider()
            componentes.vista_aprobacion(plan_pendiente, proyecto)


def _estado_sin_actividades(mensaje: str, clave_boton: str) -> None:
    st.info(mensaje)
    if st.button("Cargar proyecto de ejemplo", key=clave_boton):
        st.session_state["modo_manual"] = False
        componentes.nuevo_proyecto_sesion(proyecto_demo(), reiniciar_chat=True)
        st.rerun()


# ------------------------------------------------------- 2. Cronograma y Red
with tab_cronograma:
    if not proyecto.actividades:
        _estado_sin_actividades("Agrega actividades o usa el copiloto para empezar.", "demo_crono")
    elif error_calculo:
        st.error(f"No se puede calcular: {escapar(error_calculo)}")
    elif cpm is None:
        st.warning("Corrige los errores de la pestaña Tabla de Actividades para ver el cronograma.")
    else:
        holguras = estadisticas_holgura(cpm)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Duracion esperada",
            f"{cpm['duracion']:.1f} dias",
            help="Longitud de la ruta critica en dias laborables.",
        )
        c2.metric(
            "Costo total",
            f"USD {costos['total']:,.0f}",
            help=(
                f"Inversion privada USD {costos['privada']:,.0f} + "
                f"tramites USD {costos['tramites']:,.0f}."
            ),
        )
        c3.metric(
            "Actividades criticas",
            f"{holguras['criticas']} / {len(cpm['filas'])}",
            help="Holgura total igual a cero.",
        )
        c4.metric(
            "Desviacion estandar",
            f"{cpm['sigma']:.2f} d",
            help="Raiz de la varianza de la ruta critica seleccionada.",
        )

        st.divider()
        col_red, col_info = st.columns([2.2, 1], gap="large")
        with col_red:
            seccion(
                "Red de actividades",
                "Los nodos se ubican por inicio temprano y en carriles distintos cuando "
                "se solapan. El rojo es la ruta critica calculada.",
            )
            modo = st.radio(
                "Disposicion",
                ["Tiempo (dias)", "Dependencias"],
                horizontal=True,
                label_visibility="collapsed",
                key="modo_red",
            )
            st.plotly_chart(
                graficos.diagrama_red(
                    cpm, proyecto, modo="tiempo" if modo.startswith("Tiempo") else "dependencia"
                ),
                width="stretch",
            )
        with col_info:
            seccion("Ruta critica")
            for numero, ida in enumerate(cpm["ruta_critica"], start=1):
                fila = next((f for f in cpm["filas"] if f["id"] == ida), None)
                if fila:
                    st.markdown(
                        f'<div class="ec-item"><strong>{numero}. {escapar(fila["codigo"])}</strong> '
                        f'{escapar(fila["nombre"])} · {fila["te"]:.1f} d</div>',
                        unsafe_allow_html=True,
                    )
            st.metric("Holgura media", f"{holguras['holgura_media']:.1f} d")
            st.caption(
                f"{holguras['con_holgura']} actividades pueden atrasarse sin mover la fecha final."
            )

        seccion(
            "Gantt",
            "Barras solidas: duracion. Barras rayadas: holgura total desde el fin temprano. "
            "La linea punteada marca el fin esperado.",
        )
        st.plotly_chart(graficos.diagrama_gantt(cpm, proyecto), width="stretch")

        seccion("Tabla CPM/PERT")
        tabla = pd.DataFrame(cpm["filas"])[
            [
                "codigo", "nombre", "tipo", "predecesoras", "a", "m", "b", "te",
                "varianza", "es", "ef", "ls", "lf", "holgura", "holgura_libre", "critica",
            ]
        ]
        tabla.columns = [
            "Codigo", "Actividad", "Tipo", "Predecesoras", "a", "m", "b", "te",
            "Varianza", "ES", "EF", "LS", "LF", "Holgura total", "Holgura libre", "Critica",
        ]
        st.dataframe(
            tabla.style.apply(
                lambda fila: [
                    "background-color: #FBEEEE; color: #7F2F2F" if fila["Critica"] else ""
                    for _ in fila
                ],
                axis=1,
            ),
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Descargar tabla CPM (CSV)",
            data=tabla.to_csv(index=False).encode("utf-8"),
            file_name="tabla_cpm_pert.csv",
            mime="text/csv",
        )


# ------------------------------------------------------- 3. Presupuesto y Costos
with tab_presupuesto:
    if not proyecto.actividades:
        _estado_sin_actividades("Primero define las actividades del proyecto.", "demo_presup")
    elif cpm is None:
        st.warning("El cronograma tiene errores; corrigelos antes de presupuestar.")
    else:
        seccion(
            "Presupuesto por naturaleza del costo",
            "Cada actividad se clasifica una sola vez. El IVA no se aplica a tasas publicas "
            "y las tarifas municipales dependen del canton seleccionado.",
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Costos directos", f"USD {costos['directos']:,.2f}")
        c2.metric("Equipos", f"USD {costos['equipos']:,.2f}")
        c3.metric("Mano de obra cargada", f"USD {costos['mano_obra_incluida']:,.2f}")
        c4, c5, c6 = st.columns(3)
        c4.metric(
            "Gastos administrativos",
            f"USD {costos['administrativos']:,.2f}",
            help=f"{costos['admin_pct']:.1f}% sobre costos directos privados.",
        )
        c5.metric("Tramites y tasas", f"USD {costos['tramites']:,.2f}")
        c6.metric(
            "IVA (15%)",
            f"USD {costos['iva']:,.2f}",
            help=f"Base gravada USD {costos.get('base_iva', 0.0):,.2f} (excluye nomina y tasas publicas).",
        )
        st.metric("Total del proyecto", f"USD {costos['total']:,.2f}")
        st.caption(
            f"Cargas laborales proporcionales: {proyecto.factor_cargas(PARAMETROS):.4f} "
            "(IESS patronal, IECE/SECAP, fondos de reserva, 13ro y vacaciones) + "
            f"14to sueldo fijo USD {costos.get('decimo_cuarto_diario', 0.0):.2f}/dia por trabajador. "
            f"Base gravada de IVA: USD {costos.get('base_iva', 0.0):,.2f} (excluye nomina y tasas)."
        )

        info_canton = resumen_canton(escenario.get("canton"), PARAMETROS)
        if info_canton["disponible"]:
            estado_canton = (
                badge("ok", "Tarifario cargado")
                if info_canton["verificado"]
                else badge("advertencia", "Tarifas de referencia")
            )
            st.markdown(
                f'{estado_canton}<span class="ec-tenue">'
                f'{escapar(info_canton["entidad"])} · revisado '
                f'{escapar(info_canton["verificado_en"] or "sin fecha")}</span>',
                unsafe_allow_html=True,
            )
        else:
            st.warning(
                f"No hay tarifario cargado para {escapar(escenario.get('canton', ''))}. "
                "Los tramites municipales usan el costo de referencia del catalogo."
            )

        tarifas = costos.get("tarifas_cantonales") or []
        if tarifas:
            with st.expander(f"Trazabilidad de tasas cantonales ({len(tarifas)})"):
                tabla_tarifas = pd.DataFrame(tarifas)[
                    ["nombre", "canton", "origen", "costo", "nota"]
                ]
                tabla_tarifas.columns = ["Actividad", "Canton", "Origen", "USD", "Detalle"]
                st.dataframe(
                    tabla_tarifas.style.format({"USD": "{:,.2f}"}),
                    width="stretch",
                    hide_index=True,
                )
        advertencias = costos.get("advertencias_cantonales") or []
        if advertencias:
            with st.expander(f"Advertencias de tarifas ({len(advertencias)})"):
                for aviso in advertencias[:12]:
                    st.markdown(
                        f'<div class="ec-item">{badge("advertencia", "Tarifa")}'
                        f'{escapar(aviso["mensaje"])}</div>',
                        unsafe_allow_html=True,
                    )

        seccion("Flujo de caja semanal")
        st.plotly_chart(graficos.flujo_caja_grafico(flujo), width="stretch")
        if flujo:
            diferencia = flujo[-1]["acumulado"] - costos["base"]
            if abs(diferencia) <= 0.05:
                st.caption(
                    f"Conciliacion verificada: la suma del flujo (USD {flujo[-1]['acumulado']:,.2f}) "
                    f"coincide con el presupuesto base (USD {costos['base']:,.2f})."
                )
            else:
                st.warning(
                    f"El flujo difiere del presupuesto en USD {diferencia:,.2f}. "
                    "Revisa costos con duracion cero o actividades sin costo."
                )

        col_tabla, col_fuentes = st.columns([1.35, 1], gap="large")
        with col_tabla:
            seccion("Detalle por actividad")
            detalle = pd.DataFrame(costos["detalle"]).rename(
                columns={
                    "nombre": "Actividad",
                    "directo": "Directo USD",
                    "equipos": "Equipos USD",
                    "mano_obra": "Mano de obra USD",
                    "subtotal": "Subtotal USD",
                }
            )
            columnas = ["Actividad", "Directo USD", "Equipos USD", "Mano de obra USD", "Subtotal USD"]
            st.dataframe(
                detalle[columnas].style.format({c: "{:,.2f}" for c in columnas[1:]}),
                width="stretch",
                hide_index=True,
            )
        with col_fuentes:
            seccion("Respaldo normativo")
            catalogo = {t["id"]: t for t in BASE_ECUADOR["tramites"]}
            tramites_proyecto = [a for a in proyecto.actividades.values() if a.tipo == "tramite"]
            if not tramites_proyecto:
                st.caption("El proyecto no incluye tramites publicos.")
            for actividad in tramites_proyecto[:12]:
                registro = catalogo.get(actividad.id, {})
                valor_tipo = registro.get("valor_tipo", "")
                estado = (
                    badge("ok", "Oficial")
                    if valor_tipo == "oficial"
                    else badge("advertencia", "Estimacion")
                )
                enlace = url_segura(actividad.fuente_url)
                st.markdown(
                    f'<div class="ec-item">{estado}<strong>{escapar(actividad.nombre)}</strong><br>'
                    f'<span class="ec-tenue">{escapar(actividad.entidad)} · '
                    f'USD {actividad.costo:.2f} · revisado '
                    f'{escapar(registro.get("verificado_en", "s/f"))}</span><br>'
                    + (f'<a href="{enlace}" target="_blank" rel="noopener noreferrer">'
                       "Fuente institucional</a>" if enlace else "Sin enlace validado.")
                    + "</div>",
                    unsafe_allow_html=True,
                )
            if len(tramites_proyecto) > 12:
                st.caption(
                    f"Se muestran 12 de {len(tramites_proyecto)} tramites; el informe incluye todos."
                )

        st.divider()
        seccion("Informes")
        observaciones = [p for p in problemas if p.nivel == ERROR]
        col_x, col_p = st.columns(2)
        prob_excel = probabilidad_exito(cpm, float(round(cpm["duracion"])))
        with col_x:
            try:
                excel = exportador.exportar_excel(
                    proyecto, cpm, costos, flujo, probabilidad=prob_excel, problemas=problemas
                )
                st.download_button(
                    "Descargar Excel (presupuesto + CPM)",
                    data=excel,
                    file_name=sanitizar_nombre_archivo(proyecto.nombre, extension=".xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
            except ImportError:
                st.warning("Instala openpyxl para exportar a Excel: pip install openpyxl")
            except Exception as error:
                st.error(f"No se pudo generar el Excel: {type(error).__name__}: {escapar(error)}")
        with col_p:
            try:
                plazo_pdf = float(round(cpm["duracion"]))
                prob_pdf = probabilidad_exito(cpm, plazo_pdf)
                pdf = exportador.exportar_pdf(
                    proyecto, cpm, costos, flujo, prob_pdf, problemas
                )
                st.download_button(
                    "Descargar PDF ejecutivo",
                    data=pdf,
                    file_name=sanitizar_nombre_archivo(proyecto.nombre, extension=".pdf"),
                    mime="application/pdf",
                    width="stretch",
                )
            except ImportError:
                st.warning("Instala reportlab para exportar a PDF: pip install reportlab")
            except Exception as error:
                st.error(f"No se pudo generar el PDF: {type(error).__name__}: {escapar(error)}")

        if observaciones:
            with st.expander(f"Observaciones que se incluyen en el informe ({len(observaciones)})"):
                for problema in observaciones:
                    st.markdown(f"- {escapar(problema.mensaje)}")
        else:
            st.caption("El informe incluye la validacion del proyecto y las fuentes normativas.")


# ------------------------------------------------------- 4. Tabla de Actividades y Ley
with tab_tabla:
    with st.expander("Agregar actividad manual (PERT)", expanded=not proyecto.actividades):
        componentes.formulario_actividad_manual(proyecto, key_prefix="tabla_manual")

    proyecto_editado = componentes.tabla_editable(proyecto)
    if proyecto_editado.to_dict() != proyecto.to_dict():
        st.session_state["proyecto"] = proyecto_editado
        st.rerun()

    componentes.panel_catalogo(proyecto)

    st.divider()
    componentes.mostrar_problemas(problemas)

    huerfanas = proyecto.dependencias_huerfanas()
    if huerfanas:
        total = sum(len(v) for v in huerfanas.values())
        with st.expander(f"Dependencias conservadas sin destino ({total})", expanded=True):
            for ida, faltantes in huerfanas.items():
                st.markdown(
                    f'<div class="ec-item"><strong>{escapar(ida)}</strong> -> '
                    f'{escapar(", ".join(faltantes))}</div>',
                    unsafe_allow_html=True,
                )
            st.caption(
                "No se eliminan automaticamente. Corrige el ID en la tabla o borra la "
                "referencia cuando estes seguro de que ya no aplica."
            )

    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("Recalcular", type="primary", width="stretch"):
            st.rerun()
    with col_b:
        st.caption(
            "Tiempo esperado PERT te = (a + 4m + b) / 6 y varianza (b - a)^2 / 36. "
            "El cronograma se actualiza automaticamente al editar la tabla."
        )


# ------------------------------------------------------- 5. Riesgo PERT
with tab_probabilidad:
    if not proyecto.actividades:
        _estado_sin_actividades("Primero define las actividades del proyecto.", "demo_riesgo")
    elif cpm is None:
        st.warning("El cronograma tiene errores; corrigelos antes de estimar probabilidades.")
    else:
        seccion(
            "Probabilidad de cumplir el plazo",
            "P(T <= plazo) con la aproximacion normal sobre la ruta critica.",
        )
        col_plazo, col_res = st.columns([1, 1.7], gap="large")
        with col_plazo:
            duracion_redondeada = float(round(cpm["duracion"]))
            plazo = st.number_input(
                "Plazo objetivo (dias laborables)",
                min_value=0.0,
                max_value=max(3650.0, duracion_redondeada * 5, 10.0),
                value=max(0.0, duracion_redondeada),
                step=1.0,
            )
            resultado = probabilidad_exito(cpm, plazo)
        with col_res:
            c1, c2, c3 = st.columns(3)
            c1.metric("Valor Z", f"{resultado['z']:.2f}")
            c2.metric("Probabilidad", f"{resultado['probabilidad'] * 100:.1f}%")
            c3.metric("Holgura vs plazo", f"{resultado['holgura_plazo']:.1f} d")
            if resultado["probabilidad"] >= 0.8:
                st.success("El plazo es alcanzable con margen razonable (80% o mas).")
            elif resultado["probabilidad"] >= 0.5:
                st.warning("Plazo ajustado: la probabilidad esta entre 50% y 80%.")
            else:
                st.error("Plazo poco viable: la probabilidad es menor al 50%.")

        st.plotly_chart(
            graficos.campana_gauss(cpm, plazo, resultado["probabilidad"]),
            width="stretch",
        )

        with st.expander("Supuestos estadisticos del modelo PERT"):
            st.markdown(
                f"- Las duraciones son variables aleatorias independientes con media "
                f"`te = (a + 4m + b) / 6` y varianza `((b - a) / 6)^2`.\n"
                f"- La duracion del proyecto se aproxima por la ruta critica "
                f"(`{cpm['duracion']:.2f}` dias) y su varianza es la suma de las varianzas "
                f"de esa ruta (`{cpm['varianza']:.2f}`), no la de todas las actividades criticas.\n"
                f"- Por el teorema central del limite, la suma se aproxima a una normal: "
                f"`Z = (plazo - Te) / sigma`, con `sigma = {cpm['sigma']:.2f}` dias.\n"
                "- La aproximacion pierde precision si hay rutas casi criticas en paralelo o "
                "correlacion entre actividades; en esos casos conviene una simulacion Monte Carlo."
            )

        st.divider()
        seccion("Simulador de aceleracion")
        col_obj, col_aco = st.columns([1, 2], gap="large")
        reduccion = max(cpm["duracion"] - plazo, 0.0)
        with col_obj:
            objetivo = st.slider("Probabilidad objetivo", 0.5, 0.99, 0.80, 0.01)
            plazo_necesario = plazo_para_probabilidad(cpm, objetivo)
            st.metric(f"Plazo para {objetivo * 100:.0f}%", f"{plazo_necesario:.1f} dias")
            if reduccion > 0:
                st.write(f"Necesitas recortar **{reduccion:.1f} dias** respecto del tiempo esperado.")
            else:
                st.write("El plazo declarado ya supera el tiempo esperado.")
        with col_aco:
            if reduccion > 0:
                sugerencias = sugerencias_aceleracion(cpm, reduccion)
                st.markdown("**Actividades criticas donde conviene intervenir**")
                for sugerencia in sugerencias:
                    st.info(sugerencia["mensaje"])
                if st.button("Simular aceleracion y recalcular", width="stretch"):
                    reducciones = {s["id"]: s["recorte_dias"] for s in sugerencias}
                    simulado = simular_reduccion(proyecto, reducciones)
                    cpm_sim = calcular_cpm(simulado)
                    nueva = probabilidad_exito(cpm_sim, plazo)
                    c1, c2, c3 = st.columns(3)
                    c1.metric(
                        "Nueva duracion",
                        f"{cpm_sim['duracion']:.1f} d",
                        delta=f"{cpm_sim['duracion'] - cpm['duracion']:.1f}",
                    )
                    c2.metric(
                        "Nueva probabilidad",
                        f"{nueva['probabilidad'] * 100:.1f}%",
                        delta=f"{(nueva['probabilidad'] - resultado['probabilidad']) * 100:.1f} pts",
                    )
                    c3.metric("Nuevo Z", f"{nueva['z']:.2f}")
                    st.caption(
                        "La simulacion acorta el tiempo esperado de cada actividad, conserva la "
                        "forma PERT y recalcula todo el grafo. No modifica el proyecto guardado."
                    )
            else:
                st.success("No hace falta acelerar: el plazo es mayor que la duracion esperada.")
