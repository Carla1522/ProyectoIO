"""Pruebas de validacion, reglas legales y planes del copiloto local."""

from __future__ import annotations

import unittest
from unittest.mock import patch

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

    def test_conexion_energia_condicional_obra_vs_local(self) -> None:
        local = Proyecto()
        local.agregar(Actividad("ruc", "RUC", tipo="tramite"))
        local.agregar(Actividad("uso_suelo", "Uso de suelo", tipo="tramite", predecesoras=["ruc"]))
        local.agregar(
            Actividad("conexion_energia", "Conexion electrica", tipo="tramite", predecesoras=["uso_suelo"])
        )
        self.assertFalse([p for p in validar(local, self.base, self.parametros) if p.codigo == "regla_legal"])

        obra = Proyecto()
        obra.agregar(Actividad("ruc", "RUC", tipo="tramite"))
        obra.agregar(Actividad("uso_suelo", "Uso de suelo", tipo="tramite", predecesoras=["ruc"]))
        obra.agregar(Actividad("aprobacion_planos", "Planos", tipo="tramite", predecesoras=["uso_suelo"]))
        obra.agregar(Actividad("linea_fabrica", "Linea", tipo="tramite", predecesoras=["aprobacion_planos"]))
        obra.agregar(
            Actividad("permiso_construccion", "Permiso", tipo="tramite", predecesoras=["aprobacion_planos", "linea_fabrica"])
        )
        obra.agregar(
            Actividad("conexion_energia", "Conexion electrica", tipo="tramite", predecesoras=["uso_suelo"])
        )
        reglas = [p for p in validar(obra, self.base, self.parametros) if p.codigo == "regla_legal"]
        self.assertTrue(any("Permiso" in p.mensaje and "construccion" in p.mensaje for p in reglas))

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
            "Quiero abrir un taller de carpinteria para fabricar muebles en Quito",
            "Quiero abrir un restaurante de comida tipica en Quito",
            "Quiero abrir un consultorio medico o clinica privada en Quito",
            "Quiero abrir un hostal turistico de 200 m2 en Ambato",
            "Quiero iniciar un cultivo agricola de cacao en finca",
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

    def test_reglas_personeria_y_rimpe_en_validador(self) -> None:
        proyecto = Proyecto(
            escenario={"tipo_personeria": "sas", "regimen_tributario": "rimpe_negocio_popular"}
        )
        proyecto.agregar(Actividad("ruc", "RUC", tipo="tramite"))
        problemas = validar(proyecto, self.base, cargar_parametros())
        codigos = {p.codigo for p in problemas}
        self.assertIn("regimen_incompatible", codigos)
        self.assertIn("personeria_sin_constitucion", codigos)

        plan_sas = self._plan(
            "Quiero abrir una cafeteria en Quito",
            {"canton": "Quito", "tamano_empresa": "micro", "tipo_personeria": "sas", "regimen_tributario": "rimpe_emprendedor"},
        )
        proy_sas = copiloto_ia.aplicar_plan(plan_sas["proyecto"])
        self.assertIn("constitucion_sociedad", proy_sas.actividades)
        self.assertIn("nombramiento_representante", proy_sas.actividades)
        self.assertIn("regimen_rimpe", proy_sas.actividades)
        problemas_sas = validar(proy_sas, self.base, cargar_parametros())
        self.assertFalse([p for p in problemas_sas if p.nivel == ERROR])

        plan_agro = self._plan(
            "Quiero iniciar un cultivo agricola en finca",
            {"canton": "Ambato", "tamano_empresa": "micro", "regimen_tributario": "rimpe_emprendedor"},
        )
        proy_agro = copiloto_ia.aplicar_plan(plan_agro["proyecto"])
        codigos_agro = {p.codigo for p in validar(proy_agro, self.base, cargar_parametros())}
        self.assertIn("actividad_excluida_rimpe", codigos_agro)

    def test_validacion_empleados_escenario(self) -> None:
        proyecto = Proyecto(escenario={"empleados": 12})
        proyecto.agregar(Actividad("a", "Obra", trabajadores=15, optimista=2, probable=2, pesimista=2))
        codigos = {p.codigo for p in validar(proyecto, self.base, cargar_parametros())}
        self.assertIn("empleados_sin_iess", codigos)
        self.assertIn("empleados_sin_reglamento_higiene", codigos)
        self.assertIn("trabajadores_sobre_escenario", codigos)

    def test_aplicar_plan_conserva_area_de_barra_lateral(self) -> None:
        actual = Proyecto(escenario={"canton": "Quito", "area_m2": 1000.0, "tipo_personeria": "sas"})
        plan = {
            "nombre": "Ferreteria",
            "escenario": {"canton": "Quito", "area_m2": 0, "tipo_personeria": "persona_natural"},
            "actividades": [{"id": "a", "nombre": "A", "optimista": 1, "probable": 1, "pesimista": 1}],
        }
        resultado = copiloto_ia.aplicar_plan(plan, proyecto_actual=actual)
        self.assertEqual(resultado.escenario["area_m2"], 1000.0)
        self.assertEqual(resultado.escenario["tipo_personeria"], "sas")

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

    @patch(
        "services.copiloto_ia.configuracion",
        return_value={"proveedor": "local", "modelo": "local", "gemini": "", "openai": "", "clave_configurada": False},
    )
    def test_conversacion_corta_pide_contexto(self, _mock_cfg) -> None:
        respuesta = copiloto_ia.conversar([], "Hola", {"canton": "Ambato"})
        self.assertFalse(respuesta["listo"])
        self.assertTrue(respuesta["preguntas"])

    @patch.dict("os.environ", {}, clear=True)
    @patch(
        "services.copiloto_ia.configuracion",
        return_value={
            "proveedor": "gemini",
            "modelo": "gemini-flash-latest",
            "gemini": "secret_from_toml",
            "openai": "",
            "clave_configurada": True,
        },
    )
    @patch(
        "services.copiloto_ia._llamar_gemini",
        return_value='{"mensaje":"OK","listo":false,"preguntas":["Cuantos m2?"],"supuestos":[],"proyecto":null}',
    )
    def test_conversar_usa_clave_de_secrets_sin_env(self, mock_gemini, _mock_cfg) -> None:
        respuesta = copiloto_ia.conversar([], "Quiero abrir una ferreteria", {"canton": "Ambato"})
        self.assertEqual(respuesta["modo"], "api")
        mock_gemini.assert_called_once()

    def test_deteccion_de_etiquetas(self) -> None:
        etiquetas = copiloto_ia.detectar_etiquetas(
            "Restaurante de comida con 8 empleados y marca propia"
        )
        self.assertIn("alimentos", etiquetas)
        self.assertIn("marca", etiquetas)
        self.assertIn("empleador", etiquetas)


if __name__ == "__main__":
    unittest.main()
