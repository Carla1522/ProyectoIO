"""Copiloto de IA: entrevista al usuario y ensambla el proyecto.

Dos caminos:
1. Con clave de API (Gemini u OpenAI): el modelo recibe el catalogo normativo
   como contexto (RAG) y devuelve un proyecto en JSON estricto.
2. Sin clave: un planificador local basado en reglas y plantillas, para que la
   aplicacion nunca quede inservible ni invente tramites fuera del catalogo.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from core.modelo import Actividad, Proyecto, cargar_base_ecuador, nuevo_id

PROVEEDORES = ("auto", "gemini", "openai", "local")

# --------------------------------------------------------------- Utilidades
def _clave(proveedor: str) -> str:
    if proveedor == "gemini":
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    if proveedor == "openai":
        return os.getenv("OPENAI_API_KEY") or ""
    return ""


def _leer_secretos() -> Dict[str, str]:
    """Lee st.secrets si Streamlit esta disponible, sin acoplar el modulo."""
    try:
        import streamlit as st

        datos = dict(st.secrets)
    except Exception:
        return {}
    return {
        "GEMINI_API_KEY": str(datos.get("GEMINI_API_KEY", "")),
        "OPENAI_API_KEY": str(datos.get("OPENAI_API_KEY", "")),
        "AI_PROVIDER": str(datos.get("AI_PROVIDER", "")),
        "AI_MODEL": str(datos.get("AI_MODEL", "")),
    }


def configuracion() -> Dict[str, Any]:
    """Proveedor activo segun secretos o variables de entorno.

    La clave nunca se devuelve a la interfaz: solo se informa si esta presente.
    """
    secretos = _leer_secretos()
    gemini = secretos.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "") or ""
    openai = secretos.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "") or ""
    proveedor = (secretos.get("AI_PROVIDER") or os.getenv("AI_PROVIDER") or "auto").lower()
    if proveedor not in PROVEEDORES:
        proveedor = "auto"
    if proveedor == "auto":
        proveedor = "gemini" if gemini else ("openai" if openai else "local")
    modelo = secretos.get("AI_MODEL") or os.getenv("AI_MODEL") or ""
    if not modelo:
        modelo = "gemini-flash-latest" if proveedor == "gemini" else "gpt-4o-mini"
    clave = gemini if proveedor == "gemini" else (openai if proveedor == "openai" else "")
    return {
        "proveedor": proveedor,
        "modelo": modelo,
        "gemini": gemini,
        "openai": openai,
        "clave_configurada": bool(clave),
    }


def _clasificar_error(error: Exception) -> str:
    """Mensaje accionable sin exponer la clave ni el cuerpo completo del error."""
    texto = str(error)
    if isinstance(error, ModuleNotFoundError):
        return "Falta la dependencia 'requests'. Instala requirements.txt."
    if isinstance(error, TimeoutError) or "timed out" in texto.lower():
        return "El proveedor de IA no respondio a tiempo. Revisa tu conexion e intenta de nuevo."
    if "401" in texto or "403" in texto or "invalid_api_key" in texto.lower() or "API key" in texto:
        return "La clave de API fue rechazada. Verifica la credencial y sus permisos."
    if "429" in texto:
        return "Se agoto la cuota del proveedor. Espera un momento o revisa tu plan."
    if "404" in texto:
        return "El modelo configurado no existe o no esta disponible para esta clave."
    if "JSON" in texto or "json" in texto:
        return "La respuesta del proveedor no fue un JSON valido; se uso el plan local."
    if "Connection" in texto or "NameResolution" in texto or "proxy" in texto.lower():
        return "No hay conexion con el proveedor de IA; se uso el plan local."
    return f"Error de comunicacion con el proveedor ({type(error).__name__}); se uso el plan local."


def probar_conexion() -> Dict[str, Any]:
    """Comprueba credencial y alcance del proveedor con una llamada minima.

    Devuelve siempre un diccionario y nunca lanza: la interfaz necesita saber si
    el modo IA es real o si la aplicacion esta operando con el planificador local.
    """
    cfg = configuracion()
    if cfg["proveedor"] == "local":
        return {
            "ok": False,
            "proveedor": "local",
            "mensaje": (
                "Modo local activo: no hay clave de IA configurada. La aplicacion "
                "funciona con plantillas y catalogo, sin llamadas externas."
            ),
        }
    if not cfg.get("clave_configurada"):
        return {
            "ok": False,
            "proveedor": cfg["proveedor"],
            "mensaje": "Falta la clave del proveedor seleccionado.",
        }
    try:
        import requests

        if cfg["proveedor"] == "gemini":
            respuesta = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['modelo']}",
                params={"key": cfg["gemini"]},
                timeout=20,
            )
        else:
            respuesta = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {cfg['openai']}"},
                timeout=20,
            )
        if respuesta.status_code == 200:
            return {
                "ok": True,
                "proveedor": cfg["proveedor"],
                "mensaje": f"Conexion verificada con {cfg['proveedor']} ({cfg['modelo']}).",
            }
        return {
            "ok": False,
            "proveedor": cfg["proveedor"],
            "mensaje": _clasificar_error(Exception(str(respuesta.status_code))),
        }
    except Exception as error:  # nunca debe tumbar la pagina
        return {
            "ok": False,
            "proveedor": cfg["proveedor"],
            "mensaje": _clasificar_error(error),
        }


# --------------------------------------------------------------- Prompt / RAG
def catalogo_compacto(base: Dict[str, Any], limite: int = 60) -> str:
    lineas: List[str] = []
    for tramite in base["tramites"][:limite]:
        lineas.append(
            f"- id={tramite['id']} | {tramite['nombre']} | {tramite['entidad']} | "
            f"nivel={tramite.get('nivel', '')} | "
            f"pred={','.join(tramite.get('predecesoras', [])) or 'ninguna'} | "
            f"PERT={tramite['optimista']}/{tramite['probable']}/{tramite['pesimista']}d | "
            f"costo={tramite['costo']} USD ({tramite.get('valor_tipo', 'referencia')}) | "
            f"etiquetas={','.join(tramite.get('aplica_a', []))}"
        )
    return "\n".join(lineas)


SYSTEM_PROMPT = """Eres un consultor senior de planificacion de proyectos en Ecuador.
Entrevistas al usuario para convertir una idea vaga en una tabla de actividades
lista para CPM/PERT. Escribes en espanol claro, profesional y breve.

