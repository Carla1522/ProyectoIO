"""Identidad visual de ECUAPROJECT.

Un unico lugar define la paleta y el CSS. Los graficos importan la misma paleta
para que tablero, tablas y diagramas se vean como una sola aplicacion.

La estetica busca parecer una herramienta de ingenieria: fondo neutro, bordes
finos, jerarquia tipografica clara, un solo color de acento y cero decoracion
innecesaria. Los helpers escapan siempre el texto dinamico antes de inyectarlo
con ``unsafe_allow_html``.
"""

from __future__ import annotations

import streamlit as st

from core.seguridad import escapar

PALETA = {
    "tinta": "#15202B",
    "texto": "#27313B",
    "suave": "#5E6A75",
    "borde": "#D8DEE4",
    "borde_fuerte": "#BFC8D0",
    "fondo": "#F4F6F8",
    "superficie": "#FFFFFF",
    "primario": "#27596E",
    "primario_oscuro": "#1A3F4E",
    "critico": "#9C3A3A",
    "advertencia": "#85641F",
    "exito": "#2C6449",
    "privada": "#3A6B84",
    "tramite": "#9A6D36",
    "neutro": "#8A949E",
    "grilla": "#E5E9ED",
}

FUENTE = '"Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif'
FUENTE_MONO = '"IBM Plex Mono", "Cascadia Mono", "Consolas", monospace'

