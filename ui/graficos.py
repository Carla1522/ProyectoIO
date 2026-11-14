"""Graficos del proyecto: red CPM, Gantt, campana de Gauss y flujo de caja.

Todos los graficos consumen los resultados del motor matematico. No estiman
duraciones ni dependencias por su cuenta: la posicion de cada nodo y cada barra
proviene de ES, EF, te y holgura calculados en ``core.calculos_cpm_pert``.

La red admite dos disposiciones:

* ``tiempo`` (por defecto): eje horizontal en dias laborables y carriles
  verticales para que las actividades paralelas no se superpongan.
* ``dependencia``: columnas segun el nivel topologico, ordenadas por el
  promedio de sus predecesoras para reducir cruces.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go

from core.modelo import Proyecto
from ui.estilos import FUENTE, PALETA

TOL = 1e-6
SEPARACION_CARRIL = 0.9  # dias minimos entre nodos del mismo carril


def _layout(figura: go.Figure, alto: int, **extra: Any) -> go.Figure:
    figura.update_layout(
        height=alto,
        margin=dict(l=14, r=22, t=54, b=44),
        paper_bgcolor=PALETA["superficie"],
        plot_bgcolor=PALETA["superficie"],
        font=dict(family=FUENTE, size=11, color=PALETA["texto"]),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            font=dict(size=10), bgcolor="rgba(0,0,0,0)",
            itemsizing="constant",
        ),
        hoverlabel=dict(font=dict(family=FUENTE, size=11)),
        **extra,
    )
    return figura


def _truncar(texto: Any, maximo: int) -> str:
    limpio = " ".join(str(texto or "").split())
    return limpio if len(limpio) <= maximo else limpio[: maximo - 1].rstrip() + "…"


def _niveles(proyecto: Proyecto, cpm: Dict[str, Any]) -> Dict[str, int]:
    niveles: Dict[str, int] = {}
    for ida in cpm["orden"]:
        actividad = proyecto.actividades[ida]
        previos = [niveles[p] for p in actividad.predecesoras if p in niveles]
        niveles[ida] = (max(previos) + 1) if previos else 0
    return niveles


def _posiciones_tiempo(
    proyecto: Proyecto, cpm: Dict[str, Any]
) -> Tuple[Dict[str, Tuple[float, float]], int]:
    """Centro de cada nodo en (dia de inicio temprano, carril).

    Se asigna el primer carril libre; dos actividades que se solapan en el
    tiempo nunca comparten fila. Esto evita el amontonamiento cuando hay muchas
    actividades en paralelo.
    """
    filas = sorted(
        cpm["filas"], key=lambda f: (f["es"], f["ef"], f["codigo"])
    )
    carriles: List[float] = []
    posiciones: Dict[str, Tuple[float, float]] = {}
    for fila in filas:
        inicio = float(fila["es"])
        fin = max(float(fila["ef"]), inicio)
        indice = None
        for numero, ultimo in enumerate(carriles):
            if inicio >= ultimo - TOL:
                indice = numero
                break
        if indice is None:
            carriles.append(fin)
            indice = len(carriles) - 1
        else:
            carriles[indice] = fin
        posiciones[fila["id"]] = (inicio, -float(indice))
    return posiciones, max(len(carriles), 1)


def _posiciones_dependencia(
    proyecto: Proyecto, cpm: Dict[str, Any]
) -> Tuple[Dict[str, Tuple[float, float]], int]:
    """Columnas por nivel topologico, con orden por barycenter de predecesoras."""
    niveles = _niveles(proyecto, cpm)
    por_nivel: Dict[int, List[str]] = {}
    for ida in cpm["orden"]:
        por_nivel.setdefault(niveles[ida], []).append(ida)

    orden: Dict[str, float] = {}
    for nivel in sorted(por_nivel):
        ids = por_nivel[nivel]
        ids.sort(
            key=lambda ida: (
                sum(orden.get(p, 0.0) for p in proyecto.actividades[ida].predecesoras)
                / max(len(proyecto.actividades[ida].predecesoras), 1),
                ida,
            )
        )
        for posicion, ida in enumerate(ids):
            orden[ida] = posicion

    posiciones: Dict[str, Tuple[float, float]] = {}
    for nivel, ids in por_nivel.items():
        total = len(ids)
        for indice, ida in enumerate(ids):
            posiciones[ida] = (float(nivel), float(total - 1 - indice) - (total - 1) / 2)
    return posiciones, max((len(ids) for ids in por_nivel.values()), default=1)


def diagrama_red(
    cpm: Dict[str, Any],
    proyecto: Proyecto,
    alto: Optional[int] = None,
    modo: str = "tiempo",
) -> go.Figure:
    """Red de precedencias con ruta critica resaltada.

    ``modo='tiempo'`` alinea los nodos con los dias laborables y usa carriles
    para las actividades simultaneas. ``modo='dependencia'`` los agrupa por
    nivel topologico. En ambos casos el color rojo y el anillo exterior marcan la
    ruta critica calculada, no solo la holgura cero.
    """
    if modo == "dependencia":
        posiciones, filas_ocupadas = _posiciones_dependencia(proyecto, cpm)
    else:
        posiciones, filas_ocupadas = _posiciones_tiempo(proyecto, cpm)
    alto = alto or max(420, min(920, 150 + 34 * filas_ocupadas))

    figura = go.Figure()
    ruta = cpm["ruta_critica"]
    aristas_criticas = set(zip(ruta, ruta[1:]))
    fila_por_id = {fila["id"]: fila for fila in cpm["filas"]}

    # Aristas. El trazo rojo se reserva a los tramos de la ruta critica.
    for fila in cpm["filas"]:
        destino = posiciones.get(fila["id"])
        if destino is None:
            continue
        for pred in proyecto.actividades[fila["id"]].predecesoras:
            origen = posiciones.get(pred)
            if origen is None:
                continue
            critica = (pred, fila["id"]) in aristas_criticas
            figura.add_trace(
                go.Scatter(
                    x=[origen[0], destino[0]],
                    y=[origen[1], destino[1]],
                    mode="lines",
                    line=dict(
                        color=PALETA["critico"] if critica else "#B4BEC6",
                        width=2.6 if critica else 1.0,
                    ),
                    hovertemplate=(
                        f"{fila_por_id.get(pred, {}).get('codigo', pred)} → "
                        f"{fila['codigo']}<extra></extra>"
                    ),
                    showlegend=False,
                )
            )
            figura.add_annotation(
                x=destino[0], y=destino[1],
                ax=origen[0], ay=origen[1],
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowsize=0.9, arrowwidth=0.9,
                arrowcolor=PALETA["critico"] if critica else "#B4BEC6",
                text="",
            )

    # Nodos: se separan por tipo para una leyenda comprensible.
    for tipo, color, nombre, simbolo in (
        ("privada", PALETA["privada"], "Actividad privada", "circle"),
        ("tramite", PALETA["tramite"], "Tramite publico", "square"),
    ):
        ids = [f for f in cpm["filas"] if f["tipo"] == tipo and f["id"] in posiciones]
        if not ids:
            continue
        figura.add_trace(
            go.Scatter(
                x=[posiciones[f["id"]][0] for f in ids],
                y=[posiciones[f["id"]][1] for f in ids],
                mode="markers+text",
                name=nombre,
                marker=dict(
                    size=30,
                    color=[PALETA["critico"] if f["critica"] else color for f in ids],
                    line=dict(color=PALETA["superficie"], width=1.6),
                    symbol=simbolo,
                ),
                text=[f["codigo"] for f in ids],
                textfont=dict(color="#FFFFFF", size=9, family=FUENTE),
                textposition="middle center",
                customdata=[
                    [f["nombre"], f["es"], f["ef"], f["holgura"], f["te"],
                     "Critica" if f["critica"] else "Con holgura",
                     f["predecesoras"] or "sin predecesoras"]
                    for f in ids
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Inicio %{customdata[1]:.1f} d · Fin %{customdata[2]:.1f} d<br>"
                    "Duracion %{customdata[4]:.1f} d · Holgura %{customdata[3]:.1f} d<br>"
                    "Predecesoras: %{customdata[6]}<br>"
                    "%{customdata[5]}<extra></extra>"
                ),
            )
        )

    criticas = [f for f in cpm["filas"] if f["critica"] and f["id"] in posiciones]
    if criticas:
        figura.add_trace(
            go.Scatter(
                x=[posiciones[f["id"]][0] for f in criticas],
                y=[posiciones[f["id"]][1] for f in criticas],
                mode="markers",
                name="Ruta critica",
                marker=dict(size=40, color="rgba(0,0,0,0)",
                            line=dict(color=PALETA["critico"], width=1.4)),
                hoverinfo="skip",
            )
        )

    if modo == "dependencia":
        xaxis = dict(
            title="Nivel de dependencia",
            showgrid=True, gridcolor=PALETA["grilla"], zeroline=False,
            showticklabels=True, dtick=1,
        )
    else:
        xaxis = dict(
            title="Dias laborables (inicio temprano ES)",
            showgrid=True, gridcolor=PALETA["grilla"], zeroline=False,
            rangemode="tozero",
        )
        figura.add_vline(
            x=float(cpm["duracion"]),
            line_dash="dash",
            line_color=PALETA["critico"],
            line_width=1,
            annotation_text=f"Fin {cpm['duracion']:.1f} d",
            annotation_position="top right",
            annotation_font=dict(size=9, color=PALETA["critico"]),
        )

    _layout(
        figura, alto,
        xaxis=xaxis,
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   title="Carril de actividades simultaneas" if modo == "tiempo" else ""),
        hovermode="closest",
    )
    return figura


def diagrama_gantt(
    cpm: Dict[str, Any], proyecto: Proyecto, alto: Optional[int] = None
) -> go.Figure:
    """Gantt de barras con holgura total, ruta critica y nombres legibles."""
    filas = cpm["filas"]
    figura = go.Figure()
    alto = alto or max(340, 22 * len(filas) + 150)
    # Con muchas filas se muestran solo los codigos para evitar solapamientos;
    # el nombre completo permanece en el tooltip.
    detallado = len(filas) <= 28

    ordenadas = sorted(filas, key=lambda f: (f["es"], f["ef"], f["codigo"]))
    etiquetas = {
        f["id"]: (
            f"{f['codigo']} · {_truncar(f['nombre'], 42)}"
            if detallado else f["codigo"]
        )
        for f in ordenadas
    }
    orden_etiquetas = [etiquetas[f["id"]] for f in ordenadas]

    def barra(subset: List[Dict[str, Any]], color: str, nombre: str) -> None:
        if not subset:
            return
        figura.add_trace(
            go.Bar(
                y=[etiquetas[f["id"]] for f in subset],
                x=[f["te"] for f in subset],
                base=[f["es"] for f in subset],
                orientation="h",
                name=nombre,
                marker=dict(
                    color=color,
                    line=dict(color="rgba(21,32,43,0.20)", width=0.5),
                ),
                customdata=[
                    [f["nombre"], f["es"], f["ef"], f["holgura"], f["te"],
                     f["predecesoras"] or "-", f["ls"], f["lf"]]
                    for f in subset
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "ES %{customdata[1]:.1f} · EF %{customdata[2]:.1f} · "
                    "duracion %{customdata[4]:.1f} d<br>"
                    "LS %{customdata[6]:.1f} · LF %{customdata[7]:.1f} · "
                    "holgura %{customdata[3]:.1f} d<br>"
                    "Predecesoras: %{customdata[5]}<extra></extra>"
                ),
            )
        )

    barra([f for f in ordenadas if f["critica"]], PALETA["critico"], "Ruta critica")
    barra(
        [f for f in ordenadas if not f["critica"] and f["tipo"] == "privada"],
        PALETA["privada"], "Actividad privada",
    )
    barra(
        [f for f in ordenadas if not f["critica"] and f["tipo"] == "tramite"],
        PALETA["tramite"], "Tramite publico",
    )

    figura.add_trace(
        go.Bar(
            y=[etiquetas[f["id"]] for f in ordenadas],
            x=[f["holgura"] for f in ordenadas],
            base=[f["ef"] for f in ordenadas],
            orientation="h",
            name="Holgura total",
            marker=dict(
                color="rgba(138,148,158,0.16)",
                pattern=dict(shape="/", fgcolor="rgba(138,148,158,0.5)"),
            ),
            hoverinfo="skip",
            showlegend=True,
        )
    )

    duracion = cpm["duracion"]
    figura.add_vline(
        x=duracion,
        line_dash="dash",
        line_color=PALETA["critico"],
        line_width=1,
        annotation_text=f"Fin esperado {duracion:.1f} d",
        annotation_position="top",
        annotation_font=dict(size=10, color=PALETA["critico"]),
    )

    _layout(
        figura, alto,
        barmode="overlay",
        xaxis=dict(
            title="Dias laborables", showgrid=True, gridcolor=PALETA["grilla"],
            zeroline=False, dtick=5, rangemode="tozero",
            range=[0, max(duracion, 1) + max(duracion * 0.04, 2)],
        ),
        yaxis=dict(
            title="", autorange="reversed", tickfont=dict(size=9),
            showgrid=False, categoryorder="array", categoryarray=orden_etiquetas,
        ),
        bargap=0.28,
    )
    return figura


def _pdf_normal(x: float, media: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return (1.0 / (sigma * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((x - media) / sigma) ** 2)


def campana_gauss(
    cpm: Dict[str, Any],
    plazo_objetivo: Optional[float] = None,
    probabilidad: Optional[float] = None,
) -> go.Figure:
    media = float(cpm["duracion"])
    sigma = float(cpm["sigma"])
    figura = go.Figure()

    if sigma <= 1e-9:
        figura.add_vline(x=media, line_color=PALETA["primario"], line_width=2,
                         annotation_text=f"Duracion determinista {media:.1f} d",
                         annotation_position="top")
        _layout(figura, 320, xaxis=dict(title="Duracion del proyecto (dias laborables)"),
                yaxis=dict(showticklabels=False))
        return figura

    inicio = max(0.0, media - 4 * sigma)
    fin = media + 4 * sigma
    pasos = 180
    xs = [inicio + (fin - inicio) * i / pasos for i in range(pasos + 1)]
    ys = [_pdf_normal(x, media, sigma) for x in xs]

    figura.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Distribucion del proyecto",
                                line=dict(color=PALETA["primario"], width=2.2)))

    if plazo_objetivo is not None:
        limite = min(max(float(plazo_objetivo), inicio), fin)
        xs_sombra = [x for x in xs if x <= limite]
        ys_sombra = [_pdf_normal(x, media, sigma) for x in xs_sombra]
        figura.add_trace(go.Scatter(
            x=xs_sombra, y=ys_sombra, fill="tozeroy", mode="lines",
            line=dict(color="rgba(156,58,58,0)"), fillcolor="rgba(156,58,58,0.16)",
            name=f"P(cumplir) = {(probabilidad or 0) * 100:.1f}%", hoverinfo="skip",
        ))
        figura.add_vline(x=plazo_objetivo, line_dash="dash", line_color=PALETA["critico"],
                         annotation_text=f"Plazo {plazo_objetivo:.0f} d",
                         annotation_position="top")

    figura.add_vline(x=media, line_color=PALETA["tinta"], line_dash="dot",
                     annotation_text=f"Esperado {media:.1f} d", annotation_position="bottom")

    _layout(
        figura, 340,
        xaxis=dict(title="Duracion del proyecto (dias laborables)", showgrid=True,
                   gridcolor=PALETA["grilla"]),
        yaxis=dict(title="Densidad", showticklabels=False, showgrid=False),
    )
    return figura


def flujo_caja_grafico(flujo: List[Dict[str, Any]]) -> go.Figure:
    figura = go.Figure()
    if not flujo:
        figura.add_annotation(text="Sin costos registrados", showarrow=False,
                              font=dict(color=PALETA["suave"]))
        _layout(figura, 300)
        return figura

    figura.add_trace(go.Bar(
        x=[f"Sem {s['semana']}" for s in flujo],
        y=[s["costo"] for s in flujo],
        name="Costo semanal",
        marker_color=PALETA["tramite"],
        hovertemplate="%{x}<br>USD %{y:,.2f}<extra></extra>",
    ))
    figura.add_trace(go.Scatter(
        x=[f"Sem {s['semana']}" for s in flujo],
        y=[s["acumulado"] for s in flujo],
        name="Acumulado",
        mode="lines+markers",
        line=dict(color=PALETA["primario"], width=2.2),
        marker=dict(size=4),
        yaxis="y2",
        hovertemplate="%{x}<br>Acumulado USD %{y:,.2f}<extra></extra>",
    ))
    _layout(
        figura, 320,
        xaxis=dict(title="Semana", showgrid=False),
        yaxis=dict(title="Costo semanal (USD)", gridcolor=PALETA["grilla"]),
        yaxis2=dict(title="Acumulado (USD)", overlaying="y", side="right", showgrid=False),
    )
    return figura
