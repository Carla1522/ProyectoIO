"""Pruebas del modulo de costos cantonales.

El objetivo es demostrar tres cosas:

1. Cada canton aplica su propio tarifario (no se copian valores entre ciudades).
2. Sin datos del canton o sin area, se conserva el costo del catalogo y se avisa.
3. El presupuesto usa la tarifa cantonal resuelta, no un valor fijo global.
"""

from __future__ import annotations

import unittest

from core.costos_cantonales import (
    datos_canton,
    lista_cantones,
    resolver_tarifa,
    resumen_canton,
)
from core.modelo import Actividad, Proyecto, cargar_base_ecuador, cargar_parametros, catalogo_por_id
from core.validador import validar


def actividad_cantonal(ida: str = "bomberos") -> Actividad:
    tramite = catalogo_por_id()[ida]
    return Actividad.desde_catalogo(tramite)


class TestResolverTarifas(unittest.TestCase):
    def setUp(self) -> None:
        self.parametros = cargar_parametros()

    def test_solo_actividades_cantonales(self) -> None:
        privada = Actividad("x", "X")
        self.assertIsNone(resolver_tarifa(privada, {"canton": "Ambato"}, self.parametros))
        nacional = Actividad("ruc", "RUC", tipo="tramite", nivel="nacional")
        self.assertIsNone(resolver_tarifa(nacional, {"canton": "Ambato"}, self.parametros))

    def test_bomberos_difiere_por_canton(self) -> None:
        esperado = {"Ambato": 15.0, "Quito": 18.0, "Guayaquil": 20.0}
        for canton, monto in esperado.items():
            with self.subTest(canton=canton):
                tarifa = resolver_tarifa(
                    actividad_cantonal(), {"canton": canton}, self.parametros
                )
                self.assertIsNotNone(tarifa)
                self.assertTrue(tarifa["aplica"])
                self.assertEqual(tarifa["origen"], "cantonal")
                self.assertAlmostEqual(tarifa["costo"], monto, places=2)

    def test_construccion_por_metro_cuadrado(self) -> None:
        actividad = actividad_cantonal("permiso_construccion")
        tarifa = resolver_tarifa(
            actividad, {"canton": "Ambato", "area_m2": 100}, self.parametros
        )
        self.assertTrue(tarifa["aplica"])
        self.assertAlmostEqual(tarifa["costo"], 3.5 * 100, places=2)

    def test_sin_area_conserva_catalogo_y_advierte(self) -> None:
        actividad = actividad_cantonal("permiso_construccion")
        tarifa = resolver_tarifa(
            actividad, {"canton": "Ambato", "area_m2": 0}, self.parametros
        )
        self.assertFalse(tarifa["aplica"])
        self.assertAlmostEqual(tarifa["costo"], actividad.costo, places=2)
        self.assertTrue(tarifa["advertencia"])

    def test_canton_sin_tarifario_no_inventa_datos(self) -> None:
        tarifa = resolver_tarifa(
            actividad_cantonal(), {"canton": "Loja"}, self.parametros
        )
        self.assertFalse(tarifa["aplica"])
        self.assertEqual(tarifa["origen"], "catalogo")
        self.assertIn("Loja", tarifa["advertencia"])
        self.assertTrue(tarifa["advertencia"])

    def test_cada_canton_declara_sus_tarifas(self) -> None:
        self.assertIn("Ambato", lista_cantones(self.parametros))
        for canton in lista_cantones(self.parametros):
            datos = datos_canton(canton, self.parametros)
            self.assertIsNotNone(datos)
            self.assertIn("tarifas", datos)
            self.assertIn("bomberos", datos["tarifas"])
            self.assertFalse(datos["verificado"], "no se declara verificado sin tarifario directo")
            self.assertTrue(datos["fuente_url"].startswith("https://"))
            info = resumen_canton(canton, self.parametros)
            self.assertTrue(info["disponible"])


class TestPresupuestoCantonal(unittest.TestCase):
    def _proyecto(self, canton: str) -> Proyecto:
        proyecto = Proyecto(escenario={"canton": canton, "area_m2": 100})
        proyecto.agregar(actividad_cantonal("bomberos"))
        proyecto.agregar(actividad_cantonal("permiso_construccion"))
        proyecto.agregar(actividad_cantonal("uso_suelo"))
        return proyecto

    def test_presupuesto_cambia_con_el_canton(self) -> None:
        parametros = cargar_parametros()
        ambato = self._proyecto("Ambato").resumen_costos(parametros)
        quito = self._proyecto("Quito").resumen_costos(parametros)
        self.assertNotAlmostEqual(ambato["tramites"], quito["tramites"], places=2)
        # 15 + 350 + 2 vs 18 + 400 + 2
        self.assertAlmostEqual(ambato["tramites"], 367.0, places=2)
        self.assertAlmostEqual(quito["tramites"], 420.0, places=2)

    def test_trazabilidad_de_tarifas(self) -> None:
        resultado = self._proyecto("Guayaquil").resumen_costos(cargar_parametros())
        tarifas = {t["id"]: t for t in resultado["tarifas_cantonales"]}
        self.assertEqual(tarifas["bomberos"]["origen"], "cantonal")
        self.assertEqual(tarifas["bomberos"]["canton"], "Guayaquil")
        self.assertAlmostEqual(tarifas["bomberos"]["costo"], 20.0, places=2)

    def test_validador_advierte_canton_desconocido(self) -> None:
        proyecto = self._proyecto("Loja")
        problemas = validar(proyecto, cargar_base_ecuador(), cargar_parametros())
        codigos = {p.codigo for p in problemas}
        self.assertIn("canton_sin_tarifario", codigos)

    def test_catalogo_marca_estimaciones_sin_fuente_directa(self) -> None:
        base = cargar_base_ecuador()
        for tramite in base["tramites"]:
            with self.subTest(tramite=tramite["id"]):
                self.assertIn(tramite.get("valor_tipo"), ("oficial", "estimacion", "rango", "mercado"))
                self.assertIn(tramite.get("fuente_tipo"), ("portal_institucional", "directa"))
                self.assertTrue(tramite.get("verificado_en"))
                if tramite["nivel"] == "cantonal":
                    self.assertNotEqual(tramite.get("valor_tipo"), "oficial")
                    self.assertTrue(tramite.get("verificar"))


if __name__ == "__main__":
    unittest.main()
