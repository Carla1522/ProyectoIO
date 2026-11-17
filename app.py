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
from core.modelo import Proyecto, cargar_base_ecuador, cargar_parametros
from core.seguridad import escapar, url_segura
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
    return copiloto_ia.aplicar_plan(plan["proyecto"])


def inicializar_estado() -> None:
    st.session_state.setdefault("_proyecto_revision", 0)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("calculado", True)
    if "proyecto" not in st.session_state:
        st.session_state["proyecto"] = proyecto_demo()


inicializar_estado()

# --------------------------------------------------------------- Navegacion
st.sidebar.markdown("#### Proyecto")
if st.sidebar.button("Cargar ejemplo: galpon de muebles", width="stretch"):
    componentes.nuevo_proyecto_sesion(proyecto_demo(), reiniciar_chat=True)
    st.rerun()
if st.sidebar.button("Nuevo proyecto vacio", width="stretch"):
    componentes.nuevo_proyecto_sesion(Proyecto(nombre="Nuevo proyecto"), reiniciar_chat=True)
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
    + ("IA conectada" if cfg_ia["proveedor"] != "local" else "modo local")
)
encabezado(
    proyecto.nombre or "Proyecto sin titulo",
    "Planificacion CPM/PERT, presupuesto y cumplimiento normativo del Ecuador",
    contexto,
)

tab_definir, tab_tabla, tab_resultados, tab_probabilidad, tab_costos = st.tabs(
    ["Definicion", "Actividades", "Cronograma", "Riesgo y plazo", "Presupuesto"]
)


# ------------------------------------------------------- 1. Definir proyecto
with tab_definir:
    with st.form("datos_proyecto"):
        col_nombre, col_desc = st.columns([1, 2], gap="large")
        with col_nombre:
            nombre = st.text_input("Nombre del proyecto", value=proyecto.nombre)
        with col_desc:
            descripcion = st.text_area(
                "Descripcion",
                value=proyecto.descripcion,
                height=84,
                placeholder="Ej: Galpon de 300 m2 para fabricar muebles en Ambato, con 8 empleados.",
            )
        if st.form_submit_button("Guardar datos"):
            proyecto.nombre = nombre.strip() or "Proyecto sin titulo"
            proyecto.descripcion = descripcion.strip()
            st.session_state["proyecto"] = proyecto
            st.rerun()

    st.divider()
    col_izq, col_der = st.columns([1.5, 1], gap="large")
    with col_izq:
        componentes.panel_copiloto(
            proyecto, incluir_opcionales=escenario.get("empleados", 0) > 0
        )
    with col_der:
        seccion("Estado del proyecto")
        tramites = sum(1 for a in proyecto.actividades.values() if a.tipo == "tramite")
        st.markdown(f"**{len(proyecto.actividades)} actividades** · {tramites} tramites publicos")

        etiquetas = copiloto_ia.detectar_etiquetas(
            f"{proyecto.nombre} {proyecto.descripcion}"
        )
        faltantes = tramites_obligatorios_faltantes(proyecto, etiquetas, BASE_ECUADOR)
        if faltantes:
            with st.expander(f"Tramites obligatorios sugeridos ({len(faltantes)})"):
                for tramite in faltantes:
                    st.markdown(f"- **{escapar(tramite['nombre'])}** · {escapar(tramite['entidad'])}")
        else:
            st.caption("No hay tramites obligatorios pendientes para este tipo de proyecto.")

        if st.button(
            "Armar plan base con el catalogo",
            width="stretch",
            help="Genera actividades privadas y tramites aplicables. Luego podras editarlos.",
        ):
            with st.spinner("Ensamblando actividades y tramites..."):
                plan = copiloto_ia.plan_local(
                    proyecto.descripcion or proyecto.nombre, escenario
                )
                plan["modo"] = "local"
                st.session_state["plan_pendiente"] = plan["proyecto"] | {"modo": "local"}
            st.rerun()

        st.divider()
        seccion("Como se construye el plan")
        st.markdown(
            "1. **Entrevista.** El copiloto identifica giro, ubicacion y tamano del proyecto.\n"
            "2. **Propuesta.** Combina actividades privadas con los tramites del catalogo y sus "
            "predecesoras legales.\n"
            "3. **Aprobacion.** Revisas y editas la tabla; nada se incorpora sin tu aprobacion.\n"
            "4. **Calculo.** El motor obtiene ruta critica, holguras, probabilidad y presupuesto."
        )

