"""Validador del proyecto: integridad del grafo, tiempos y reglas normativas.

El validador no calcula el cronograma: solo detecta condiciones que impiden o
desaconsejan programarlo. Devuelve objetos ``Problema`` que la interfaz muestra
agrupados por severidad y que tambien se incluyen en el informe PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from core.calculos_cpm_pert import CicloError, orden_topologico
from core.costos_cantonales import datos_canton, resolver_tarifa
from core.modelo import Proyecto, cargar_parametros

ERROR = "error"
ADVERTENCIA = "advertencia"
INFO = "info"


@dataclass
class Problema:
    nivel: str
    codigo: str
    mensaje: str
    actividad: Optional[str] = None

    @property
    def etiqueta(self) -> str:
        return {
            ERROR: "Error",
            ADVERTENCIA: "Advertencia",
            INFO: "Observacion",
        }.get(self.nivel, "Observacion")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nivel": self.nivel,
            "codigo": self.codigo,
            "mensaje": self.mensaje,
            "actividad": self.actividad,
        }


# Dependencias legales minimas: (actividad, predecesora_requerida, explicacion)
REGLAS_LEGALES = [
    ("registro_patronal", "ruc", "El IESS exige RUC activo para dar de alta al patrono."),
    ("patente_municipal", "ruc", "La patente se declara sobre un RUC vigente."),
    ("patente_municipal", "uso_suelo", "No se puede patentar un giro no autorizado en el predio."),
    ("habilitacion_municipal", "uso_suelo", "El certificado unico consolida el uso de suelo."),
    ("habilitacion_municipal", "patente_municipal", "La habilitacion requiere la patente pagada."),
    ("habilitacion_municipal", "bomberos", "La habilitacion exige la inspeccion de bomberos."),
    ("habilitacion_municipal", "ruc", "La habilitacion requiere RUC."),
    ("permiso_arcsa", "ruc", "ARCSA valida el RUC del establecimiento."),
    ("permiso_arcsa", "patente_municipal", "ARCSA pide la patente municipal vigente."),
    ("notificacion_sanitaria", "permiso_arcsa", "Sin permiso de funcionamiento no se notifica un producto."),
    ("registro_sanitario_medicamentos", "permiso_arcsa", "El registro sanitario exige permiso de funcionamiento."),
    ("aviso_entrada", "registro_patronal", "El aviso de entrada se registra bajo un patrono dado de alta."),
    ("contrato_sut", "registro_patronal", "El contrato se registra con el patrono ya constituido."),
    ("reglamento_higiene", "registro_patronal", "El reglamento se aprueba ante el patrono registrado."),
    ("aprobacion_planos", "uso_suelo", "No se aprueban planos en un predio sin uso de suelo compatible."),
    ("linea_fabrica", "aprobacion_planos", "La linea de fabrica califica planos ya aprobados."),
    ("permiso_construccion", "aprobacion_planos", "Sin planos aprobados no se emite permiso de construccion."),
    ("inspeccion_final_obra", "permiso_construccion", "No se recibe una obra que nunca fue autorizada."),
    ("registro_ambiental", "certificado_ambiental", "El registro ambiental parte del certificado del SUIA."),
    ("licencia_ambiental", "registro_ambiental", "La licencia de alto impacto requiere el registro previo."),
    ("registro_marca", "busqueda_fonetica", "El registro de marca se solicita tras la busqueda fonetica."),
    ("nombramiento_representante", "constitucion_sociedad", "El nombramiento se inscribe tras constituir la compania."),
    ("luaf_turismo", "registro_turismo_mintur", "La LUAF municipal exige el Registro de Turismo previo del MINTUR."),
    ("luaf_turismo", "uso_suelo", "La LUAF exige certificado de uso de suelo compatible."),
    ("luaf_turismo", "patente_municipal", "La LUAF exige patente municipal vigente."),
    ("luaf_turismo", "bomberos", "La LUAF exige permiso del Cuerpo de Bomberos."),
    ("permiso_acess", "ruc", "ACESS valida el RUC del establecimiento de salud."),
    ("permiso_acess", "rues_msp", "El permiso ACESS requiere el Unicodigo RUES del MSP."),
    ("permiso_acess", "patente_municipal", "ACESS exige la patente municipal vigente."),
    ("permiso_acess", "bomberos", "ACESS exige permiso de funcionamiento de bomberos."),
    ("gestion_desechos_sanitarios", "permiso_acess", "El plan de desechos se vincula a la habilitacion sanitaria del establecimiento."),
    ("certificacion_bpa", "registro_operador_agrocalidad", "La certificacion BPA exige estar registrado como operador en el Sistema GUIA."),
]


def _es_alcanzable(proyecto: Proyecto, desde: str, objetivo: str) -> bool:
    """True si ``objetivo`` aparece en la cadena transitiva de predecesoras."""
    if desde not in proyecto.actividades:
        return False
    vistos: Set[str] = set()
    pila = list(proyecto.actividades[desde].predecesoras)
    while pila:
        actual = pila.pop()
        if actual == objetivo:
            return True
        if actual in vistos:
            continue
        vistos.add(actual)
        actividad = proyecto.obtener(actual)
        if actividad:
            pila.extend(actividad.predecesoras)
    return False


def cadenas_legales_faltantes(proyecto: Proyecto) -> List[Problema]:
    problemas: List[Problema] = []
    for actividad_id, requisito, explicacion in REGLAS_LEGALES:
        actividad = proyecto.obtener(actividad_id)
        if actividad is None:
            continue
        if requisito not in proyecto.actividades:
            # La actividad existe pero falta por completo su requisito legal:
            # es un error, no una regla que se pueda omitir.
            problemas.append(
                Problema(
                    ERROR,
                    "regla_legal",
                    f"'{actividad.nombre}' requiere '{requisito}', que no esta en el proyecto. "
                    f"{explicacion}",
                    actividad=actividad_id,
                )
            )
            continue
        if not _es_alcanzable(proyecto, actividad_id, requisito):
            problemas.append(
                Problema(
                    ERROR,
                    "regla_legal",
                    f"'{actividad.nombre}' requiere como predecesora a "
                    f"'{proyecto.actividades[requisito].nombre}'. {explicacion}",
                    actividad=actividad_id,
                )
            )

    conexion = proyecto.obtener("conexion_energia")
    if conexion is not None:
        if "permiso_construccion" in proyecto.actividades:
            if not _es_alcanzable(proyecto, "conexion_energia", "permiso_construccion"):
                problemas.append(
                    Problema(
                        ERROR,
                        "regla_legal",
                        f"'{conexion.nombre}' requiere como predecesora a "
                        f"'{proyecto.actividades['permiso_construccion'].nombre}'. "
                        "En obra nueva, la distribuidora exige permiso de construccion.",
                        actividad="conexion_energia",
                    )
                )
        elif "uso_suelo" in proyecto.actividades:
            if not _es_alcanzable(proyecto, "conexion_energia", "uso_suelo"):
                problemas.append(
                    Problema(
                        ERROR,
                        "regla_legal",
                        f"'{conexion.nombre}' requiere como predecesora a "
                        f"'{proyecto.actividades['uso_suelo'].nombre}' en locales existentes.",
                        actividad="conexion_energia",
                    )
                )
    return problemas


def validar(
    proyecto: Proyecto,
    base_catalogo: Optional[Dict[str, Any]] = None,
    parametros: Optional[Dict[str, Any]] = None,
) -> List[Problema]:
    """Devuelve todos los problemas encontrados, del mas grave al mas leve."""
    problemas: List[Problema] = []

    if not proyecto.actividades:
        problemas.append(Problema(ADVERTENCIA, "vacio", "El proyecto aun no tiene actividades."))
        return problemas

    # 1. Ciclos y orden topologico
    try:
        orden_topologico(proyecto)
    except CicloError as error:
        problemas.append(Problema(ERROR, "ciclo", str(error)))

    # 2. Predecesoras inexistentes, autorreferencias y duplicados
    for actividad in proyecto.actividades.values():
        if actividad.id in actividad.predecesoras:
            problemas.append(
                Problema(
                    ERROR,
                    "autodependencia",
                    f"'{actividad.nombre}' se declara predecesora de si misma.",
                    actividad=actividad.id,
                )
            )
        for pred in actividad.predecesoras:
            if pred not in proyecto.actividades:
                problemas.append(
                    Problema(
                        ERROR,
                        "predecesora_inexistente",
                        f"'{actividad.nombre}' depende de '{pred}', que no existe en el proyecto. "
                        "La dependencia se conserva: corrige el ID o elimina la referencia "
                        "de forma explicita.",
                        actividad=actividad.id,
                    )
                )
        duplicadas = {p for p in actividad.predecesoras if actividad.predecesoras.count(p) > 1}
        if duplicadas:
            problemas.append(
                Problema(
                    ADVERTENCIA,
                    "predecesora_duplicada",
                    f"'{actividad.nombre}' repite predecesoras: {', '.join(sorted(duplicadas))}.",
                    actividad=actividad.id,
                )
            )

    # 3. Tiempos PERT y costos
    parametros = parametros or cargar_parametros()
    sbu = float(parametros.get("salario", {}).get("sbu", 0.0) or 0.0)
    for actividad in proyecto.actividades.values():
        if not actividad.tiempos_validos():
            problemas.append(
                Problema(
                    ERROR,
                    "tiempos_invalidos",
                    f"'{actividad.nombre}' tiene tiempos inconsistentes: debe cumplirse "
                    f"0 <= optimista <= probable <= pesimista.",
                    actividad=actividad.id,
                )
            )
        elif actividad.pesimista - actividad.optimista > 3 * max(actividad.probable, 1):
            problemas.append(
                Problema(
                    ADVERTENCIA,
                    "incertidumbre_alta",
                    f"'{actividad.nombre}' tiene un rango PERT muy amplio; la estimacion "
                    f"aporta poca informacion.",
                    actividad=actividad.id,
                )
            )
        if (
            actividad.costo < 0
            or actividad.costo_equipos < 0
            or actividad.costo_por_m2 < 0
            or (actividad.costo_base or 0) < 0
        ):
            problemas.append(
                Problema(
                    ERROR,
                    "costo_negativo",
                    f"'{actividad.nombre}' tiene un costo negativo.",
                    actividad=actividad.id,
                )
            )
        if actividad.costo_mo_diario > 0 and sbu > 0:
            mensual = actividad.costo_mo_diario * float(
                parametros.get("salario", {}).get("dias_mes", 30) or 30
            )
            if mensual < sbu - 0.01:
                problemas.append(
                    Problema(
                        ADVERTENCIA,
                        "mano_obra_bajo_sbu",
                        f"'{actividad.nombre}' paga USD {mensual:.2f} mensuales por trabajador, "
                        f"por debajo del SBU {parametros.get('salario', {}).get('sbu_vigencia', '')} "
                        f"(USD {sbu:.2f}).",
                        actividad=actividad.id,
                    )
                )

    # 4. Hitos sin predecesoras (posible tramite huerfano)
    for actividad in proyecto.actividades.values():
        if actividad.tipo == "tramite" and not actividad.predecesoras:
            problemas.append(
                Problema(
                    INFO,
                    "tramite_sin_predecesora",
                    f"'{actividad.nombre}' no tiene predecesoras; verifica si legalmente puede iniciarse solo.",
                    actividad=actividad.id,
                )
            )

    # 5. Consistencia con el catalogo normativo y su nivel de verificacion
    if base_catalogo:
        catalogo = {t["id"]: t for t in base_catalogo.get("tramites", [])}
        for actividad in proyecto.actividades.values():
            if actividad.tipo != "tramite":
                continue
            registro = catalogo.get(actividad.id)
            if registro is None:
                problemas.append(
                    Problema(
                        INFO,
                        "tramite_fuera_catalogo",
                        f"'{actividad.nombre}' no figura en el catalogo normativo: verifica su base legal.",
                        actividad=actividad.id,
                    )
                )
                continue
            valor_tipo = registro.get("valor_tipo", "")
            fuente_tipo = registro.get("fuente_tipo", "")
            if registro.get("verificar") or valor_tipo in ("estimacion", "rango", "mercado"):
                etiqueta = {
                    "estimacion": "valor estimado",
                    "rango": "valor en rango",
                    "mercado": "precio de mercado",
                }.get(valor_tipo, "tasa por confirmar")
                problemas.append(
                    Problema(
                        INFO,
                        "tasa_por_confirmar",
                        f"'{actividad.nombre}': {etiqueta}. "
                        f"Confirma el monto en {registro.get('entidad', 'la entidad')} "
                        f"({fuente_tipo or 'fuente institucional'}; revisado "
                        f"{registro.get('verificado_en', 'sin fecha')}).",
                        actividad=actividad.id,
                    )
                )

    # 6. Tarifas cantonales: el canton del escenario debe tener tarifario propio
    canton = str(proyecto.escenario.get("canton") or "").strip()
    hay_tarifario = datos_canton(canton, parametros) is not None if canton else False
    if canton and not hay_tarifario:
        problemas.append(
            Problema(
                ADVERTENCIA,
                "canton_sin_tarifario",
                f"El canton '{canton}' no tiene tarifario cargado. Los tramites "
                "municipales usan el costo de referencia del catalogo y deben "
                "confirmarse en el GAD correspondiente.",
            )
        )
    for actividad in proyecto.actividades.values():
        tarifa = resolver_tarifa(actividad, proyecto.escenario, parametros)
        if tarifa is None or not tarifa.get("advertencia") or not hay_tarifario:
            # Sin tarifario general ya se emitio una advertencia unica; no se
            # repite el mismo aviso por cada tramite municipal.
            continue
        problemas.append(
            Problema(
                INFO,
                "tasa_cantonal_referencia",
                f"{tarifa['advertencia']} (Actividad: '{actividad.nombre}'.)",
                actividad=actividad.id,
            )
        )

    # 7. Reglas normativas y coherencia de personeria / regimen tributario
    problemas.extend(cadenas_legales_faltantes(proyecto))
    personeria = str(proyecto.escenario.get("tipo_personeria") or "persona_natural")
    regimen = str(proyecto.escenario.get("regimen_tributario") or "general")
    if regimen == "rimpe_negocio_popular" and personeria in ("sas", "compania"):
        problemas.append(
            Problema(
                ERROR,
                "regimen_incompatible",
                "El regimen RIMPE Negocio Popular aplica unicamente a personas naturales "
                "(hasta USD 20,000 anuales), no a sociedades ni S.A.S.",
            )
        )
    if regimen in ("rimpe_emprendedor", "rimpe_negocio_popular"):
        if any(
            ida in proyecto.actividades
            for ida in (
                "permiso_construccion",
                "aprobacion_planos",
                "registro_operador_agrocalidad",
                "certificacion_bpa",
            )
        ):
            problemas.append(
                Problema(
                    ADVERTENCIA,
                    "actividad_excluida_rimpe",
                    "Segun la normativa del SRI, las actividades de construccion y "
                    "agropecuarias estan excluidas del regimen RIMPE y tributan en Regimen General.",
                )
            )
        if "ruc" in proyecto.actividades and "regimen_rimpe" not in proyecto.actividades:
            problemas.append(
                Problema(
                    INFO,
                    "rimpe_sin_registro",
                    "El escenario declara regimen RIMPE; considera incorporar el tramite "
                    "de acogimiento RIMPE en el SRI.",
                )
            )
    if personeria in ("sas", "compania") and "constitucion_sociedad" not in proyecto.actividades:
        problemas.append(
            Problema(
                ADVERTENCIA,
                "personeria_sin_constitucion",
                "El escenario declara personeria juridica, pero el cronograma no incluye "
                "el tramite de constitucion societaria.",
            )
        )

    empleados = int(proyecto.escenario.get("empleados") or 0)
    if empleados > 0 and "registro_patronal" not in proyecto.actividades:
        problemas.append(
            Problema(
                ADVERTENCIA,
                "empleados_sin_iess",
                f"El escenario declara {empleados} empleado(s), pero el cronograma no incluye "
                "el registro patronal en el IESS.",
            )
        )
    if empleados > 10 and "reglamento_higiene" not in proyecto.actividades:
        problemas.append(
            Problema(
                ADVERTENCIA,
                "empleados_sin_reglamento_higiene",
                f"Con {empleados} empleados (>10) es obligatorio aprobar el Reglamento de "
                "Higiene y Seguridad ante el Ministerio del Trabajo.",
            )
        )
    if empleados > 0:
        for actividad in proyecto.actividades.values():
            if actividad.trabajadores > empleados:
                problemas.append(
                    Problema(
                        INFO,
                        "trabajadores_sobre_escenario",
                        f"'{actividad.nombre}' asigna {actividad.trabajadores} trabajadores, "
                        f"por encima de los {empleados} empleados declarados en el escenario.",
                        actividad=actividad.id,
                    )
                )

    orden = {ERROR: 0, ADVERTENCIA: 1, INFO: 2}
    return sorted(problemas, key=lambda p: (orden.get(p.nivel, 3), p.actividad or ""))


def hay_errores(problemas: Iterable[Problema]) -> bool:
    return any(problema.nivel == ERROR for problema in problemas)


def tramites_obligatorios_faltantes(
    proyecto: Proyecto,
    etiquetas: Iterable[str],
    base_catalogo: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Compara el proyecto contra el catalogo segun las etiquetas del escenario."""
    etiquetas = set(etiquetas)
    existentes = set(proyecto.actividades)
    faltantes: List[Dict[str, Any]] = []
    for tramite in base_catalogo.get("tramites", []):
        if not tramite.get("obligatorio"):
            continue
        aplica = set(tramite.get("aplica_a", []))
        if not aplica & etiquetas:
            continue
        if tramite["id"] in existentes:
            continue
        faltantes.append(tramite)
    return faltantes
