"""Pruebas de los informes exportables y de los graficos."""

from __future__ import annotations

import io
import unittest

from core.calculos_cpm_pert import calcular_cpm, flujo_caja, probabilidad_exito
from core.modelo import cargar_parametros
from core.validador import validar
from services import copiloto_ia, exportador
from ui import graficos


def proyecto_ejemplo():
    plan = copiloto_ia.plan_local(
        "Quiero construir un galpon para fabricar muebles en Ambato",
        {"canton": "Ambato", "tamano_empresa": "micro", "area_m2": 300, "empleados": 8},
    )
    return copiloto_ia.aplicar_plan(plan["proyecto"])


class TestInformes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.proyecto = proyecto_ejemplo()
        cls.cpm = calcular_cpm(cls.proyecto)
        cls.costos = cls.proyecto.resumen_costos(cargar_parametros())
        cls.flujo = flujo_caja(
            cls.cpm, cls.costos["detalle"], administrativos=cls.costos["administrativos"]
        )
        cls.probabilidad = probabilidad_exito(cls.cpm, round(cls.cpm["duracion"]))
        cls.problemas = validar(cls.proyecto)

    def test_excel_contiene_hojas_esperadas(self) -> None:
        from openpyxl import load_workbook

        contenido = exportador.exportar_excel(
            self.proyecto, self.cpm, self.costos, self.flujo,
            self.probabilidad, self.problemas,
        )
        self.assertTrue(contenido.startswith(b"PK"))
        libro = load_workbook(io.BytesIO(contenido))
        hojas = set(libro.sheetnames)
        self.assertTrue(
            {"Resumen", "Actividades CPM", "Presupuesto", "Ruta critica",
             "Flujo de caja", "Fuentes normativas", "Observaciones"}.issubset(hojas)
        )
        resumen = libro["Resumen"]
        texto = " ".join(str(celda.value) for fila in resumen.iter_rows() for celda in fila if celda.value)
        self.assertIn("Duracion esperada", texto)
        self.assertIn("IVA", texto)

    def test_pdf_valido_y_con_gantt(self) -> None:
        contenido = exportador.exportar_pdf(
            self.proyecto, self.cpm, self.costos, self.flujo,
            self.probabilidad, self.problemas,
        )
        self.assertTrue(contenido.startswith(b"%PDF"))
        self.assertGreater(len(contenido), 8000)

    def test_pdf_sin_flujo_ni_probabilidad(self) -> None:
        contenido = exportador.exportar_pdf(
            self.proyecto, self.cpm, self.costos, None, None, None
        )
        self.assertTrue(contenido.startswith(b"%PDF"))

    def test_flujo_reconcilia_en_informe(self) -> None:
        self.assertAlmostEqual(
            self.flujo[-1]["acumulado"], self.costos["base"], delta=0.1
        )


class TestGraficos(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.proyecto = proyecto_ejemplo()
        cls.cpm = calcular_cpm(cls.proyecto)
        cls.flujo = flujo_caja(
            cls.cpm, cls.proyecto.resumen_costos(cargar_parametros())["detalle"],
            administrativos=5.0,
        )

    def test_red_y_gantt_tienen_trazas(self) -> None:
        self.assertGreater(len(graficos.diagrama_red(self.cpm, self.proyecto).data), 3)
        self.assertGreaterEqual(len(graficos.diagrama_gantt(self.cpm, self.proyecto).data), 2)

    def test_campana_y_flujo(self) -> None:
        self.assertGreaterEqual(len(graficos.campana_gauss(self.cpm, 100, 0.3).data), 2)
        self.assertEqual(len(graficos.flujo_caja_grafico(self.flujo).data), 2)

    def test_campana_con_sigma_cero(self) -> None:
        cpm = {"duracion": 10.0, "sigma": 0.0}
        figura = graficos.campana_gauss(cpm, 10, 1.0)
        self.assertGreaterEqual(len(figura.layout.shapes), 1)


if __name__ == "__main__":
    unittest.main()