CSS = f"""
<style>
    html, body, [class*="css"] {{
        font-family: {FUENTE};
        font-feature-settings: "tnum" 1, "cv05" 1;
    }}
    .stApp {{ background: {PALETA['fondo']}; }}
    .main .block-container {{
        max-width: 1220px;
        margin: 0 auto;
        padding-top: 1.5rem;
        padding-bottom: 4rem;
        padding-left: 1.8rem;
        padding-right: 1.8rem;
    }}
    h1, h2, h3, h4 {{
        color: {PALETA['tinta']};
        letter-spacing: -0.012em;
    }}
    h1 {{ font-size: 1.5rem; font-weight: 600; margin-bottom: 0.1rem; }}
    h2 {{ font-size: 1.0rem; font-weight: 600; margin-top: 0.3rem; }}
    h3 {{ font-size: 0.92rem; font-weight: 600; }}
    p, li, label, .stMarkdown {{ color: {PALETA['texto']}; }}
    [data-testid="stCaptionContainer"] p {{
        color: {PALETA['suave']};
        font-size: 0.8rem;
        line-height: 1.45;
    }}
    code {{
        font-family: {FUENTE_MONO};
        font-size: 0.78rem;
        background: #EEF1F4;
        border: 1px solid {PALETA['borde']};
        border-radius: 3px;
        padding: 0.05rem 0.3rem;
    }}

    /* Encabezado */
    .ec-topbar {{
        display: flex; align-items: center; justify-content: space-between;
        gap: 1.5rem; border: 1px solid {PALETA['borde']};
        background: linear-gradient(135deg, {PALETA['superficie']} 0%, #F9FBFC 100%);
        border-left: 4px solid {PALETA['primario']};
        border-radius: 8px;
        padding: 1.05rem 1.4rem; margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }}
    .ec-marca {{
        font-family: {FUENTE_MONO};
        font-size: 0.68rem; letter-spacing: 0.16em; text-transform: uppercase;
        color: {PALETA['primario']}; font-weight: 600;
    }}
    .ec-titulo {{
        font-size: 1.42rem; font-weight: 600; color: {PALETA['tinta']};
        margin: 0.15rem 0 0.12rem 0; line-height: 1.25;
    }}
    .ec-subtitulo {{ font-size: 0.83rem; color: {PALETA['suave']}; margin: 0; }}
    .ec-contexto {{
        font-family: {FUENTE_MONO}; font-size: 0.72rem; color: {PALETA['primario_oscuro']};
        background: #EDF3F5; border: 1px solid #CDDDE3; border-radius: 999px;
        padding: 0.28rem 0.75rem; text-align: right; white-space: nowrap;
    }}
    .ec-card {{
        background: {PALETA['superficie']};
        border: 1px solid {PALETA['borde']};
        border-radius: 8px;
        padding: 1.0rem 1.15rem;
        margin-bottom: 0.85rem;
    }}
    .ec-card-titulo {{
        font-size: 0.88rem; font-weight: 600; color: {PALETA['tinta']};
        margin: 0 0 0.45rem 0;
    }}
    .ec-card p {{
        font-size: 0.82rem; color: {PALETA['suave']};
        margin: 0 0 0.45rem 0; line-height: 1.48;
    }}
    .ec-card p:last-child {{ margin-bottom: 0; }}
    .ec-paso {{
        display: flex; gap: 0.55rem; align-items: flex-start;
        padding: 0.38rem 0; font-size: 0.81rem; color: {PALETA['texto']};
        border-bottom: 1px solid {PALETA['grilla']};
    }}
    .ec-paso:last-child {{ border-bottom: none; padding-bottom: 0; }}
    .ec-paso-num {{
        font-family: {FUENTE_MONO}; font-size: 0.7rem; font-weight: 600;
        color: {PALETA['primario']}; background: #EDF3F5; border: 1px solid #CDDDE3;
        border-radius: 4px; padding: 0.05rem 0.36rem; flex-shrink: 0; margin-top: 0.08rem;
    }}

    /* Secciones */
    .ec-seccion {{ margin: 1.45rem 0 0.55rem 0; }}
    .ec-seccion h2 {{
        margin: 0; font-size: 0.98rem; font-weight: 600;
        display: flex; align-items: center; gap: 0.5rem;
    }}
    .ec-seccion h2::before {{
        content: ""; width: 3px; height: 0.95rem; background: {PALETA['primario']};
        display: inline-block; border-radius: 1px;
    }}
    .ec-seccion p {{
        margin: 0.22rem 0 0 0.65rem; color: {PALETA['suave']}; font-size: 0.8rem;
    }}

    /* Metricas */
    div[data-testid="stMetric"] {{
        background: {PALETA['superficie']};
        border: 1px solid {PALETA['borde']};
        border-radius: 5px;
        padding: 0.7rem 0.85rem;
        min-height: 4.6rem;
    }}
    div[data-testid="stMetricLabel"] p {{
        font-size: 0.7rem; color: {PALETA['suave']};
        text-transform: uppercase; letter-spacing: 0.055em; font-weight: 600;
    }}
    div[data-testid="stMetricValue"] {{
        font-size: 1.28rem; color: {PALETA['tinta']}; font-weight: 600;
        font-variant-numeric: tabular-nums;
    }}

    /* Badges e items */
    .ec-badge {{
        display: inline-block; font-family: {FUENTE_MONO};
        font-size: 0.66rem; font-weight: 600; letter-spacing: 0.03em;
        text-transform: uppercase; padding: 0.1rem 0.4rem; border-radius: 3px;
        margin-right: 0.45rem; border: 1px solid transparent; vertical-align: 1px;
    }}
    .ec-badge-error {{ color: {PALETA['critico']}; background: #FBEEEE; border-color: #E8CECE; }}
    .ec-badge-warn {{ color: {PALETA['advertencia']}; background: #FBF6E8; border-color: #E7DCC2; }}
    .ec-badge-info {{ color: {PALETA['primario']}; background: #EDF3F5; border-color: #CDDDE3; }}
    .ec-badge-ok {{ color: {PALETA['exito']}; background: #EDF4EF; border-color: #CCE0D3; }}
    .ec-item {{
        padding: 0.34rem 0; border-bottom: 1px solid {PALETA['grilla']};
        font-size: 0.83rem; line-height: 1.4;
    }}
    .ec-item:last-child {{ border-bottom: none; }}
    .ec-item a {{ color: {PALETA['primario']}; text-decoration: none; }}
    .ec-item a:hover {{ text-decoration: underline; }}
    .ec-item .ec-tenue {{ color: {PALETA['suave']}; font-size: 0.78rem; }}

    /* Franja de contexto del proyecto */
    .ec-meta {{
        display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
        gap: 0.6rem 1.4rem;
        border: 1px solid {PALETA['borde']}; background: {PALETA['superficie']};
        border-radius: 8px; padding: 0.62rem 1.15rem; margin-top: 0; margin-bottom: 0.9rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }}
    .ec-meta div {{ font-size: 0.78rem; color: {PALETA['texto']}; }}
    .ec-meta span {{
        font-family: {FUENTE_MONO}; font-size: 0.68rem; color: {PALETA['suave']};
        text-transform: uppercase; letter-spacing: 0.05em; margin-right: 0.4rem;
    }}

    /* Pestanas */
    button[data-baseweb="tab"] {{
        font-size: 0.84rem; color: {PALETA['suave']}; padding: 0.5rem 0.1rem;
        font-weight: 500;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {PALETA['primario_oscuro']}; font-weight: 600;
    }}
    div[data-baseweb="tab-highlight"] {{ background: {PALETA['primario']}; }}
    div[data-baseweb="tab-list"] {{
        gap: 1.5rem; border-bottom: 1px solid {PALETA['borde']};
    }}

    /* Controles */
    .stButton > button, .stDownloadButton > button {{
        border-radius: 4px; border: 1px solid {PALETA['borde_fuerte']};
        font-size: 0.83rem; font-weight: 500; color: {PALETA['texto']};
        background: {PALETA['superficie']};
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{
        border-color: {PALETA['primario']}; color: {PALETA['primario']};
    }}
    .stButton > button[kind="primary"] {{
        background: {PALETA['primario']}; border-color: {PALETA['primario']};
        color: #FFFFFF;
    }}
    .stButton > button[kind="primary"]:hover {{ background: {PALETA['primario_oscuro']}; }}
    .stButton > button[kind="primary"]:disabled {{
        background: #7B99A6 !important; border-color: #7B99A6 !important;
        color: rgba(255, 255, 255, 0.9) !important; opacity: 0.78 !important;
    }}
    div[data-baseweb="input"] input, div[data-baseweb="select"] > div,
    textarea {{
        font-size: 0.85rem;
    }}
    div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within {{
        border-color: {PALETA['primario']} !important;
        box-shadow: 0 0 0 1px {PALETA['primario']} !important;
    }}

    /* Navegacion lateral */
    section[data-testid="stSidebar"] {{
        background: {PALETA['superficie']};
        border-right: 1px solid {PALETA['borde']};
    }}
    section[data-testid="stSidebar"] .block-container {{ padding-top: 1.1rem; }}
    section[data-testid="stSidebar"] h4 {{
        font-family: {FUENTE_MONO}; font-size: 0.68rem; letter-spacing: 0.12em;
        text-transform: uppercase; color: {PALETA['suave']}; margin-bottom: 0.4rem;
    }}

    /* Tablas */
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {{
        border: 1px solid {PALETA['borde']}; border-radius: 4px;
        background: {PALETA['superficie']};
    }}
    div[data-testid="stDataFrame"] [role="columnheader"] {{
        font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em;
        color: {PALETA['suave']};
    }}
    hr {{ border-color: {PALETA['borde']}; margin: 1.2rem 0; }}
    div[data-testid="stExpander"] {{
        border: 1px solid {PALETA['borde']}; border-radius: 4px;
        background: {PALETA['superficie']};
    }}
    div[data-testid="stExpander"] summary {{ font-size: 0.84rem; }}

    /* Chat */
    div[data-testid="stChatMessage"] {{
        border: 1px solid {PALETA['borde']}; border-radius: 5px;
        background: {PALETA['superficie']}; padding: 0.55rem 0.7rem;
    }}
    div[data-testid="stChatMessage"] p {{ font-size: 0.85rem; }}

    /* Elementos de servicio */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    div[data-testid="stDecoration"] {{display: none;}}
</style>
"""