# ------------------------------------------------ 2. Actividades y validacion
with tab_tabla:
    proyecto_editado = componentes.tabla_editable(proyecto)
    if proyecto_editado.to_dict() != proyecto.to_dict():
        st.session_state["proyecto"] = proyecto_editado
        proyecto = proyecto_editado
        st.session_state["calculado"] = True

    componentes.panel_catalogo(proyecto)

    st.divider()
    problemas = validar(proyecto, BASE_ECUADOR, PARAMETROS)
    componentes.mostrar_problemas(problemas)

    huerfanas = proyecto.dependencias_huerfanas()
    if huerfanas:
        total = sum(len(v) for v in huerfanas.values())
        with st.expander(f"Dependencias conservadas sin destino ({total})", expanded=True):
            for ida, faltantes in huerfanas.items():
                st.markdown(
                    f'<div class="ec-item"><strong>{escapar(ida)}</strong> → '
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
            st.session_state["calculado"] = True
            st.rerun()
    with col_b:
        st.caption(
            "Tiempo esperado PERT te = (a + 4m + b) / 6 y varianza (b - a)^2 / 36. "
            "El cronograma se actualiza automaticamente al editar la tabla."
        )


# --------------------------------------------------------- Calculo unico
proyecto = st.session_state["proyecto"]
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

barra_meta(
    [
        ("Canton", str(escenario.get("canton", "sin definir"))),
        ("Actividades", f"{len(proyecto.actividades)} ({sum(1 for a in proyecto.actividades.values() if a.tipo == 'tramite')} tramites)"),
        ("Plazo estimado", f"{cpm['duracion']:.1f} dias" if cpm else "sin calcular"),
        ("Presupuesto", f"USD {costos['total']:,.2f}"),
        ("Catalogo", f"v{BASE_ECUADOR.get('version', '')}"),
    ]
)


# --------------------------------------------------------------- 3. Resultados
with tab_resultados:
    if not proyecto.actividades:
        st.info("Agrega actividades o usa el copiloto para empezar.")
    elif error_calculo:
        st.error(f"No se puede calcular: {escapar(error_calculo)}")
    elif cpm is None:
        st.warning("Corrige los errores de la pestana Actividades para ver el cronograma.")
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


# ------------------------------------------- 4. Probabilidad y simulacion
with tab_probabilidad:
    if not proyecto.actividades:
        st.info("Primero define las actividades del proyecto.")
    elif cpm is None:
        st.warning("El cronograma tiene errores; corrigelos antes de estimar probabilidades.")
    else:
        seccion(
            "Probabilidad de cumplir el plazo",
            "P(T <= plazo) con la aproximacion normal sobre la ruta critica.",
        )
        col_plazo, col_res = st.columns([1, 1.7], gap="large")
        with col_plazo:
            # Asegurar que el min_value sea al menos 1.0 y <= value (Bug 9)
            val = float(round(cpm["duracion"]))
            if val < 1.0: val = 1.0
            plazo = st.number_input(
                "Plazo objetivo (dias laborables)",
                min_value=1.0,
                max_value=max(3650.0, cpm["duracion"] * 5),
                value=val,
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


# ----------------------------------------------- 5. Costos y exportacion
with tab_costos:
    if not proyecto.actividades:
        st.info("Primero define las actividades del proyecto.")
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
        c6.metric("IVA", f"USD {costos['iva']:,.2f}")
        st.metric("Total del proyecto", f"USD {costos['total']:,.2f}")
        st.caption(
            f"Factor de costo empleador aplicado: {proyecto.factor_cargas(PARAMETROS):.4f} "
            "(aporte patronal, IECE/SECAP, fondos de reserva, decimos y vacaciones)."
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
                    file_name="informe_proyecto.xlsx",
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
                    file_name="informe_proyecto.pdf",
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
