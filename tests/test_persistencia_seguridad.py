"""Pruebas de persistencia, dependencias y seguridad de entradas.

Cubren los fallos que la auditoria de la segunda etapa detecto:

* cargar o calcular borraba predecesoras inexistentes,
* el editor reconstruia el proyecto descartando referencias desconocidas,
* el JSON de usuario se aceptaba sin validar tipos ni limites,
* el HTML de la interfaz interpolaba texto sin escapar.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

import pandas as pd

from core.calculos_cpm_pert import calcular_cpm
from core.modelo import Actividad, Proyecto
from core.seguridad import (
    ErrorDatos,
    cargar_json_bytes,
    escapar,
    sanitizar_nombre_archivo,
    url_segura,
    validar_proyecto_json,
)
from core.validador import ERROR, validar
from services import copiloto_ia
from ui.componentes import COLUMNAS_EDITABLES, proyecto_desde_dataframe


def proyecto_con_huerfana() -> Proyecto:
    proyecto = Proyecto(nombre="Prueba")
    proyecto.agregar(Actividad("a", "A", optimista=2, probable=2, pesimista=2,
                               predecesoras=["fantasma"]))
    proyecto.agregar(Actividad("b", "B", predecesoras=["a"]))
    return proyecto


class TestDependenciasConservadas(unittest.TestCase):
    def test_calcular_cpm_no_borra_predecesoras(self) -> None:
        proyecto = proyecto_con_huerfana()
        cpm = calcular_cpm(proyecto)
        self.assertEqual(proyecto.obtener("a").predecesoras, ["fantasma"])
        self.assertEqual(cpm["dependencias_huerfanas"], {"a": ["fantasma"]})
        # a = 2 dias; b usa la duracion por defecto (1 dia) y depende de a.
        self.assertEqual(cpm["duracion"], 3.0)

    def test_validador_reporta_la_referencia_conservada(self) -> None:
        problemas = validar(proyecto_con_huerfana())
        errores = [p for p in problemas if p.nivel == ERROR]
        self.assertTrue(any(p.codigo == "predecesora_inexistente" for p in errores))
        self.assertTrue(any("se conserva" in p.mensaje for p in errores))

    def test_from_dict_conserva_y_roundtrip(self) -> None:
        original = proyecto_con_huerfana()
        cargado = Proyecto.from_dict(original.to_dict())
        self.assertEqual(cargado.obtener("a").predecesoras, ["fantasma"])
        self.assertEqual(cargado.to_dict(), original.to_dict())

    def test_guardar_y_cargar_archivo(self) -> None:
        original = proyecto_con_huerfana()
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "proyecto.json")
            original.guardar(ruta)
            cargado = Proyecto.cargar(ruta)
        self.assertEqual(cargado.dependencias_huerfanas(), {"a": ["fantasma"]})

    def test_limpieza_solo_es_explicita(self) -> None:
        proyecto = proyecto_con_huerfana()
        eliminadas = proyecto.limpiar_predecesoras_huerfanas()
        self.assertEqual(eliminadas, {"a": ["fantasma"]})
        self.assertEqual(proyecto.obtener("a").predecesoras, [])

    def test_editor_conserva_predecesora_desconocida(self) -> None:
        original = Proyecto(nombre="Editor")
        original.agregar(Actividad("a", "A", optimista=1, probable=1, pesimista=1))
        tabla = pd.DataFrame(
            [
                {
                    "ID": "a", "Actividad": "A", "Tipo": "privada",
                    "Predecesoras": "fantasma", "a": 1.0, "m": 1.0, "b": 1.0,
                    "Costo USD": 0.0, "Equipos USD": 0.0, "Trabajadores": 0,
                    "Costo MO/dia": 0.0, "Entidad": "",
                }
            ],
            columns=COLUMNAS_EDITABLES,
        )
        nuevo = proyecto_desde_dataframe(original, tabla)
        self.assertEqual(nuevo.obtener("a").predecesoras, ["fantasma"])

    def test_plan_ia_con_tramite_inventado_pasa_a_privada(self) -> None:
        plan = {
            "nombre": "Plan",
            "actividades": [
                {"id": "permiso_inventado", "nombre": "Permiso inventado",
                 "tipo": "tramite", "costo": 500, "optimista": 1, "probable": 1,
                 "pesimista": 1},
            ],
        }
        proyecto = copiloto_ia.aplicar_plan(plan)
        actividad = proyecto.obtener("permiso_inventado")
        self.assertEqual(actividad.tipo, "privada")
        self.assertIn("fuera del catalogo", actividad.notas)


class TestSeguridadEntradas(unittest.TestCase):
    def test_escapar_html(self) -> None:
        texto = escapar('<img src=x onerror="alert(1)">')
        self.assertNotIn("<img", texto)
        self.assertIn("&lt;img", texto)
        self.assertIn("&quot;", texto)

    def test_urls_peligrosas_rechazadas(self) -> None:
        for url in (
            "javascript:alert(1)",
            "data:text/html;base64,PHNjcmlwdD4=",
            "https://user:pass@example.com/",
            "https://example.com/\n<script>",
            "file:///etc/passwd",
            "",
            None,
        ):
            with self.subTest(url=url):
                self.assertEqual(url_segura(url), "")
        self.assertEqual(
            url_segura("https://www.ambiente.gob.ec/"), "https://www.ambiente.gob.ec/"
        )

    def test_nombre_de_archivo_saneado(self) -> None:
        self.assertEqual(sanitizar_nombre_archivo("../../etc/passwd"), "etc_passwd.json")
        self.assertEqual(sanitizar_nombre_archivo(""), "proyecto.json")

    def _datos_validos(self) -> dict:
        return {
            "nombre": "Proyecto",
            "descripcion": "",
            "escenario": {"canton": "Ambato", "area_m2": 10, "aplica_iva": False},
            "actividades": [
                {"id": "a", "nombre": "A", "tipo": "privada",
                 "optimista": 1, "probable": 2, "pesimista": 3, "costo": 10},
            ],
        }

    def test_json_valido_se_normaliza(self) -> None:
        contenido = json.dumps(self._datos_validos()).encode("utf-8")
        datos = validar_proyecto_json(cargar_json_bytes(contenido))
        self.assertEqual(datos["actividades"][0]["id"], "a")
        self.assertEqual(datos["escenario"]["canton"], "Ambato")

    def test_rechaza_json_gigante(self) -> None:
        contenido = b"{" + b" " * 2_000_001 + b"}"
        with self.assertRaises(ErrorDatos):
            cargar_json_bytes(contenido)

    def test_rechaza_nan_y_raiz_no_objeto(self) -> None:
        with self.assertRaises(ErrorDatos):
            cargar_json_bytes(b'{"costo": NaN}')
        with self.assertRaises(ErrorDatos):
            cargar_json_bytes(b"[1, 2, 3]")

    def test_rechaza_ids_invalidos_y_duplicados(self) -> None:
        datos = self._datos_validos()
        # Un editor de tabla permite espacios; lo que no se acepta es un
        # caracter de control ni un ID desmedido.
        datos["actividades"][0]["id"] = "id\nmalo"
        with self.assertRaises(ErrorDatos):
            validar_proyecto_json(datos)

        datos = self._datos_validos()
        datos["actividades"][0]["id"] = "x" * 65
        with self.assertRaises(ErrorDatos):
            validar_proyecto_json(datos)

        datos = self._datos_validos()
        datos["actividades"][0]["id"] = "id con espacios"
        self.assertEqual(
            validar_proyecto_json(datos)["actividades"][0]["id"], "id con espacios"
        )

        datos = self._datos_validos()
        datos["actividades"].append(dict(datos["actividades"][0]))
        with self.assertRaises(ErrorDatos):
            validar_proyecto_json(datos)

    def test_rechaza_costos_y_tiempos_invalidos(self) -> None:
        for campo, valor in (("costo", -5), ("optimista", -1), ("costo", float("inf"))):
            datos = self._datos_validos()
            datos["actividades"][0][campo] = valor
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ErrorDatos):
                validar_proyecto_json(datos)

    def test_rechaza_demasiadas_actividades(self) -> None:
        datos = self._datos_validos()
        datos["actividades"] = [
            {"id": f"a{i}", "nombre": "A"} for i in range(501)
        ]
        with self.assertRaises(ErrorDatos):
            validar_proyecto_json(datos)

    def test_rechaza_escenario_con_tipos_incorrectos(self) -> None:
        datos = self._datos_validos()
        datos["escenario"]["aplica_iva"] = "si"
        with self.assertRaises(ErrorDatos):
            validar_proyecto_json(datos)


if __name__ == "__main__":
    unittest.main()
