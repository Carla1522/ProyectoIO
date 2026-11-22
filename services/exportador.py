"""Exportacion del proyecto a Excel y PDF.

Los informes se construyen a partir de los resultados del motor (no vuelven a
calcular nada) e incluyen proyecto, actividades CPM/PERT, ruta critica,
presupuesto por naturaleza, flujo de caja, probabilidad de cumplimiento,
gantt y observaciones de validacion.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from core.modelo import Proyecto, cargar_base_ecuador

AZUL = "#1F3A4D"
GRIS = "#5F6B76"
ROJO = "#A23B3B"
GRIS_CLARO = "#EEF1F4"


def _texto(valor: Any) -> str:
    return escape(str(valor or ""))


def _celda_segura(valor: Any) -> Any:
    """Evita inyeccion de formulas en Excel (= + - @)."""
    if isinstance(valor, str):
        val = valor.strip()
        if val.startswith(("=", "+", "-", "@")):
            return "'" + val
    return valor


def _catalogo() -> Dict[str, Any]:
    try:
        return cargar_base_ecuador()
    except Exception:  # el informe no debe fallar por un catalogo ausente
        return {"tramites": []}


def _resumen_texto(
    cpm: Dict[str, Any],
    costos: Dict[str, Any],
    proyecto: Proyecto,
    probabilidad: Optional[Dict[str, Any]] = None,
) -> List[str]:
    lineas = [
        f"Proyecto: {proyecto.nombre}",
        f"Canton del escenario: {proyecto.escenario.get('canton', 'sin definir')}",
        f"Personeria / Regimen: {proyecto.escenario.get('tipo_personeria', 'persona_natural')} / "
        f"{proyecto.escenario.get('regimen_tributario', 'general')}",
        f"Fecha de generacion: {date.today().isoformat()}",
        f"Actividades: {len(cpm['filas'])} "
        f"({sum(1 for f in cpm['filas'] if f['tipo'] == 'tramite')} tramites publicos)",
        f"Duracion esperada: {cpm['duracion']:.2f} dias laborables",
        f"Desviacion estandar de la ruta critica: {cpm['sigma']:.2f} dias",
        f"Costos directos: USD {costos['directos']:,.2f}",
        f"Equipos: USD {costos['equipos']:,.2f}",
        f"Mano de obra cargada: USD {costos['mano_obra_incluida']:,.2f}",
        f"Gastos administrativos ({costos['admin_pct']:.1f}%): USD {costos['administrativos']:,.2f}",
        f"Inversion privada: USD {costos['privada']:,.2f}",
        f"Tramites y tasas publicas: USD {costos['tramites']:,.2f}",
        f"Base gravada IVA (excluye nomina y tasas): USD {costos.get('base_iva', 0.0):,.2f}",
        f"IVA: USD {costos['iva']:,.2f}",
        f"Total del proyecto: USD {costos['total']:,.2f}",
        "Las tasas cantonales se aplican segun el canton del escenario; los valores "
        "marcados como estimacion deben confirmarse en la fuente oficial.",
        "Ruta critica: " + " -> ".join(
            next(
                (f"{f['codigo']} {f['nombre']}" for f in cpm["filas"] if f["id"] == ida),
                ida,
            )
            for ida in cpm["ruta_critica"]
        ),
    ]
    if probabilidad:
        lineas.append(
            f"Plazo evaluado: {probabilidad['plazo']:.1f} dias · "
            f"Z = {probabilidad['z']:.3f} · "
            f"P(cumplir) = {probabilidad['probabilidad'] * 100:.1f}%"
        )
    return lineas


# ------------------------------------------------------------------- Excel
def exportar_excel(
    proyecto: Proyecto,
    cpm: Dict[str, Any],
    costos: Dict[str, Any],
    flujo: Optional[List[Dict[str, Any]]] = None,
    probabilidad: Optional[Dict[str, Any]] = None,
    problemas: Optional[List[Any]] = None,
) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    libro = Workbook()
    cabecera_fill = PatternFill("solid", fgColor="1F3A4D")
    cabecera_font = Font(color="FFFFFF", bold=True)

    def escribir_cabecera(hoja, columnas: List[str]) -> None:
        hoja.append(columnas)
        for indice, _ in enumerate(columnas, start=1):
            celda = hoja.cell(row=1, column=indice)
            celda.fill = cabecera_fill
            celda.font = cabecera_font
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        hoja.freeze_panes = "A2"

    # Resumen
    hoja = libro.active
    if hoja is None:  # openpyxl siempre crea una hoja; se cubre por tipado
        hoja = libro.create_sheet("Resumen")
    hoja.title = "Resumen"
    hoja.append(["ECUAPROJECT - Informe de planificacion CPM/PERT"])
    hoja["A1"].font = Font(bold=True, size=14)
    for linea in _resumen_texto(cpm, costos, proyecto, probabilidad):
        hoja.append([linea])
    if probabilidad:
        hoja.append([])
        hoja.append(["Supuestos PERT"])
        hoja.append([
            "Duraciones independientes; media te=(a+4m+b)/6; varianza ((b-a)/6)^2; "
            "la duracion del proyecto se aproxima por una normal con la media y la "
            "varianza de la ruta critica."
        ])
    hoja.column_dimensions["A"].width = 120

    costos_por_id = {fila["id"]: fila for fila in costos["detalle"]}

    # Actividades
    hoja = libro.create_sheet("Actividades CPM")
    escribir_cabecera(
        hoja,
        [
            "Codigo", "ID", "Actividad", "Tipo", "Entidad", "Predecesoras", "a", "m", "b",
            "te", "Varianza", "ES", "EF", "LS", "LF", "Holgura total", "Holgura libre",
            "Critica", "Costo total USD",
        ],
    )
    for fila in cpm["filas"]:
        hoja.append([
            _celda_segura(fila.get("codigo", "")), _celda_segura(fila["id"]), _celda_segura(fila["nombre"]),
            _celda_segura(fila["tipo"]), _celda_segura(fila["entidad"]),
            _celda_segura(str(fila["predecesoras"])), fila["a"], fila["m"], fila["b"], fila["te"],
            fila["varianza"], fila["es"], fila["ef"], fila["ls"], fila["lf"],
            fila["holgura"], fila["holgura_libre"], "SI" if fila["critica"] else "NO",
            costos_por_id.get(fila["id"], {}).get("subtotal", 0.0),
        ])
    anchos = [8, 24, 44, 10, 30, 26, 6, 6, 6, 7, 9, 7, 7, 7, 7, 9, 9, 8, 15]
    for indice, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho
    for fila in hoja.iter_rows(min_row=2):
        if fila[17].value == "SI":
            for celda in fila:
                celda.font = Font(color="A23B3B", bold=True)

    # Presupuesto
    hoja = libro.create_sheet("Presupuesto")
    escribir_cabecera(
        hoja,
        ["Codigo", "ID", "Actividad", "Tipo", "Costos directos", "Equipos",
         "Mano de obra", "Subtotal"],
    )
    for detalle in costos["detalle"]:
        fila_cpm = next((f for f in cpm["filas"] if f["id"] == detalle["id"]), {})
        hoja.append([
            _celda_segura(fila_cpm.get("codigo", "")), _celda_segura(detalle["id"]), _celda_segura(detalle["nombre"]),
            _celda_segura(fila_cpm.get("tipo", "")), detalle["directo"], detalle["equipos"],
            detalle["mano_obra"], detalle["subtotal"],
        ])
    hoja.append([])
    for etiqueta, valor in (
        ("Costos directos privados", costos["directos"]),
        ("Equipos", costos["equipos"]),
        ("Mano de obra cargada", costos["mano_obra_incluida"]),
        (f"Gastos administrativos ({costos['admin_pct']:.1f}%)", costos["administrativos"]),
        ("Subtotal inversion privada", costos["privada"]),
        ("Tramites y tasas", costos["tramites"]),
        ("Base gravada IVA (sin nomina)", costos.get("base_iva", 0.0)),
        ("IVA", costos["iva"]),
        ("TOTAL", costos["total"]),
    ):
        hoja.append(["", "", "", "", "", "", etiqueta, valor])
    for indice, ancho in enumerate([8, 24, 44, 10, 16, 12, 18, 14], start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho
    for fila in hoja.iter_rows(min_row=2, min_col=5, max_col=8):
        for celda in fila:
            celda.number_format = '#,##0.00'
    suma_detalle = sum(detalle["subtotal"] for detalle in costos["detalle"])
    diferencia = round(
        costos["total"]
        - suma_detalle
        - costos["administrativos"]
        - costos["iva"],
        2,
    )
    hoja.append([])
    hoja.append(["", "", "", "", "", "", "Suma del detalle", round(suma_detalle, 2)])
    hoja.append(["", "", "", "", "", "", "Diferencia de conciliacion", diferencia])
    hoja.cell(row=hoja.max_row, column=6).number_format = '#,##0.00'
    hoja.cell(row=hoja.max_row, column=8).number_format = '#,##0.00'
    hoja.cell(row=hoja.max_row - 1, column=8).number_format = '#,##0.00'

    # Cronograma con grafico de barras apiladas (inicio + duracion)
    hoja = libro.create_sheet("Cronograma")
    escribir_cabecera(hoja, ["Actividad", "Inicio", "Duracion", "Fin", "Critica"])
    for fila in cpm["filas"]:
        hoja.append([
            _celda_segura(f"{fila.get('codigo', '')} {fila['nombre'][:40]}"),
            fila["es"], fila["te"], fila["ef"], "SI" if fila["critica"] else "NO",
        ])
    hoja.freeze_panes = "A2"
    for indice, ancho in enumerate([46, 10, 11, 10, 8], start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho
    try:
        from openpyxl.chart import BarChart, Reference

        if cpm["filas"]:
            grafico = BarChart()
            grafico.type = "bar"
            grafico.grouping = "stacked"
            grafico.overlap = 100
            grafico.title = "Cronograma (inicio temprano + duracion)"
            grafico.x_axis.title = "Dias laborables"
            datos = Reference(hoja, min_col=2, max_col=3, min_row=1, max_row=hoja.max_row)
            categorias = Reference(hoja, min_col=1, min_row=2, max_row=hoja.max_row)
            grafico.add_data(datos, titles_from_data=True)
            grafico.set_categories(categorias)
            grafico.height = min(18, 4 + 0.35 * len(cpm["filas"]))
            grafico.width = 24
            if grafico.series:
                grafico.series[0].graphicalProperties.noFill = True
                grafico.series[0].graphicalProperties.line.noFill = True
            hoja.add_chart(grafico, "G2")
    except Exception:
        # El informe sigue siendo valido aunque la version de openpyxl no
        # permita dibujar el grafico.
        pass

    # Ruta critica
    hoja = libro.create_sheet("Ruta critica")
    escribir_cabecera(hoja, ["#", "Codigo", "Actividad", "Inicio", "Fin", "Duracion", "Costo USD"])
    for numero, ida in enumerate(cpm["ruta_critica"], start=1):
        fila = next((f for f in cpm["filas"] if f["id"] == ida), None)
        if fila:
            hoja.append([
                numero, _celda_segura(fila.get("codigo", "")), _celda_segura(fila["nombre"]), fila["es"], fila["ef"],
                fila["te"], costos_por_id.get(ida, {}).get("subtotal", 0.0),
            ])
    for indice, ancho in enumerate([5, 9, 45, 9, 9, 10, 12], start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho

    # Flujo de caja
    if flujo:
        hoja = libro.create_sheet("Flujo de caja")
        escribir_cabecera(hoja, ["Semana", "Costo semanal USD", "Acumulado USD"])
        for semana in flujo:
            hoja.append([semana["semana"], semana["costo"], semana["acumulado"]])
        for indice, ancho in enumerate([10, 20, 18], start=1):
            hoja.column_dimensions[get_column_letter(indice)].width = ancho

    # Fuentes normativas
    hoja = libro.create_sheet("Fuentes normativas")
    escribir_cabecera(
        hoja,
        ["Actividad", "Entidad", "Nivel", "Normativa", "URL", "Costo de referencia",
         "Origen del costo", "Revisado"],
    )
    catalogo = {t["id"]: t for t in _catalogo().get("tramites", [])}
    tarifas = {t["id"]: t for t in costos.get("tarifas_cantonales", [])}
    for actividad in proyecto.actividades.values():
        if actividad.tipo != "tramite":
            continue
        registro = catalogo.get(actividad.id, {})
        tarifa = tarifas.get(actividad.id, {})
        hoja.append([
            _celda_segura(actividad.nombre), _celda_segura(actividad.entidad), _celda_segura(actividad.nivel or actividad.categoria),
            _celda_segura(actividad.fuente_normativa), _celda_segura(actividad.fuente_url),
            _celda_segura(str(actividad.costo_nota or actividad.costo)),
            _celda_segura(tarifa.get("origen", registro.get("valor_tipo", "referencia"))),
            _celda_segura(registro.get("verificado_en", "")),
        ])
    for indice, ancho in enumerate([42, 32, 18, 48, 42, 46, 18, 12], start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho

    # Observaciones
    hoja = libro.create_sheet("Observaciones")
    escribir_cabecera(hoja, ["Severidad", "Codigo", "Mensaje", "Actividad"])
    for problema in problemas or []:
        hoja.append([
            _celda_segura(getattr(problema, "nivel", "")),
            _celda_segura(getattr(problema, "codigo", "")),
            _celda_segura(getattr(problema, "mensaje", str(problema))),
            _celda_segura(getattr(problema, "actividad", "") or ""),
        ])
    for indice, ancho in enumerate([14, 28, 90, 26], start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho

    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


# --------------------------------------------------------------------- PDF
def _gantt_dibujos(cpm: Dict[str, Any], max_filas: int = 32) -> List[Any]:
    """Construye uno o varios dibujos de Gantt con primitivas de reportlab."""
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.units import cm

    filas = cpm["filas"]
    dibujos: List[Any] = []
    duracion = max(float(cpm["duracion"]), 1.0)
    codigos_criticos = set(cpm["ruta_critica"])

    for inicio in range(0, len(filas), max_filas):
        bloque = filas[inicio : inicio + max_filas]
        fila_h = 0.42 * cm
        alto = (len(bloque) + 2) * fila_h + 0.6 * cm
        ancho = 26.0 * cm
        dibujo = Drawing(ancho, alto)
        x0, x1 = 2.2 * cm, ancho - 1.0 * cm
        escala = (x1 - x0) / duracion

        # Eje superior
        y_base = alto - fila_h
        dibujo.add(Line(x0, y_base, x1, y_base, strokeColor=colors.HexColor("#B8C1C8"),
                        strokeWidth=0.6))
        paso = 5
        dia = 0
        while dia <= duracion:
            x = x0 + dia * escala
            dibujo.add(Line(x, y_base - 0.08 * cm, x, y_base + 0.08 * cm,
                            strokeColor=colors.HexColor("#B8C1C8"), strokeWidth=0.4))
            dibujo.add(String(x + 0.05 * cm, y_base + 0.12 * cm, f"{dia}d",
                              fontSize=5.5, fillColor=colors.HexColor(GRIS)))
            dia += paso

        for indice, fila in enumerate(bloque):
            y = y_base - (indice + 1) * fila_h
            dibujo.add(String(0.1 * cm, y + 0.12 * cm, fila.get("codigo", ""),
                              fontSize=6, fillColor=colors.HexColor(GRIS)))
            if fila["critica"]:
                color = colors.HexColor(ROJO)
            elif fila["tipo"] == "tramite":
                color = colors.HexColor("#A9793F")
            else:
                color = colors.HexColor("#3C7089")
            x = x0 + float(fila["es"]) * escala
            ancho_barra = max(float(fila["te"]) * escala, 0.8)
            dibujo.add(Rect(x, y + 0.06 * cm, ancho_barra, 0.26 * cm,
                            fillColor=color, strokeColor=None))
            if fila["holgura"] > 0:
                dibujo.add(Rect(
                    x + ancho_barra, y + 0.06 * cm,
                    max(float(fila["holgura"]) * escala, 0.3), 0.26 * cm,
                    fillColor=colors.HexColor("#DDE2E6"), strokeColor=None,
                ))
            if fila["id"] in codigos_criticos:
                dibujo.add(String(
                    min(x + ancho_barra + 0.1 * cm, x1 - 0.2 * cm),
                    y + 0.12 * cm, "C", fontSize=5.5, fillColor=colors.HexColor(ROJO),
                ))

        # Linea de fin esperado
        x_fin = x0 + duracion * escala
        dibujo.add(Line(x_fin, y_base, x_fin, y_base - len(bloque) * fila_h,
                        strokeColor=colors.HexColor(ROJO), strokeWidth=0.7,
                        strokeDashArray=[2, 2]))
        dibujos.append(dibujo)
    return dibujos


def exportar_pdf(
    proyecto: Proyecto,
    cpm: Dict[str, Any],
    costos: Dict[str, Any],
    flujo: Optional[List[Dict[str, Any]]] = None,
    probabilidad: Optional[Dict[str, Any]] = None,
    problemas: Optional[List[Any]] = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.1 * cm,
        title=proyecto.nombre,
        author="ECUAPROJECT",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("Titulo", parent=estilos["Title"], fontSize=17,
                            textColor=colors.HexColor(AZUL), spaceAfter=8)
    subtitulo = ParagraphStyle("Sub", parent=estilos["Heading2"], fontSize=11,
                               textColor=colors.HexColor(AZUL), spaceBefore=10, spaceAfter=5)
    normal = ParagraphStyle("Normal2", parent=estilos["BodyText"], fontSize=8.5, leading=12)
    pie = ParagraphStyle("Pie", parent=estilos["Italic"], fontSize=7, textColor=colors.HexColor(GRIS),
                         leading=9)
    celda = ParagraphStyle("Celda", parent=normal, fontSize=7, leading=8.5)

    elementos: List[Any] = [
        Paragraph("Informe de planificacion CPM/PERT", titulo),
        Paragraph(_texto(proyecto.nombre), estilos["Heading2"]),
        Spacer(1, 5),
    ]
    for linea in _resumen_texto(cpm, costos, proyecto, probabilidad):
        elementos.append(Paragraph(_texto(linea), normal))

    # Tablero de indicadores
    kpis = Table(
        [
            ["Duracion esperada", "Desviacion sigma", "Actividades criticas", "Total del proyecto"],
            [
                f"{cpm['duracion']:.1f} dias",
                f"{cpm['sigma']:.2f} dias",
                f"{len(cpm['actividades_criticas'])} de {len(cpm['filas'])}",
                f"USD {costos['total']:,.2f}",
            ],
        ],
        colWidths=[6.0 * cm, 5.4 * cm, 6.2 * cm, 6.2 * cm],
    )
    kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GRIS_CLARO)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(GRIS)),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, 1), 10),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor(AZUL)),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DEE4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elementos.append(Spacer(1, 8))
    elementos.append(kpis)

    if probabilidad:
        elementos.append(Paragraph("Supuestos estadisticos", subtitulo))
        elementos.append(Paragraph(
            "Las duraciones se tratan como variables independientes con media "
            "te=(a+4m+b)/6 y varianza ((b-a)/6)^2. La duracion del proyecto se aproxima "
            "por la ruta critica y, por el teorema central del limite, por una distribucion "
            "normal con media Te y desviacion sigma. La probabilidad de cumplir el plazo es "
            "Phi(Z), con Z=(plazo-Te)/sigma. La aproximacion puede perder precision si hay "
            "rutas casi criticas o actividades correlacionadas.",
            normal,
        ))
        tabla_prob = Table(
            [
                ["Plazo evaluado", "Z", "P(cumplir el plazo)", "Holgura vs plazo"],
                [
                    f"{probabilidad['plazo']:.1f} dias",
                    f"{probabilidad['z']:.3f}",
                    f"{probabilidad['probabilidad'] * 100:.1f}%",
                    f"{probabilidad['holgura_plazo']:.1f} dias",
                ],
            ],
            colWidths=[6.0 * cm, 4.0 * cm, 6.0 * cm, 6.0 * cm],
        )
        tabla_prob.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D1D7")),
        ]))
        elementos.append(Spacer(1, 6))
        elementos.append(tabla_prob)

    # Tabla CPM
    elementos.append(Paragraph("Tabla CPM/PERT", subtitulo))
    datos: List[List[Any]] = [[
        "Cod.", "Actividad", "Tipo", "te", "ES", "EF", "LS", "LF",
        "Holgura", "Critica",
    ]]
    for fila in cpm["filas"]:
        datos.append([
            fila.get("codigo", ""), Paragraph(_texto(fila["nombre"]), celda),
            fila["tipo"], f"{fila['te']:.1f}", f"{fila['es']:.1f}", f"{fila['ef']:.1f}",
            f"{fila['ls']:.1f}", f"{fila['lf']:.1f}", f"{fila['holgura']:.1f}",
            "SI" if fila["critica"] else "NO",
        ])
    tabla = Table(
        datos, repeatRows=1,
        colWidths=[1.1 * cm, 8.2 * cm, 1.5 * cm, 1.1 * cm, 1.1 * cm, 1.1 * cm,
                   1.1 * cm, 1.1 * cm, 1.5 * cm, 1.3 * cm],
    )
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D1D7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F8")]),
        ("TEXTCOLOR", (9, 1), (9, -1), colors.HexColor(ROJO)),
    ]))
    elementos.append(tabla)

    # Ruta critica
    elementos.append(Paragraph("Ruta critica", subtitulo))
    ruta = " -> ".join(
        next((f"{f['codigo']} {f['nombre']}" for f in cpm["filas"] if f["id"] == ida), ida)
        for ida in cpm["ruta_critica"]
    )
    elementos.append(Paragraph(_texto(ruta or "Sin ruta critica definida."), normal))

    # Gantt
    elementos.append(PageBreak())
    elementos.append(Paragraph("Diagrama de Gantt", subtitulo))
    elementos.append(Paragraph(
        "Barra solida: duracion de la actividad. Barra gris: holgura total. "
        "Linea punteada: fin esperado del proyecto.",
        normal,
    ))
    elementos.append(Spacer(1, 6))
    for dibujo in _gantt_dibujos(cpm):
        elementos.append(dibujo)
        elementos.append(Spacer(1, 8))

    # Tarifas cantonales aplicadas
    tarifas = costos.get("tarifas_cantonales") or []
    if tarifas:
        elementos.append(Paragraph("Trazabilidad de tasas cantonales", subtitulo))
        filas_tarifa = [["Actividad", "Canton", "Origen", "USD", "Detalle"]]
        for tarifa in tarifas:
            filas_tarifa.append([
                Paragraph(_texto(tarifa.get("nombre", "")), celda),
                Paragraph(_texto(tarifa.get("canton", "")), celda),
                Paragraph(_texto(tarifa.get("origen", "")), celda),
                f"{float(tarifa.get('costo') or 0):,.2f}",
                Paragraph(_texto(tarifa.get("nota", "")), celda),
            ])
        tabla_tarifas = Table(
            filas_tarifa, repeatRows=1,
            colWidths=[7.0 * cm, 3.0 * cm, 2.4 * cm, 2.6 * cm, 11.0 * cm],
        )
        tabla_tarifas.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D1D7")),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elementos.append(tabla_tarifas)
        elementos.append(Paragraph(
            "Las tarifas municipales son referencias del canton seleccionado y deben "
            "confirmarse en la ordenanza vigente del GAD.",
            pie,
        ))

    # Presupuesto
    elementos.append(Paragraph("Presupuesto por naturaleza del costo", subtitulo))
    costos_datos = [
        ["Concepto", "USD"],
        ["Costos directos privados", f"{costos['directos']:,.2f}"],
        ["Equipos", f"{costos['equipos']:,.2f}"],
        ["Mano de obra cargada", f"{costos['mano_obra_incluida']:,.2f}"],
        [f"Gastos administrativos ({costos['admin_pct']:.1f}%)", f"{costos['administrativos']:,.2f}"],
        ["Subtotal inversion privada", f"{costos['privada']:,.2f}"],
        ["Tramites y tasas publicas", f"{costos['tramites']:,.2f}"],
        ["Base gravada IVA (excluye nomina)", f"{costos.get('base_iva', 0.0):,.2f}"],
        ["IVA", f"{costos['iva']:,.2f}"],
        ["TOTAL", f"{costos['total']:,.2f}"],
    ]
    tabla_costos = Table(costos_datos, colWidths=[8 * cm, 3.5 * cm])
    tabla_costos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D1D7")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E7EEF2")),
    ]))
    elementos.append(tabla_costos)

    # Fuentes normativas
    tramites = [a for a in proyecto.actividades.values() if a.tipo == "tramite"]
    if tramites:
        elementos.append(Paragraph("Fuentes normativas de los tramites", subtitulo))
        catalogo = {t["id"]: t for t in _catalogo().get("tramites", [])}
        fuentes = [["Tramite", "Entidad", "Normativa", "Tipo de valor", "Fuente"]]
        for actividad in tramites:
            registro = catalogo.get(actividad.id, {})
            fuentes.append([
                Paragraph(_texto(actividad.nombre), celda),
                Paragraph(_texto(actividad.entidad), celda),
                Paragraph(_texto(actividad.fuente_normativa), celda),
                Paragraph(_texto(registro.get("valor_tipo", "referencia")), celda),
                Paragraph(_texto(actividad.fuente_url), celda),
            ])
        tabla_fuentes = Table(
            fuentes, repeatRows=1,
            colWidths=[6.8 * cm, 5.0 * cm, 6.6 * cm, 2.6 * cm, 5.5 * cm],
        )
        tabla_fuentes.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D1D7")),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elementos.append(tabla_fuentes)

    # Flujo de caja
    if flujo:
        elementos.append(PageBreak())
        elementos.append(Paragraph("Flujo de caja semanal", subtitulo))
        datos_flujo = [["Semana", "Costo semanal", "Acumulado"]]
        for semana in flujo:
            datos_flujo.append([
                str(semana["semana"]), f"{semana['costo']:,.2f}", f"{semana['acumulado']:,.2f}",
            ])
        tabla_flujo = Table(datos_flujo, repeatRows=1, colWidths=[2.5 * cm, 4 * cm, 4 * cm])
        tabla_flujo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D1D7")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elementos.append(tabla_flujo)

    # Observaciones
    if problemas:
        elementos.append(Paragraph("Observaciones de validacion", subtitulo))
        for problema in problemas[:30]:
            nivel = {"error": "Error", "advertencia": "Advertencia", "info": "Observacion"}.get(
                getattr(problema, "nivel", ""), "Observacion"
            )
            elementos.append(Paragraph(
                f"<b>{nivel}:</b> {_texto(getattr(problema, 'mensaje', problema))}", normal
            ))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
        "Documento generado automaticamente por ECUAPROJECT. Las tasas y plazos provienen "
        "del catalogo normativo y deben confirmarse en la fuente oficial antes de su "
        "presentacion definitiva. La herramienta no sustituye asesoria legal ni la revision "
        "de un profesional responsable.",
        pie,
    ))
    def _pie_pagina(lienzo, documento_actual) -> None:
        lienzo.saveState()
        lienzo.setFont("Helvetica", 7)
        lienzo.setFillColor(colors.HexColor(GRIS))
        lienzo.drawString(1.2 * cm, 0.55 * cm, "ECUAPROJECT · Informe CPM/PERT")
        lienzo.drawRightString(
            landscape(A4)[0] - 1.2 * cm,
            0.55 * cm,
            f"Pagina {documento_actual.page}",
        )
        lienzo.restoreState()

    documento.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    return salida.getvalue()