REGLAS DURAS
1. Solo puedes usar tramites publicos con los ids del CATALOGO. Nunca inventes un
   tramite, una tasa ni una entidad. Si el catalogo no cubre algo, agrega una
   actividad privada y declara el supuesto en "supuestos".
2. Las actividades privadas (tipo "privada") son trabajo del usuario: diseno,
   obra, compras, contratacion, operacion. Las publicas (tipo "tramite") salen
   del catalogo con su id exacto.
3. Toda predecesora debe existir en la lista de actividades que devuelves.
4. Respetas el orden legal: RUC antes de patente, uso de suelo antes de planos,
   bomberos y patente antes de habilitacion, permiso ARCSA antes de notificacion
   sanitaria, busqueda fonetica antes de registro de marca.
5. Estimaciones PERT realistas en dias laborables con a <= m <= b.
6. Maximo 3 preguntas por turno. Si ya tienes ubicacion, tamano, si hay local o
   construccion, empleados y si vende con marca, genera el proyecto.

RESPUESTA: un unico objeto JSON, sin markdown:
{
  "mensaje": "texto para el usuario",
  "listo": true,
  "preguntas": ["..."],
  "supuestos": ["..."],
  "proyecto": {
    "nombre": "...",
    "descripcion": "...",
    "escenario": {"canton": "Ambato", "tamano_empresa": "micro", "area_m2": 0, "aplica_iva": false},
    "actividades": [
      {"id": "snake_case", "nombre": "...", "tipo": "privada|tramite",
       "predecesoras": ["id"], "optimista": 1, "probable": 2, "pesimista": 4,
       "costo": 0, "trabajadores": 0, "costo_mo_diario": 0, "notas": ""}
    ]
  }
}
Si faltan datos, usa "listo": false y "proyecto": null."""


def construir_prompt(escenario: Dict[str, Any], base: Optional[Dict[str, Any]] = None) -> str:
    base = base or cargar_base_ecuador()
    return (
        f"{SYSTEM_PROMPT}\n\nESCENARIO DECLARADO POR EL USUARIO:\n{json.dumps(escenario, ensure_ascii=False)}\n\n"
        f"CATALOGO NORMATIVO ECUADOR (fuente oficial, no modificar):\n{catalogo_compacto(base)}"
    )


# ------------------------------------------------------------------- Llamadas
def _llamar_openai(mensajes: List[Dict[str, str]], cfg: Dict[str, str]) -> str:
    import requests

    respuesta = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {cfg['openai']}", "Content-Type": "application/json"},
        json={
            "model": cfg["modelo"],
            "messages": mensajes,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        },
        timeout=90,
    )
    respuesta.raise_for_status()
    return respuesta.json()["choices"][0]["message"]["content"]


def _llamar_gemini(mensajes: List[Dict[str, str]], cfg: Dict[str, str]) -> str:
    import requests

    sistema = mensajes[0]["content"]
    historial = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
        for m in mensajes[1:]
    ]
    respuesta = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['modelo']}:generateContent",
        params={"key": cfg["gemini"]},
        json={
            "system_instruction": {"parts": [{"text": sistema}]},
            "contents": historial,
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
        },
        timeout=90,
    )
    respuesta.raise_for_status()
    return respuesta.json()["candidates"][0]["content"]["parts"][0]["text"]


def _extraer_json(texto: str) -> Dict[str, Any]:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?", "", texto).rstrip("`").strip()
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1:
        raise ValueError("La IA no devolvio un objeto JSON reconocible.")
    return json.loads(texto[inicio : fin + 1])


# ------------------------------------------------------------ Plan local
KEYWORDS = {
    "alimentos": ["restaurant", "cafeter", "comida", "alimento", "panader", "pasteler", "cocina", "mercado"],
    "salud": ["farmacia", "clinica", "consultorio", "medic", "salud", "laboratorio"],
    "cosmeticos": ["cosmetic", "perfume", "maquillaje", "cuidado personal"],
    "software": ["software", "aplicacion", "app ", "plataforma", "sistema web", "saas", "desarrollo"],
    "obra_civil": ["construir", "construccion", "galpon", "obra", "nave industrial", "planta", "edificio", "adecuacion", "remodelacion"],
    "industria": ["fabrica", "fabricar", "muebles", "carpinter", "produccion", "manufactura", "taller"],
    "evento": ["evento", "feria", "concierto", "expo", "activacion"],
    "comercio": ["tienda", "local", "negocio", "bazar", "almacen", "distribuidora", "papeleria"],
    "marca": ["marca propia", "marca", "branding", "logo", "patente"],
    "empleador": ["empleado", "trabajador", "personal", "contratar", "obreros"],
}

ARQUETIPOS = ["obra_civil", "alimentos", "software", "comercio", "evento", "industria"]


def detectar_etiquetas(descripcion: str) -> List[str]:
    texto = descripcion.lower()
    etiquetas: List[str] = []
    for etiqueta, palabras in KEYWORDS.items():
        if any(palabra in texto for palabra in palabras):
            etiquetas.append(etiqueta)
    if "obra_civil" in etiquetas:
        etiquetas.extend(["local_comercial", "ambiente_bajo"])
    if "alimentos" in etiquetas:
        etiquetas.extend(["local_comercial", "ambiente_bajo"])
    if "industria" in etiquetas:
        etiquetas.extend(["ambiente_medio"])
    if "comercio" in etiquetas:
        etiquetas.append("local_comercial")
    if "todos" not in etiquetas:
        etiquetas.append("todos")
    return list(dict.fromkeys(etiquetas))


def _tarea(id_: str, nombre: str, a: float, m: float, b: float, costo: float,
           preds: Optional[List[str]] = None, trabajadores: int = 0,
           mo_diario: float = 0.0, notas: str = "") -> Dict[str, Any]:
    return {
        "id": id_,
        "nombre": nombre,
        "tipo": "privada",
        "predecesoras": preds or [],
        "optimista": a,
        "probable": m,
        "pesimista": b,
        "costo": costo,
        "trabajadores": trabajadores,
        "costo_mo_diario": mo_diario,
        "notas": notas,
    }


PLANTILLAS: Dict[str, List[Dict[str, Any]]] = {
    "obra_civil": [
        _tarea("topografia", "Levantamiento topografico del predio", 2, 3, 6, 250, notas="Equipo topografico contratado."),
        _tarea("estudio_suelos", "Estudio de suelos y mecanica de suelos", 4, 7, 12, 700, ["topografia"]),
        _tarea("diseno_arquitectonico", "Diseno arquitectonico y planos", 5, 10, 20, 800, ["topografia"]),
        _tarea("diseno_estructural", "Diseno estructural segun NEC", 5, 10, 18, 900, ["estudio_suelos", "diseno_arquitectonico"]),
        _tarea("limpieza_terreno", "Limpieza y preparacion del terreno", 2, 3, 6, 300, ["topografia"], 2, 20),
        _tarea("cimentacion", "Cimentacion y obra gris", 8, 15, 25, 4200, ["diseno_estructural", "limpieza_terreno"], 3, 20),
        _tarea("estructura", "Estructura metalica y cubierta", 10, 18, 30, 7500, ["cimentacion"], 3, 20),
        _tarea("instalaciones", "Instalaciones electricas e hidrosanitarias", 5, 10, 18, 2600, ["cimentacion"], 2, 20),
        _tarea("acabados", "Acabados, pisos y pintura", 6, 12, 20, 3200, ["estructura", "instalaciones"], 2, 20),
        _tarea("compra_maquinaria", "Compra y transporte de maquinaria", 10, 20, 35, 9000, notas="Cotizaciones y anticipo a proveedor."),
        _tarea("instalacion_maquinaria", "Montaje y calibracion de maquinaria", 3, 6, 10, 600, ["acabados", "compra_maquinaria"], 2, 20),
        _tarea("mobiliario", "Mobiliario y equipamiento de oficina", 3, 7, 12, 1800, ["acabados"]),
        _tarea("contratacion_personal", "Reclutamiento y contratacion de personal", 5, 10, 18, 1500, ["acabados"]),
        _tarea("capacitacion", "Capacitacion en seguridad y proceso productivo", 2, 3, 5, 300, ["contratacion_personal", "instalacion_maquinaria"]),
        _tarea("pruebas", "Pruebas piloto de produccion", 3, 5, 10, 500, ["capacitacion", "mobiliario"]),
        _tarea("inauguracion", "Inauguracion y apertura comercial", 1, 1, 2, 500, ["pruebas"]),
    ],
    "alimentos": [
        _tarea("diseno_concepto", "Definicion de concepto, menu y proveedores", 4, 8, 15, 400),
        _tarea("adecuacion_local", "Adecuacion del local segun BPM", 8, 15, 25, 5000, ["diseno_concepto"], 3, 20),
        _tarea("equipamiento", "Compra e instalacion de equipos de cocina", 5, 10, 18, 6500, ["adecuacion_local"]),
        _tarea("formulacion_producto", "Formulacion y fichas tecnicas de producto", 3, 7, 12, 500, ["diseno_concepto"]),
        _tarea("diseno_etiqueta", "Diseno de etiqueta conforme INEN", 2, 4, 8, 250, ["formulacion_producto"]),
        _tarea("analisis_laboratorio", "Analisis fisico-quimico y microbiologico", 5, 10, 18, 450, ["formulacion_producto"]),
        _tarea("contratacion_personal", "Contratacion de cocina y atencion", 4, 8, 15, 800, ["adecuacion_local"]),
        _tarea("capacitacion", "Capacitacion en manipulacion de alimentos", 2, 3, 5, 250, ["contratacion_personal"]),
        _tarea("pruebas", "Marcha blanca con clientes piloto", 3, 5, 8, 300, ["equipamiento", "capacitacion"]),
        _tarea("inauguracion", "Inauguracion del establecimiento", 1, 1, 2, 500, ["pruebas"]),
    ],
    "software": [
        _tarea("relevamiento", "Relevamiento de requerimientos", 3, 6, 10, 600),
        _tarea("arquitectura", "Diseno de arquitectura y modelo de datos", 3, 6, 12, 800, ["relevamiento"]),
        _tarea("desarrollo_backend", "Desarrollo del backend e integraciones", 15, 30, 50, 4000, ["arquitectura"], 2, 45),
        _tarea("desarrollo_frontend", "Desarrollo de la interfaz de usuario", 12, 25, 40, 3200, ["arquitectura"], 2, 45),
        _tarea("qa", "Pruebas funcionales y de seguridad", 5, 10, 18, 1200, ["desarrollo_backend", "desarrollo_frontend"]),
        _tarea("despliegue", "Despliegue en produccion y monitoreo", 2, 3, 6, 400, ["qa"]),
        _tarea("capacitacion", "Capacitacion a usuarios y manuales", 3, 5, 8, 500, ["despliegue"]),
        _tarea("lanzamiento", "Lanzamiento comercial", 1, 2, 4, 600, ["capacitacion"]),
    ],
    "comercio": [
        _tarea("estudio_mercado", "Estudio de mercado y ubicacion", 5, 10, 20, 500),
        _tarea("negociacion_local", "Negociacion y firma de arriendo", 3, 7, 15, 1200, ["estudio_mercado"]),
        _tarea("adecuacion_local", "Remodelacion y adecuacion del local", 8, 15, 25, 4500, ["negociacion_local"], 3, 20),
        _tarea("compra_inventario", "Compra de inventario inicial", 5, 10, 18, 7000, ["adecuacion_local"]),
        _tarea("sistemas", "Implementacion de punto de venta y facturacion", 2, 4, 8, 700, ["adecuacion_local"]),
        _tarea("contratacion_personal", "Contratacion de vendedores", 4, 8, 15, 600, ["adecuacion_local"]),
        _tarea("capacitacion", "Capacitacion en atencion y caja", 2, 3, 5, 250, ["contratacion_personal", "sistemas"]),
        _tarea("pruebas", "Apertura de prueba", 2, 4, 8, 300, ["compra_inventario", "capacitacion"]),
        _tarea("inauguracion", "Inauguracion", 1, 1, 2, 400, ["pruebas"]),
    ],
    "evento": [
        _tarea("concepto", "Concepto, aforo y presupuesto del evento", 3, 6, 10, 400),
        _tarea("reserva_espacio", "Reserva del espacio y proveedores", 3, 6, 12, 2500, ["concepto"]),
        _tarea("produccion", "Produccion tecnica: escenario, sonido e iluminacion", 4, 8, 15, 4000, ["reserva_espacio"]),
        _tarea("promocion", "Campana de difusion y venta de entradas", 10, 20, 30, 1500),
        _tarea("montaje", "Montaje y prueba de sonido", 2, 3, 5, 800, ["produccion"]),
        _tarea("ejecucion", "Ejecucion del evento", 1, 1, 2, 600, ["montaje", "promocion"]),
        _tarea("cierre", "Desmontaje y cierre administrativo", 1, 2, 4, 300, ["ejecucion"]),
    ],
}


def _arquetipo(etiquetas: List[str]) -> str:
    for candidato in ARQUETIPOS:
        if candidato in etiquetas:
            return candidato
    return "comercio"


# Enlaces entre tareas privadas y tramites del catalogo
ENLACES: Dict[str, List[str]] = {
    "uso_suelo": ["negociacion_local"],
    "aprobacion_planos": ["diseno_estructural", "diseno_arquitectonico"],
    "linea_fabrica": ["diseno_arquitectonico"],
    "permiso_construccion": ["diseno_estructural"],
    "registro_patronal": ["contratacion_personal"],
    "aviso_entrada": ["contratacion_personal"],
    "contrato_sut": ["contratacion_personal"],
    "permiso_arcsa": ["adecuacion_local", "capacitacion"],
    "notificacion_sanitaria": ["formulacion_producto", "diseno_etiqueta", "analisis_laboratorio"],
    "inspeccion_final_obra": ["acabados"],
    "habilitacion_municipal": ["pruebas"],
    "registro_marca": ["lanzamiento", "inauguracion"],
    "registro_software": ["qa"],
    "factibilidad_agua": ["permiso_construccion"],
}


def _cerrar_dependencias(ids: List[str], catalogo: Dict[str, Dict[str, Any]]) -> List[str]:
    """Agrega los tramites predecesores que falten (cierre transitivo legal)."""
    resultado = list(dict.fromkeys(ids))
    pendientes = list(resultado)
    while pendientes:
        actual = pendientes.pop()
        for pred in catalogo.get(actual, {}).get("predecesoras", []):
            if pred in catalogo and pred not in resultado:
                resultado.append(pred)
                pendientes.append(pred)
    return resultado


def _seleccionar_tramites(
    etiquetas: List[str], catalogo: Dict[str, Dict[str, Any]], incluir_opcionales: bool
) -> List[str]:
    etiquetas_set = set(etiquetas)
    seleccion: List[str] = []
    for tramite_id, tramite in catalogo.items():
        aplica = set(tramite.get("aplica_a", []))
        if not aplica & etiquetas_set:
            continue
        if tramite.get("obligatorio") or incluir_opcionales:
            seleccion.append(tramite_id)
        elif tramite.get("categoria") == "Propiedad intelectual" and "marca" in etiquetas_set:
            seleccion.append(tramite_id)
        elif tramite_id == "registro_software" and "software" in etiquetas_set:
            seleccion.append(tramite_id)
    return _cerrar_dependencias(seleccion, catalogo)


def plan_local(
    descripcion: str,
    escenario: Optional[Dict[str, Any]] = None,
    base: Optional[Dict[str, Any]] = None,
    incluir_opcionales: bool = False,
) -> Dict[str, Any]:
    """Genera un proyecto completo sin IA, usando plantillas + catalogo."""
    base = base or cargar_base_ecuador()
    catalogo = {tramite["id"]: tramite for tramite in base["tramites"]}
    escenario = dict(escenario or {})
    etiquetas = detectar_etiquetas(descripcion)
    arquetipo = _arquetipo(etiquetas)
    if arquetipo in ("comercio", "alimentos", "obra_civil"):
        etiquetas.append("local_comercial")
    if "marca" in etiquetas:
        etiquetas.append("marca")
    if str(escenario.get("tamano_empresa", "micro")) == "micro":
        etiquetas.append("microempresa")
    if any(tarea["id"] == "contratacion_personal" for tarea in PLANTILLAS[arquetipo]):
        etiquetas.append("empleador")
        if int(escenario.get("empleados", 0) or 0) > 10:
            etiquetas.append("empleador_grande")

    privadas = [dict(tarea) for tarea in PLANTILLAS[arquetipo]]
    ids_privadas = {tarea["id"] for tarea in privadas}

    # Las tareas privadas con predecesoras inexistentes se limpian
    for tarea in privadas:
        tarea["predecesoras"] = [p for p in tarea["predecesoras"] if p in ids_privadas]

    ids_tramites = _seleccionar_tramites(etiquetas, catalogo, incluir_opcionales)
    actividades: List[Dict[str, Any]] = privadas

    for tramite_id in ids_tramites:
        tramite = catalogo[tramite_id]
        preds = list(tramite.get("predecesoras", []))
        preds += [p for p in ENLACES.get(tramite_id, []) if p in ids_privadas]
        actividad = Actividad.desde_catalogo(tramite, predecesoras=list(dict.fromkeys(preds))).to_dict()
        actividades.append(actividad)

    # Enlace de la obra con el tramite final
    habilitacion = next((a for a in actividades if a["id"] == "habilitacion_municipal"), None)
    if habilitacion and "inauguracion" in ids_privadas:
        habilitacion["predecesoras"] = list(dict.fromkeys(habilitacion["predecesoras"] + ["inauguracion"]))

    escenario.setdefault("canton", "Ambato")
    escenario.setdefault("tamano_empresa", "micro")
    escenario.setdefault("area_m2", 0)
    escenario.setdefault("aplica_iva", False)

    supuestos = [
        f"Arquetipo detectado: {arquetipo}.",
        "Los tramites provienen del catalogo normativo; las tasas municipales deben confirmarse en la ordenanza vigente.",
        "Las duraciones privadas son estimaciones parametricas editables por el usuario.",
    ]
    if "obra_civil" in etiquetas:
        supuestos.append("Se asume un area de construccion declarada por el usuario para calcular tasas por m2.")

    return {
        "proveedor": "local",
        "mensaje": (
            f"Arme un plan base para un proyecto de tipo {arquetipo.replace('_', ' ')} "
            f"con {len(privadas)} actividades privadas y {len(ids_tramites)} tramites publicos. "
            "Revisa y ajusta duraciones y costos antes de calcular."
        ),
        "listo": True,
        "preguntas": [],
        "supuestos": supuestos,
        "proyecto": {
            "nombre": _titulo(descripcion, arquetipo),
            "descripcion": descripcion.strip(),
            "escenario": escenario,
            "actividades": actividades,
        },
        "etiquetas": etiquetas,
        "error": None,
    }


def _titulo(descripcion: str, arquetipo: str) -> str:
    limpio = " ".join(descripcion.split())
    if len(limpio) > 70:
        limpio = limpio[:67].rstrip() + "..."
    if len(limpio) < 8:
        return f"Proyecto {arquetipo.replace('_', ' ')}"
    return limpio[0].upper() + limpio[1:]


def preguntas_locales(descripcion: str) -> List[str]:
    etiquetas = detectar_etiquetas(descripcion)
    preguntas = [
        "¿El terreno o local ya es tuyo o vas a arrendar?",
        "¿Cuantos metros cuadrados tendra y cuantos empleados piensas contratar?",
    ]
    if "marca" not in etiquetas:
        preguntas.append("¿Vas a vender con marca propia o solo como servicio generico?")
    return preguntas


# ------------------------------------------------------------------ Fachada
def aplicar_plan(datos: Dict[str, Any], proyecto_actual: Optional[Proyecto] = None) -> Proyecto:
    """Convierte el JSON del plan en un Proyecto de dominio, evitando ids repetidos.

    Es la unica puerta de entrada de un plan (local o IA). Normaliza tiempos y
    costos, completa el nivel y el canton de los tramites desde el catalogo y
    degrada a actividad privada cualquier supuesto tramite publico cuyo id no
    exista: una tasa inventada no debe entrar al presupuesto como si fuera legal.
    """
    proyecto_actual = proyecto_actual or Proyecto()
    escenario_plan = datos.get("escenario")
    proyecto = Proyecto(
        nombre=str(datos.get("nombre") or "Proyecto generado"),
        descripcion=str(datos.get("descripcion") or ""),
        escenario={
            **proyecto_actual.escenario,
            **(dict(escenario_plan) if isinstance(escenario_plan, dict) else {}),
        },
    )
    existentes: List[str] = []
    mapa_ids: Dict[str, str] = {}
    catalogo = {t["id"]: t for t in cargar_base_ecuador().get("tramites", [])}
    actividades_brutas = datos.get("actividades")
    if not isinstance(actividades_brutas, list):
        actividades_brutas = []

    for bruto in actividades_brutas:
        if not isinstance(bruto, dict):
            continue
        actividad = Actividad.from_dict(bruto)
        if actividad.tipo not in ("privada", "tramite"):
            actividad.tipo = "privada"
        # La IA puede devolver numeros fuera de orden. El motor exige
        # 0 <= a <= m <= b; se normaliza sin confiar en el texto del modelo.
        a = max(float(actividad.optimista or 0), 0.0)
        m = max(float(actividad.probable or 0), 0.0)
        b = max(float(actividad.pesimista or 0), 0.0)
        a, m, b = sorted((a, m, b))
        actividad.optimista, actividad.probable, actividad.pesimista = a, m, b
        actividad.costo = max(float(actividad.costo or 0), 0.0)
        actividad.costo_equipos = max(float(actividad.costo_equipos or 0), 0.0)
        actividad.trabajadores = max(int(actividad.trabajadores or 0), 0)
        base_id = actividad.id
        if actividad.tipo == "tramite":
            registro = catalogo.get(base_id)
            if registro is None:
                actividad.tipo = "privada"
                actividad.nivel = ""
                actividad.notas = (
                    (actividad.notas + " ").strip()
                    + "Supuesto tramite fuera del catalogo: se trata como actividad privada."
                ).strip()
            else:
                actividad.nivel = registro.get("nivel", "")
                actividad.canton = registro.get("canton") or ""
                actividad.entidad = registro.get("entidad", actividad.entidad)
        if base_id in existentes:
            actividad.id = nuevo_id(actividad.nombre, existentes)
        mapa_ids[base_id] = actividad.id
        existentes.append(actividad.id)
        actividad.predecesoras = []
        proyecto.agregar(actividad)

    for bruto in actividades_brutas:
        if not isinstance(bruto, dict):
            continue
        id_original = bruto.get("id")
        actividad = proyecto.obtener(mapa_ids.get(id_original, id_original))
        if actividad is None:
            continue
        preds = bruto.get("predecesoras")
        if not isinstance(preds, list):
            preds = []
        # Se conservan las referencias tal como llegaron. Si el modelo invento un
        # ID, el validador lo mostrara como error en lugar de borrarlo en silencio.
        actividad.predecesoras = [
            str(mapa_ids.get(pred, pred)).strip()
            for pred in preds
            if str(mapa_ids.get(pred, pred)).strip()
        ]
    return proyecto


def _lista_textos(valor: Any, maximo: int = 8) -> List[str]:
    if not isinstance(valor, list):
        return []
    return [str(elemento).strip()[:400] for elemento in valor[:maximo] if str(elemento).strip()]


def _normalizar_respuesta_ia(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Valida la forma de la respuesta del modelo antes de usarla.

    La IA no es una fuente de datos confiable: solo se aceptan campos conocidos
    con los tipos esperados. El proyecto se valida despues con ``aplicar_plan``.
    """
    if not isinstance(datos, dict):
        raise ValueError("La IA no devolvio un objeto JSON.")
    proyecto = datos.get("proyecto")
    if proyecto is not None and not isinstance(proyecto, dict):
        proyecto = None
    if proyecto is not None:
        actividades = proyecto.get("actividades")
        if not isinstance(actividades, list):
            proyecto = None
        else:
            proyecto = {
                "nombre": str(proyecto.get("nombre") or "Proyecto generado")[:200],
                "descripcion": str(proyecto.get("descripcion") or "")[:4000],
                "escenario": proyecto.get("escenario")
                if isinstance(proyecto.get("escenario"), dict)
                else {},
                "actividades": [a for a in actividades if isinstance(a, dict)][:500],
            }
    return {
        "mensaje": str(datos.get("mensaje") or "")[:4000],
        "listo": bool(datos.get("listo")) and proyecto is not None,
        "preguntas": _lista_textos(datos.get("preguntas")),
        "supuestos": _lista_textos(datos.get("supuestos")),
        "proyecto": proyecto,
    }


