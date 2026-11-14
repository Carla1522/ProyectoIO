"""Pruebas de validacion, reglas legales y planes del copiloto local."""

from __future__ import annotations

import unittest

from core.modelo import Actividad, Proyecto, cargar_base_ecuador, cargar_parametros
from core.validador import (
    ADVERTENCIA,
    ERROR,
    hay_errores,
    tramites_obligatorios_faltantes,
    validar,
)
from services import copiloto_ia


class TestValidador(unittest.TestCase):
    def setUp(self) -> None:
        self.base = cargar_base_ecuador()
        self.parametros = cargar_parametros()

    def test_predecesora_inexistente(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(Actividad("a", "A", predecesoras=["fantasma"]))
        problemas = validar(proyecto, self.base, self.parametros)
        self.assertTrue(hay_errores(problemas))
        self.assertIn("predecesora_inexistente", {p.codigo for p in problemas})

    def test_ciclo_reportado(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(Actividad("a", "A", predecesoras=["b"]))
        proyecto.agregar(Actividad("b", "B", predecesoras=["a"]))
        problemas = validar(proyecto, self.base, self.parametros)
        self.assertIn("ciclo", {p.codigo for p in problemas})
        self.assertTrue(hay_errores(problemas))

    def test_tiempos_invalidos(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(Actividad("a", "A", optimista=5, probable=2, pesimista=1))
        problemas = validar(proyecto, self.base, self.parametros)
        self.assertIn("tiempos_invalidos", {p.codigo for p in problemas})

    def test_regla_legal_patente_sin_uso_suelo(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(Actividad("patente_municipal", "Patente", tipo="tramite", costo=10))
        problemas = validar(proyecto, self.base, self.parametros)
        reglas = [p for p in problemas if p.codigo == "regla_legal"]
        self.assertTrue(reglas)
        self.assertTrue(any("uso_suelo" in p.mensaje for p in reglas))

    def test_cadena_legal_correcta_no_reporta_error(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(Actividad("ruc", "RUC", tipo="tramite"))
        proyecto.agregar(Actividad("uso_suelo", "Uso de suelo", tipo="tramite", predecesoras=["ruc"]))
        proyecto.agregar(
            Actividad("patente_municipal", "Patente", tipo="tramite", predecesoras=["ruc", "uso_suelo"])
        )
        problemas = validar(proyecto, self.base, self.parametros)
        self.assertFalse([p for p in problemas if p.codigo == "regla_legal"])

    def test_mano_de_obra_bajo_sbu(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(
            Actividad("a", "A", optimista=1, probable=1, pesimista=1,
                      trabajadores=1, costo_mo_diario=10.0)
        )
        problemas = validar(proyecto, self.base, self.parametros)
        self.assertIn("mano_obra_bajo_sbu", {p.codigo for p in problemas})
        self.assertTrue(any(p.nivel == ADVERTENCIA for p in problemas))

    def test_tasa_por_confirmar(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(Actividad.desde_catalogo(
            next(t for t in self.base["tramites"] if t.get("verificar"))
        ))
        problemas = validar(proyecto, self.base, self.parametros)
        self.assertIn("tasa_por_confirmar", {p.codigo for p in problemas})

    def test_proyecto_vacio(self) -> None:
        problemas = validar(Proyecto(), self.base, self.parametros)
        self.assertEqual(len(problemas), 1)
        self.assertEqual(problemas[0].codigo, "vacio")
        self.assertFalse(hay_errores(problemas))

    def test_tramites_obligatorios_faltantes(self) -> None:
        proyecto = Proyecto()
        etiquetas = copiloto_ia.detectar_etiquetas(
            "Quiero abrir un restaurante en Ambato"
        )
        faltantes = tramites_obligatorios_faltantes(proyecto, etiquetas, self.base)
        ids = {t["id"] for t in faltantes}
        self.assertIn("ruc", ids)
        self.assertIn("permiso_arcsa", ids)
        proyecto.agregar(Actividad("ruc", "RUC", tipo="tramite"))
        faltantes = tramites_obligatorios_faltantes(proyecto, etiquetas, self.base)
        self.assertNotIn("ruc", {t["id"] for t in faltantes})


class TestCopilotoLocal(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = cargar_base_ecuador()
        cls.catalogo = {t["id"]: t for t in cls.base["tramites"]}

    def _plan(self, descripcion: str, escenario: dict | None = None):
        return copiloto_ia.plan_local(
            descripcion,
            escenario or {"canton": "Ambato", "tamano_empresa": "micro", "empleados": 5},
            self.base,
        )

    def test_planes_validos_para_tres_giros(self) -> None:
        casos = [
            "Quiero construir un galpon para fabricar muebles en Ambato",
            "Quiero abrir un restaurante de comida tipica en Quito",
            "Quiero desarrollar una aplicacion web para gestionar clinicas",
        ]
        for descripcion in casos:
            with self.subTest(descripcion=descripcion):
                plan = self._plan(descripcion)
                self.assertTrue(plan["listo"])
                proyecto = copiloto_ia.aplicar_plan(plan["proyecto"])
                self.assertGreater(len(proyecto.actividades), 5)
                problemas = validar(proyecto, self.base, cargar_parametros())
                self.assertFalse(
                    [p for p in problemas if p.nivel == ERROR],
                    msg=[p.mensaje for p in problemas if p.nivel == ERROR],
                )

    def test_planes_solo_usan_tramites_del_catalogo(self) -> None:
        plan = self._plan("Quiero una panaderia con marca propia en Ambato")
        for actividad in plan["proyecto"]["actividades"]:
            if actividad["tipo"] == "tramite":
                with self.subTest(actividad=actividad["id"]):
                    self.assertIn(actividad["id"], self.catalogo)

    def test_predecesoras_del_plan_existen(self) -> None:
        plan = self._plan("Quiero construir un galpon industrial en Ambato")
        ids = {a["id"] for a in plan["proyecto"]["actividades"]}
        for actividad in plan["proyecto"]["actividades"]:
            for pred in actividad.get("predecesoras", []):
                with self.subTest(actividad=actividad["id"], pred=pred):
                    self.assertIn(pred, ids)

    def test_aplicar_plan_normaliza_tiempos(self) -> None:
        plan = {
            "nombre": "Prueba",
            "actividades": [
                {"id": "a", "nombre": "A", "tipo": "privada",
                 "optimista": 9, "probable": 2, "pesimista": 3, "costo": -5},
            ],
        }
        proyecto = copiloto_ia.aplicar_plan(plan)
        actividad = proyecto.obtener("a")
        self.assertEqual(actividad.optimista, 2)
        self.assertEqual(actividad.probable, 3)
        self.assertEqual(actividad.pesimista, 9)
        self.assertEqual(actividad.costo, 0.0)

    def test_aplicar_plan_conserva_predecesoras_inexistentes(self) -> None:
        """La referencia se conserva: el validador debe reportarla, no borrarla."""
        plan = {
            "nombre": "Prueba",
            "actividades": [
                {"id": "a", "nombre": "A", "predecesoras": ["no_existe"]},
            ],
        }
        proyecto = copiloto_ia.aplicar_plan(plan)
        self.assertEqual(proyecto.obtener("a").predecesoras, ["no_existe"])
        self.assertEqual(proyecto.dependencias_huerfanas(), {"a": ["no_existe"]})

    def test_conversacion_corta_pide_contexto(self) -> None:
        respuesta = copiloto_ia.conversar([], "Hola", {"canton": "Ambato"})
        self.assertFalse(respuesta["listo"])
        self.assertTrue(respuesta["preguntas"])

    def test_deteccion_de_etiquetas(self) -> None:
        etiquetas = copiloto_ia.detectar_etiquetas(
            "Restaurante de comida con 8 empleados y marca propia"
        )
        self.assertIn("alimentos", etiquetas)
        self.assertIn("marca", etiquetas)
        self.assertIn("empleador", etiquetas)


if __name__ == "__main__":
    unittest.main()
