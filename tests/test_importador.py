"""Pruebas de importacion de proyectos desde JSON, XLSX, CSV y PDF."""

from __future__ import annotations

import io
import json
import unittest

from openpyxl import Workbook

from core.calculos_cpm_pert import calcular_cpm, flujo_caja, probabilidad_exito
from core.modelo import Actividad, Proyecto, cargar_parametros
from core.seguridad import ErrorDatos
from core.validador import validar
from services import copiloto_ia, exportador, importador


def _proyecto_muestra() -> Proyecto:
    plan = copiloto_ia.plan_local(
        "Quiero construir un galpon para fabricar muebles en Ambato",
        {"canton": "Ambato", "tamano_empresa": "micro", "area_m2": 300, "empleados": 8},
    )
    return copiloto_ia.aplicar_plan(plan["proyecto"])


class TestImportador(unittest.TestCase):
    def test_importar_json_valido(self) -> None:
        proyecto = Proyecto(nombre="Prueba JSON")
        proyecto.agregar(Actividad("A", "Inicio", optimista=1, probable=2, pesimista=3, costo=100))
        raw = json.dumps(proyecto.to_dict()).encode("utf-8")
        cargado, fmt, avisos = importador.importar_archivo("mi_proyecto.json", raw)
        self.assertEqual(fmt, "json")
        self.assertEqual(avisos, [])
        self.assertEqual(cargado.nombre, "Prueba JSON")
        self.assertIn("A", cargado.actividades)

    def test_importar_csv_coma_y_punto_y_coma(self) -> None:
        csv_coma = (
            "ID,Actividad,Tipo,Predecesoras,a,m,b,Costo USD,IVA\n"
            "A,Diseno,privada,,1,2,4,250,SI\n"
            "B,Obra,privada,A,3,5,8,1200,NO\n"
        ).encode("utf-8")
        cargado, fmt, avisos = importador.importar_archivo("plan.csv", csv_coma)
        self.assertEqual(fmt, "csv")
        self.assertEqual(avisos, [])
        self.assertEqual(cargado.obtener("B").predecesoras, ["A"])
        self.assertTrue(cargado.obtener("A").grava_iva)
        self.assertFalse(cargado.obtener("B").grava_iva)

        csv_semi = (
            "ID;Actividad;Predecesoras;te;Costo\n"
            "A;Tarea 1;;3,5;100,50\n"
            "B;Tarea 2;A;2;50\n"
        ).encode("latin-1")
        cargado2, _, avisos2 = importador.importar_archivo("espanol.csv", csv_semi)
        self.assertEqual(cargado2.obtener("A").optimista, 3.5)
        self.assertEqual(cargado2.obtener("A").costo, 100.50)
        self.assertTrue(avisos2)

    def test_importar_xlsx_plantilla_y_roundtrip_exportador(self) -> None:
        plantilla = importador.plantilla_excel()
        cargado_p, fmt_p, _ = importador.importar_archivo("plantilla.xlsx", plantilla)
        self.assertEqual(fmt_p, "xlsx")
        self.assertEqual(set(cargado_p.actividades), {"A", "B"})
        self.assertEqual(cargado_p.obtener("B").predecesoras, ["A"])

        proyecto = _proyecto_muestra()
        cpm = calcular_cpm(proyecto)
        costos = proyecto.resumen_costos(cargar_parametros())
        flujo = flujo_caja(cpm, costos["detalle"], administrativos=costos["administrativos"])
        excel_bytes = exportador.exportar_excel(
            proyecto, cpm, costos, flujo, probabilidad_exito(cpm, round(cpm["duracion"])), validar(proyecto)
        )
        reimportado, fmt_x, _ = importador.importar_archivo("informe_proyecto.xlsx", excel_bytes)
        self.assertEqual(fmt_x, "xlsx")
        self.assertEqual(len(reimportado.actividades), len(proyecto.actividades))
        self.assertEqual(reimportado.escenario["canton"], "Ambato")
        self.assertIn("ruc", reimportado.actividades)
        self.assertEqual(reimportado.obtener("cimentacion").costo, proyecto.obtener("cimentacion").costo)

    def test_importar_xlsx_con_encabezado_desplazado(self) -> None:
        libro = Workbook()
        hoja = libro.active
        hoja.append(["Reporte externo"])
        hoja.append([])
        hoja.append(["Codigo", "Nombre", "Depende de", "Optimista", "Probable", "Pesimista", "Costo"])
        hoja.append(["T1", "Estudio", "", 2, 3, 5, 400])
        hoja.append(["T2", "Permiso", "T1", 1, 2, 4, 50])
        buf = io.BytesIO()
        libro.save(buf)

        cargado, _, _ = importador.importar_archivo("externo.xlsx", buf.getvalue())
        self.assertEqual(set(cargado.actividades), {"T1", "T2"})
        self.assertEqual(cargado.obtener("T2").predecesoras, ["T1"])

    def test_importar_pdf_exportado_por_ecuaproject(self) -> None:
        proyecto = _proyecto_muestra()
        cpm = calcular_cpm(proyecto)
        costos = proyecto.resumen_costos(cargar_parametros())
        flujo = flujo_caja(cpm, costos["detalle"], administrativos=costos["administrativos"])
        pdf_bytes = exportador.exportar_pdf(
            proyecto, cpm, costos, flujo, probabilidad_exito(cpm, round(cpm["duracion"])), validar(proyecto)
        )

        cargado, fmt, avisos = importador.importar_archivo("informe.pdf", pdf_bytes)
        self.assertEqual(fmt, "pdf")
        self.assertEqual(len(cargado.actividades), len(proyecto.actividades))
        self.assertTrue(any("PDF" in a for a in avisos))

    def test_rechaza_archivo_grande_o_invalido(self) -> None:
        with self.assertRaises(ErrorDatos):
            importador.importar_archivo("vacio.csv", b"")
        with self.assertRaises(ErrorDatos):
            importador.importar_archivo("grande.csv", b"x" * 2_000_001)
        with self.assertRaises(ErrorDatos):
            importador.importar_archivo("desconocido.txt", b"hola")
        with self.assertRaises(ErrorDatos):
            importador.importar_archivo("corrupto.pdf", b"%PDF-corrupto")


if __name__ == "__main__":
    unittest.main()