def conversar(
    historial: List[Dict[str, str]],
    mensaje: str,
    escenario: Optional[Dict[str, Any]] = None,
    incluir_opcionales: bool = False,
) -> Dict[str, Any]:
    """Turno de conversacion con el copiloto. Devuelve mensaje, preguntas y plan.

    ``modo`` distingue una respuesta real de la API (``api``) del planificador
    local (``local``) y del respaldo usado cuando la API falla
    (``respaldo_local``). La interfaz muestra ese valor: nunca se presenta un
    plan simulado como si fuera una respuesta del modelo.
    """
    escenario = escenario or {}
    base = cargar_base_ecuador()
    cfg = configuracion()

    if cfg["proveedor"] == "local" or not _clave(cfg["proveedor"]):
        texto_total = " ".join([m["content"] for m in historial if m["role"] == "user"] + [mensaje])
        etiquetas = detectar_etiquetas(texto_total)
        suficientemente_claro = len(texto_total.split()) >= 12 and any(
            e in etiquetas for e in ARQUETIPOS
        )
        if not suficientemente_claro:
            return {
                "proveedor": "local",
                "modo": "local",
                "mensaje": (
                    "Para armarte el cronograma necesito ubicar el proyecto. "
                    "Responde estas preguntas y lo genero de inmediato."
                ),
                "listo": False,
                "preguntas": preguntas_locales(texto_total),
                "supuestos": [],
                "proyecto": None,
                "etiquetas": etiquetas,
                "error": None,
            }
        plan = plan_local(mensaje or texto_total, escenario, base, incluir_opcionales)
        plan["modo"] = "local"
        plan["mensaje"] = (
            "Modo local (sin clave de IA): use plantillas verificadas y el catalogo normativo. "
            + plan["mensaje"]
        )
        plan["proyecto"]["descripcion"] = texto_total.strip()
        return plan

    # La interfaz agrega el mensaje actual al historial antes de llamar aqui.
    # Se elimina ese ultimo turno para no enviarlo dos veces al proveedor.
    turnos = list(historial)
    if turnos and turnos[-1].get("role") == "user" and turnos[-1].get("content", "").strip() == mensaje.strip():
        turnos = turnos[:-1]

    mensajes = [{"role": "system", "content": construir_prompt(escenario, base)}]
    for turno in turnos[-8:]:
        if turno["role"] in ("user", "assistant"):
            mensajes.append({"role": turno["role"], "content": turno["content"]})
    mensajes.append({"role": "user", "content": mensaje})

    try:
        crudo = _llamar_gemini(mensajes, cfg) if cfg["proveedor"] == "gemini" else _llamar_openai(mensajes, cfg)
        datos = _normalizar_respuesta_ia(_extraer_json(crudo))
    except Exception as error:  # la app cae al modo local, nunca se rompe
        respaldo = plan_local(mensaje, escenario, base, incluir_opcionales)
        respaldo["modo"] = "respaldo_local"
        respaldo["mensaje"] = (
            f"{_clasificar_error(error)} Se uso el planificador local, no una respuesta "
            "de la IA. " + respaldo["mensaje"]
        )
        respaldo["error"] = f"{type(error).__name__}: {str(error)[:200]}"
        return respaldo

    return {
        "proveedor": cfg["proveedor"],
        "modo": "api",
        "mensaje": datos["mensaje"],
        "listo": datos["listo"],
        "preguntas": datos["preguntas"],
        "supuestos": datos["supuestos"],
        "proyecto": datos["proyecto"],
        "etiquetas": detectar_etiquetas(mensaje),
        "error": None,
    }
