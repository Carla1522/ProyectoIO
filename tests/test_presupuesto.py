"""Pruebas de presupuesto y consistencia del catalogo normativo."""

from __future__ import annotations

import unittest

from core.modelo import (
    Actividad,
    Proyecto,
    cargar_base_ecuador,
    cargar_parametros,
    catalogo_por_id,
)


def proyecto_con_costos() -> Proyecto:
    proyecto = Proyecto(escenario={"tamano_empresa": "micro", "area_m2": 0, "aplica_iva": True})
    proyecto.agregar(
        Actividad(
            id="a", nombre="Actividad privada", tipo="privada",
            optimista=5, probable=5, pesimista=5,
            costo=1000.0, costo_equipos=500.0,
            trabajadores=2, costo_mo_diario=30.0,
        )
    )
    proyecto.agregar(
        Actividad(id="t", nombre="Tramite", tipo="tramite",
                  optimista=1, probable=1, pesimista=1, costo=100.0)
    )
    return proyecto


class TestPresupuesto(unittest.TestCase):
    def setUp(self) -> None:
        self.parametros = cargar_parametros()
        self.proyecto = proyecto_con_costos()
        self.costos = self.proyecto.resumen_costos(self.parametros)

    def test_factor_cargas_desde_componentes(self) -> None:
        componentes = self.parametros["costo_empleador"]["componentes"]
        esperado = 1 + sum(componentes.values()) / 100
        self.assertAlmostEqual(self.proyecto.factor_cargas(self.parametros), esperado, places=6)
        self.assertAlmostEqual(esperado, 1.4131, places=4)

    def test_mano_de_obra_cargada(self) -> None:
        esperado = 2 * 30 * 1.4131 * 5
        self.assertAlmostEqual(self.costos["mano_obra_incluida"], round(esperado, 2), places=2)

    def test_total_sin_duplicaciones(self) -> None:
        suma_partidas = (
            self.costos["directos"]
            + self.costos["equipos"]
            + self.costos["mano_obra_incluida"]
            + self.costos["administrativos"]
            + self.costos["tramites"]
            + self.costos["iva"]
        )
        self.assertAlmostEqual(self.costos["total"], suma_partidas, places=2)
        self.assertAlmostEqual(self.costos["base"] + self.costos["iva"], self.costos["total"], places=2)

    def test_administrativos_solo_sobre_inversion_privada(self) -> None:
        base_admin = (
            self.costos["directos"]
            + self.costos["equipos"]
            + self.costos["mano_obra_incluida"]
        )
        self.assertAlmostEqual(self.costos["administrativos"], round(base_admin * 0.05, 2), places=2)
        self.assertAlmostEqual(self.costos["privada"], round(base_admin + self.costos["administrativos"], 2), places=2)

    def test_iva_no_grava_tramites(self) -> None:
        self.assertAlmostEqual(self.costos["iva"], round(self.costos["privada"] * 0.15, 2), places=2)
        self.assertAlmostEqual(
            self.costos["total"],
            round(self.costos["privada"] + self.costos["tramites"] + self.costos["iva"], 2),
            places=2,
        )

    def test_iva_desactivable(self) -> None:
        self.proyecto.escenario["aplica_iva"] = False
        costos = self.proyecto.resumen_costos(self.parametros)
        self.assertEqual(costos["iva"], 0.0)
        self.assertAlmostEqual(costos["total"], costos["base"], places=2)

    def test_admin_personalizado(self) -> None:
        self.proyecto.escenario["admin_pct"] = 0.0
        costos = self.proyecto.resumen_costos(self.parametros)
        self.assertEqual(costos["administrativos"], 0.0)

    def test_detalle_suma_subtotales(self) -> None:
        suma = sum(fila["subtotal"] for fila in self.costos["detalle"])
        self.assertAlmostEqual(
            suma,
            self.costos["directos"] + self.costos["equipos"]
            + self.costos["mano_obra_incluida"] + self.costos["tramites"],
            places=2,
        )


class TestCatalogoEcuador(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = cargar_base_ecuador()
        cls.catalogo = catalogo_por_id(cls.base)

    def test_catalogo_no_vacio_y_con_fuentes(self) -> None:
        self.assertGreaterEqual(len(self.catalogo), 25)
        for ida, tramite in self.catalogo.items():
            with self.subTest(tramite=ida):
                self.assertTrue(tramite["nombre"])
                self.assertTrue(tramite["entidad"])
                self.assertIn(tramite["nivel"], ("nacional", "cantonal"))
                self.assertTrue(tramite["fuente_url"].startswith("https://"))
                self.assertTrue(tramite["fuente_normativa"])

    def test_ids_unicos_y_predecesoras_existen(self) -> None:
        ids = [t["id"] for t in self.base["tramites"]]
        self.assertEqual(len(ids), len(set(ids)))
        for tramite in self.base["tramites"]:
            for pred in tramite.get("predecesoras", []):
                with self.subTest(tramite=tramite["id"], pred=pred):
                    self.assertIn(pred, self.catalogo)

    def test_tiempos_pert_validos(self) -> None:
        for tramite in self.base["tramites"]:
            with self.subTest(tramite=tramite["id"]):
                self.assertLessEqual(0, tramite["optimista"])
                self.assertLessEqual(tramite["optimista"], tramite["probable"])
                self.assertLessEqual(tramite["probable"], tramite["pesimista"])
                self.assertGreaterEqual(tramite["costo"], 0)

    def test_parametros_legales_2026(self) -> None:
        parametros = cargar_parametros()
        self.assertEqual(parametros["salario"]["sbu"], 482.0)
        self.assertEqual(parametros["salario"]["sbu_vigencia"], "2026")
        self.assertEqual(parametros["impuestos"]["iva_pct"], 15.0)
        self.assertEqual(parametros["iess"]["aporte_patronal_pct"], 11.15)
        self.assertEqual(parametros["iess"]["aporte_personal_pct"], 9.45)

    def test_arcsa_exento_para_microempresa(self) -> None:
        micro = Actividad.desde_catalogo(self.catalogo["permiso_arcsa"])
        pequena = Actividad.desde_catalogo(self.catalogo["permiso_arcsa"])
        self.assertEqual(micro.costo_efectivo({"tamano_empresa": "micro"})["directo"], 0.0)
        self.assertEqual(pequena.costo_efectivo({"tamano_empresa": "pequena"})["directo"], 60.0)

    def test_descuento_pyme_en_marca(self) -> None:
        marca = Actividad.desde_catalogo(self.catalogo["registro_marca"])
        self.assertEqual(marca.costo_efectivo({"tamano_empresa": "micro"})["directo"], 104.0)
        self.assertEqual(marca.costo_efectivo({"tamano_empresa": "grande"})["directo"], 208.0)

    def test_costo_por_metro_cuadrado(self) -> None:
        planos = Actividad.desde_catalogo(self.catalogo["aprobacion_planos"])
        sin_area = planos.costo_efectivo({"area_m2": 0})["directo"]
        con_area = planos.costo_efectivo({"area_m2": 100})["directo"]
        self.assertAlmostEqual(con_area - sin_area, 50.0, places=2)


if __name__ == "__main__":
    unittest.main()