def aplicar_estilos() -> None:
    """Inyecta la hoja de estilos una vez por render."""
    st.markdown(CSS, unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str, contexto: str = "") -> None:
    """Encabezado de pagina. Todo el texto se escapa antes de inyectarse."""
    bloque_contexto = (
        f'<div class="ec-contexto">{escapar(contexto)}</div>' if contexto else ""
    )
    st.markdown(
        f"""
        <div class="ec-topbar">
            <div>
                <div class="ec-marca">ECUAPROJECT · Planificacion y presupuesto</div>
                <div class="ec-titulo">{escapar(titulo)}</div>
                <p class="ec-subtitulo">{escapar(subtitulo)}</p>
            </div>
            {bloque_contexto}
        </div>
        """,
        unsafe_allow_html=True,
    )


def seccion(titulo: str, descripcion: str = "") -> None:
    detalle = f"<p>{escapar(descripcion)}</p>" if descripcion else ""
    st.markdown(
        f'<div class="ec-seccion"><h2>{escapar(titulo)}</h2>{detalle}</div>',
        unsafe_allow_html=True,
    )


def badge(nivel: str, texto: str) -> str:
    clase = {
        "error": "ec-badge-error",
        "advertencia": "ec-badge-warn",
        "info": "ec-badge-info",
        "ok": "ec-badge-ok",
    }.get(nivel, "ec-badge-info")
    return f'<span class="ec-badge {clase}">{escapar(texto)}</span>'


def barra_meta(items: list[tuple[str, str]]) -> None:
    """Franja compacta con el contexto del proyecto (canton, plazo, costo)."""
    bloques = "".join(
        f'<div><span>{escapar(etiqueta)}</span>{escapar(valor)}</div>'
        for etiqueta, valor in items
    )
    st.markdown(f'<div class="ec-meta">{bloques}</div>', unsafe_allow_html=True)
