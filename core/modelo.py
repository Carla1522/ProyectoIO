"""Modelo de dominio: Actividad y Proyecto.

El modelo es independiente de Streamlit y de la interfaz. Toda la logica de
costos de ley vive aqui para que el motor matematico solo se preocupe del
grafo y los tiempos.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.costos_cantonales import resolver_tarifa

RAIZ = Path(__file__).resolve().parent.parent
RUTA_BASE_ECUADOR = RAIZ / "data" / "base_ecuador.json"
RUTA_PARAMETROS = RAIZ / "data" / "parametros_ley.json"


def _slug(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    normalizado = re.sub(r"[^a-zA-Z0-9]+", "_", normalizado).strip("_").lower()
    return normalizado or "actividad"


def cargar_json(ruta: Path) -> Dict[str, Any]:
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def cargar_base_ecuador() -> Dict[str, Any]:
    return cargar_json(RUTA_BASE_ECUADOR)


def cargar_parametros() -> Dict[str, Any]:
    return cargar_json(RUTA_PARAMETROS)


def catalogo_por_id(base: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    base = base or cargar_base_ecuador()
    return {tramite["id"]: tramite for tramite in base["tramites"]}


@dataclass
class Actividad:
    """Una tarea privada o un tramite publico del cronograma."""

    id: str
    nombre: str
    tipo: str = "privada"
    descripcion: str = ""
    predecesoras: List[str] = field(default_factory=list)
    optimista: float = 1.0
    probable: float = 1.0
    pesimista: float = 1.0
    costo: float = 0.0          # costos directos: materiales, compras y servicios
    costo_equipos: float = 0.0  # maquinaria, herramientas y equipos alquilados
    costo_nota: str = ""
    entidad: str = ""
    categoria: str = ""
    nivel: str = ""       # nacional | cantonal (segun el catalogo)
    canton: str = ""      # solo cuando la tarifa depende de un GAD
    fuente_normativa: str = ""
    fuente_url: str = ""
    requisitos: List[str] = field(default_factory=list)
    # Costos parametricos
    costo_base: Optional[float] = None
    costo_por_m2: float = 0.0
    costos_por_tamano: Dict[str, float] = field(default_factory=dict)
    costo_descuento_pyme: Optional[float] = None
    # Mano de obra
    trabajadores: int = 0
    costo_mo_diario: float = 0.0
    # Impuestos
    grava_iva: bool = True
    # Origen
    origen: str = "manual"  # manual | copiloto | catalogo
    costo_manual: bool = False
    notas: str = ""

    # ------------------------------------------------------------------ PERT
    @property
    def te(self) -> float:
        """Tiempo esperado PERT: (a + 4m + b) / 6."""
        return (self.optimista + 4 * self.probable + self.pesimista) / 6

    @property
    def varianza(self) -> float:
        return ((self.pesimista - self.optimista) / 6.0) ** 2

    @property
    def sigma(self) -> float:
        return self.varianza ** 0.5

    @property
    def duracion(self) -> float:
        """Duracion usada en la programacion (tiempo esperado, redondeado a 2 decimales)."""
        return round(self.te, 2)

    def tiempos_validos(self) -> bool:
        return 0 <= self.optimista <= self.probable <= self.pesimista

    # ----------------------------------------------------------------- Costos
    def costo_mano_obra(
        self, factor_cargas: float = 1.0, decimo_cuarto_diario: float = 0.0
    ) -> float:
        if self.trabajadores <= 0 or self.costo_mo_diario <= 0:
            return 0.0
        costo_diario = self.costo_mo_diario * factor_cargas + max(float(decimo_cuarto_diario or 0.0), 0.0)
        return self.trabajadores * costo_diario * self.duracion

    def costo_efectivo(
        self,
        escenario: Optional[Dict[str, Any]] = None,
        factor_cargas: float = 1.0,
        precios_por_clase: bool = True,
        tarifa_cantonal: Optional[Dict[str, Any]] = None,
        decimo_cuarto_diario: float = 0.0,
    ) -> Dict[str, float]:
        """Desglose del costo de la actividad segun el escenario del proyecto.

        Separa los costos directos (materiales, compras y tasas), los equipos y
        la mano de obra cargada. El subtotal es la suma de las tres partidas y
        se calcula una sola vez para evitar duplicaciones.

        ``tarifa_cantonal`` lo resuelve :mod:`core.costos_cantonales`. Cuando el
        canton tiene tarifa propia, reemplaza el costo del catalogo y evita
        sumar de nuevo componentes por metro cuadrado o por tamano de empresa.
        """
        escenario = escenario or {}
        tamano = escenario.get("tamano_empresa", "micro")
        area = float(escenario.get("area_m2") or 0)
        es_pyme = tamano in ("micro", "pequena")

        if self.costo_manual or self.origen == "manual":
            base = self.costo
        else:
            base = self.costo_base if self.costo_base is not None else self.costo
        base = float(base or 0.0)

        usa_tarifa = bool(tarifa_cantonal and tarifa_cantonal.get("aplica"))
        if usa_tarifa:
            base = float(tarifa_cantonal.get("costo") or 0.0)
        else:
            if precios_por_clase and self.costos_por_tamano:
                base = float(self.costos_por_tamano.get(tamano, base))
            if self.costo_descuento_pyme is not None and es_pyme:
                base = float(self.costo_descuento_pyme)
            if self.costo_por_m2 and area:
                base += self.costo_por_m2 * area

        directo = max(base, 0.0)
        equipos = max(float(self.costo_equipos or 0.0), 0.0)
        mano_obra = self.costo_mano_obra(factor_cargas, decimo_cuarto_diario)
        return {
            "directo": round(directo, 2),
            "equipos": round(equipos, 2),
            "mano_obra": round(mano_obra, 2),
            "subtotal": round(directo + equipos + mano_obra, 2),
        }

    # -------------------------------------------------------------- Serializacion
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "descripcion": self.descripcion,
            "predecesoras": list(self.predecesoras),
            "optimista": self.optimista,
            "probable": self.probable,
            "pesimista": self.pesimista,
            "costo": self.costo,
            "costo_equipos": self.costo_equipos,
            "costo_nota": self.costo_nota,
            "entidad": self.entidad,
            "categoria": self.categoria,
            "nivel": self.nivel,
            "canton": self.canton,
            "fuente_normativa": self.fuente_normativa,
            "fuente_url": self.fuente_url,
            "requisitos": list(self.requisitos),
            "costo_base": self.costo_base,
            "costo_por_m2": self.costo_por_m2,
            "costos_por_tamano": dict(self.costos_por_tamano),
            "costo_descuento_pyme": self.costo_descuento_pyme,
            "trabajadores": self.trabajadores,
            "costo_mo_diario": self.costo_mo_diario,
            "grava_iva": self.grava_iva,
            "origen": self.origen,
            "notas": self.notas,
        }

    @classmethod
    def from_dict(cls, datos: Dict[str, Any]) -> "Actividad":
        if not isinstance(datos, dict):
            raise ValueError("Cada actividad debe ser un objeto JSON.")
        campos = {campo for campo in cls.__dataclass_fields__}
        limpio = {clave: valor for clave, valor in datos.items() if clave in campos}
        limpio.setdefault("id", _slug(str(limpio.get("nombre", "actividad"))))
        limpio["id"] = str(limpio["id"] or _slug(str(limpio.get("nombre", "actividad"))))
        limpio["nombre"] = str(limpio.get("nombre") or limpio["id"])
        # Las predecesoras se conservan tal como llegaron: si alguna no existe,
        # el validador lo reporta en lugar de borrarla silenciosamente.
        preds = limpio.get("predecesoras")
        limpio["predecesoras"] = (
            [str(p).strip() for p in preds if str(p).strip()]
            if isinstance(preds, (list, tuple))
            else []
        )
        if limpio.get("tipo") not in ("privada", "tramite"):
            limpio["tipo"] = "privada"
        if "grava_iva" not in limpio or limpio["grava_iva"] is None:
            limpio["grava_iva"] = limpio["tipo"] == "privada"
        else:
            limpio["grava_iva"] = bool(limpio["grava_iva"])
        return cls(**limpio)

    @classmethod
    def desde_catalogo(cls, tramite: Dict[str, Any], predecesoras: Optional[List[str]] = None) -> "Actividad":
        return cls(
            id=tramite["id"],
            nombre=tramite["nombre"],
            tipo="tramite",
            descripcion=tramite.get("descripcion", ""),
            predecesoras=list(predecesoras if predecesoras is not None else tramite.get("predecesoras", [])),
            optimista=float(tramite.get("optimista", 1)),
            probable=float(tramite.get("probable", 1)),
            pesimista=float(tramite.get("pesimista", 1)),
            costo=float(tramite.get("costo", 0.0)),
            costo_nota=tramite.get("costo_nota", ""),
            entidad=tramite.get("entidad", ""),
            categoria=tramite.get("categoria", ""),
            nivel=tramite.get("nivel", ""),
            canton=tramite.get("canton") or "",
            fuente_normativa=tramite.get("fuente_normativa", ""),
            fuente_url=tramite.get("fuente_url", ""),
            requisitos=list(tramite.get("requisitos", [])),
            costo_base=tramite.get("costo_base"),
            costo_por_m2=float(tramite.get("costo_por_m2", 0.0) or 0.0),
            costos_por_tamano=dict(tramite.get("costos_por_tamano", {}) or {}),
            costo_descuento_pyme=tramite.get("costo_descuento_pyme"),
            grava_iva=False,
            origen="catalogo",
        )


@dataclass
class Proyecto:
    nombre: str = "Proyecto sin titulo"
    descripcion: str = ""
    actividades: Dict[str, Actividad] = field(default_factory=dict)
    escenario: Dict[str, Any] = field(
        default_factory=lambda: {
            "canton": "Ambato",
            "tamano_empresa": "micro",
            "tipo_personeria": "persona_natural",
            "regimen_tributario": "general",
            "area_m2": 0.0,
            "aplica_iva": False,
        }
    )

    # ------------------------------------------------------------- Gestion
    def agregar(self, actividad: Actividad) -> Actividad:
        self.actividades[actividad.id] = actividad
        return actividad

    def obtener(self, actividad_id: str) -> Optional[Actividad]:
        return self.actividades.get(actividad_id)

    def __len__(self) -> int:
        return len(self.actividades)

    def ids(self) -> List[str]:
        return list(self.actividades.keys())

    def dependencias_huerfanas(self) -> Dict[str, List[str]]:
        """Predecesoras declaradas que no existen en el proyecto.

        No se eliminan automaticamente: borrar una dependencia sin avisar puede
        cambiar la ruta critica y ocultar un error de digitacion. Se informan y
        el usuario decide si corrige el ID o elimina la referencia.
        """
        existentes = set(self.actividades)
        huerfanas: Dict[str, List[str]] = {}
        for actividad in self.actividades.values():
            faltantes = [p for p in actividad.predecesoras if p not in existentes]
            if faltantes:
                huerfanas[actividad.id] = faltantes
        return huerfanas

    def limpiar_predecesoras_huerfanas(self) -> Dict[str, List[str]]:
        """Elimina referencias inexistentes solo cuando el usuario lo pide.

        Devuelve el mapa de lo que se elimino para poder informarlo.
        """
        eliminadas = self.dependencias_huerfanas()
        existentes = set(self.actividades)
        for actividad in self.actividades.values():
            actividad.predecesoras = [p for p in actividad.predecesoras if p in existentes]
        return eliminadas

    def huella(self) -> str:
        """Hash estable del contenido, util para detectar cambios y aislar widgets."""
        contenido = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------- Costos
    def factor_cargas(self, parametros: Optional[Dict[str, Any]] = None) -> float:
        """Factor de costo empleador calculado desde sus componentes de ley.

        Si el archivo de parametros declara ``costo_empleador.componentes`` se
        suman esos porcentajes; en caso contrario se usa el factor explicito.
        Calcularlo (y no fijarlo a mano) evita que el presupuesto quede
        desactualizado cuando cambia un aporte o un beneficio social.
        """
        parametros = parametros or cargar_parametros()
        datos = parametros.get("costo_empleador", {}) or {}
        componentes = datos.get("componentes") or {}
        if componentes:
            return 1.0 + sum(float(valor) for valor in componentes.values()) / 100.0
        return float(parametros.get("factor_costo_mano_obra", {}).get("valor", 1.0))

    def decimo_cuarto_diario(self, parametros: Optional[Dict[str, Any]] = None) -> float:
        """Provision diaria del decimo cuarto sueldo (1 SBU anual por trabajador).

        En Ecuador el decimo cuarto es un monto fijo independiente del sueldo.
        Si ``costo_empleador.componentes`` aun incluye ``decimo_cuarto`` como
        porcentaje, retorna 0.0 para no duplicarlo.
        """
        parametros = parametros or cargar_parametros()
        datos = parametros.get("costo_empleador", {}) or {}
        componentes = datos.get("componentes") or {}
        if "decimo_cuarto" in componentes:
            return 0.0
        sbu_anual = float(datos.get("decimo_cuarto_fijo_sbu", 1.0) or 0.0)
        salario = parametros.get("salario", {}) or {}
        sbu = float(salario.get("sbu", 0.0) or 0.0)
        dias_mes = float(salario.get("dias_mes", 30.0) or 30.0)
        if sbu <= 0 or sbu_anual <= 0 or dias_mes <= 0:
            return 0.0
        return (sbu * sbu_anual) / (12.0 * dias_mes)

    def resumen_costos(
        self,
        parametros: Optional[Dict[str, Any]] = None,
        escenario: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        parametros = parametros or cargar_parametros()
        escenario = escenario or self.escenario
        factor = self.factor_cargas(parametros)
        decimo_cuarto = self.decimo_cuarto_diario(parametros)
        iva = float(parametros["impuestos"]["iva_pct"]) / 100.0
        admin_pct = float(escenario.get("admin_pct", parametros.get("gastos_administrativos", {}).get("pct", 0.0)) or 0.0)

        directos = 0.0
        equipos = 0.0
        mano_obra = 0.0
        tramites = 0.0
        directos_gravados = 0.0
        equipos_gravados = 0.0
        detalle: List[Dict[str, Any]] = []
        advertencias_cantonales: List[Dict[str, str]] = []
        tarifas_cantonales: List[Dict[str, Any]] = []

        for actividad in self.actividades.values():
            tarifa = resolver_tarifa(actividad, escenario, parametros)
            desglose = actividad.costo_efectivo(
                escenario, factor, tarifa_cantonal=tarifa, decimo_cuarto_diario=decimo_cuarto
            )
            # Cada actividad se clasifica una sola vez: o es tramite publico o
            # es inversion privada. Su subtotal nunca se vuelve a sumar aparte.
            grava_iva = actividad.tipo != "tramite" and bool(actividad.grava_iva)
            if actividad.tipo == "tramite":
                tramites += desglose["subtotal"]
            else:
                directos += desglose["directo"]
                equipos += desglose["equipos"]
                mano_obra += desglose["mano_obra"]
                if grava_iva:
                    directos_gravados += desglose["directo"]
                    equipos_gravados += desglose["equipos"]
            if tarifa is not None:
                if tarifa.get("advertencia"):
                    advertencias_cantonales.append(
                        {"actividad": actividad.nombre, "mensaje": str(tarifa["advertencia"])}
                    )
                tarifas_cantonales.append(
                    {
                        "id": actividad.id,
                        "nombre": actividad.nombre,
                        "canton": tarifa.get("canton", ""),
                        "origen": tarifa.get("origen", "catalogo"),
                        "costo": desglose["directo"],
                        "unidad": tarifa.get("unidad", "tramite"),
                        "nota": tarifa.get("nota", ""),
                        "fuente_url": tarifa.get("fuente_url", ""),
                        "verificado": bool(tarifa.get("verificado")),
                    }
                )
            detalle.append(
                {
                    "id": actividad.id,
                    "nombre": actividad.nombre,
                    "nivel": actividad.nivel,
                    "grava_iva": grava_iva,
                    **desglose,
                    "tarifa_origen": (tarifa or {}).get("origen", ""),
                    "tarifa_nota": (tarifa or {}).get("nota", ""),
                }
            )

        # Gastos administrativos: porcentaje unico sobre los costos directos de
        # la inversion privada (materiales + equipos + mano de obra). No se
        # aplica a los tramites porque las tasas publicas no generan overhead.
        # El IVA solo grava compras, equipos y gastos generales asociados a
        # partidas gravadas; excluye nomina en relacion de dependencia y tasas.
        base_admin = directos + equipos + mano_obra
        administrativos = round(base_admin * admin_pct / 100.0, 2)
        privada = round(base_admin + administrativos, 2)
        base = privada + tramites
        base_iva = round((directos_gravados + equipos_gravados) * (1.0 + admin_pct / 100.0), 2)
        iva_monto = round(base_iva * iva, 2) if escenario.get("aplica_iva") else 0.0
        return {
            "directos": round(directos, 2),
            "equipos": round(equipos, 2),
            "mano_obra_incluida": round(mano_obra, 2),
            "decimo_cuarto_diario": round(decimo_cuarto, 4),
            "administrativos": administrativos,
            "admin_pct": admin_pct,
            "privada": privada,
            "tramites": round(tramites, 2),
            "base": round(base, 2),
            "base_iva": base_iva,
            "iva": iva_monto,
            "total": round(base + iva_monto, 2),
            "detalle": detalle,
            "canton": escenario.get("canton", ""),
            "advertencias_cantonales": advertencias_cantonales,
            "tarifas_cantonales": tarifas_cantonales,
        }

    # ------------------------------------------------------------- Serializacion
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "escenario": dict(self.escenario),
            "actividades": [actividad.to_dict() for actividad in self.actividades.values()],
        }

    @classmethod
    def from_dict(cls, datos: Dict[str, Any]) -> "Proyecto":
        """Construye el proyecto conservando todas las dependencias declaradas.

        Las predecesoras inexistentes se mantienen y se reportan con
        :meth:`dependencias_huerfanas`; el validador las muestra como error. Asi
        cargar un archivo nunca destruye informacion del usuario.
        """
        if not isinstance(datos, dict):
            raise ValueError("El proyecto debe ser un objeto JSON.")
        escenario = datos.get("escenario")
        proyecto = cls(
            nombre=str(datos.get("nombre") or "Proyecto sin titulo"),
            descripcion=str(datos.get("descripcion") or ""),
            escenario=dict(escenario) if isinstance(escenario, dict) else {},
        )
        actividades = datos.get("actividades")
        if not isinstance(actividades, list):
            actividades = []
        for bruto in actividades:
            try:
                proyecto.agregar(Actividad.from_dict(bruto))
            except (TypeError, ValueError, KeyError):
                # Una fila corrupta no debe impedir cargar el resto del proyecto.
                continue
        return proyecto

    def guardar(self, ruta: Path) -> None:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def cargar(cls, ruta: Path) -> "Proyecto":
        return cls.from_dict(cargar_json(Path(ruta)))


def nuevo_id(nombre: str, existentes: Iterable[str]) -> str:
    """Genera un id unico a partir del nombre."""
    base = _slug(nombre)
    existentes = set(existentes)
    if base not in existentes:
        return base
    indice = 2
    while f"{base}_{indice}" in existentes:
        indice += 1
    return f"{base}_{indice}"
