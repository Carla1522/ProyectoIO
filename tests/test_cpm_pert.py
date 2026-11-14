"""Pruebas del motor CPM/PERT.

El escenario base es una red con actividades en paralelo y multiples
predecesoras, resuelta a mano en los comentarios para que cualquier cambio
futuro se contraste contra numeros conocidos.
"""

from __future__ import annotations

import math
import unittest

from core.calculos_cpm_pert import (
    CicloError,
    calcular_cpm,
    flujo_caja,
    orden_topologico,
    plazo_para_probabilidad,
    probabilidad_exito,
    simular_reduccion,
)
from core.modelo import Actividad, Proyecto


def actividad(
    ida: str,
    duracion: float,
    preds: list[str] | None = None,
    tipo: str = "privada",
) -> Actividad:
    return Actividad(
        id=ida,
        nombre=ida.upper(),
        tipo=tipo,
        predecesoras=list(preds or []),
        optimista=duracion,
        probable=duracion,
        pesimista=duracion,
    )


def red_base() -> Proyecto:
    """A(3) -> B(2), C(4); D(2) depende de B y C; E(3) depende de D.

    Forward:  A 0-3 | B 3-5 | C 3-7 | D 7-9 | E 9-12
    Backward: E LF12/9 | D LF9/7 | B LF7/5 | C LF7/3 | A LF3/0
    Critica:  A -> C -> D -> E (12 dias). B tiene 2 dias de holgura.
    """
    proyecto = Proyecto(nombre="Red base")
    proyecto.agregar(actividad("a", 3))
    proyecto.agregar(actividad("b", 2, ["a"]))
    proyecto.agregar(actividad("c", 4, ["a"]))
    proyecto.agregar(actividad("d", 2, ["b", "c"]))
    proyecto.agregar(actividad("e", 3, ["d"]))
    return proyecto


class TestCPM(unittest.TestCase):
    def setUp(self) -> None:
        self.cpm = calcular_cpm(red_base())
        self.filas = {fila["id"]: fila for fila in self.cpm["filas"]}

    def test_duracion_y_orden(self) -> None:
        self.assertAlmostEqual(self.cpm["duracion"], 12.0)
        self.assertLess(self.cpm["orden"].index("a"), self.cpm["orden"].index("d"))

    def test_es_ef_ls_lf(self) -> None:
        esperado = {
            "a": (0, 3, 0, 3),
            "b": (3, 5, 5, 7),
            "c": (3, 7, 3, 7),
            "d": (7, 9, 7, 9),
            "e": (9, 12, 9, 12),
        }
        for ida, (es, ef, ls, lf) in esperado.items():
            with self.subTest(actividad=ida):
                fila = self.filas[ida]
                self.assertAlmostEqual(fila["es"], es)
                self.assertAlmostEqual(fila["ef"], ef)
                self.assertAlmostEqual(fila["ls"], ls)
                self.assertAlmostEqual(fila["lf"], lf)

    def test_holguras_y_ruta(self) -> None:
        self.assertAlmostEqual(self.filas["b"]["holgura"], 2.0)
        self.assertAlmostEqual(self.filas["a"]["holgura"], 0.0)
        self.assertEqual(
            [f["id"] for f in self.cpm["filas"] if f["critica"]],
            ["a", "c", "d", "e"],
        )
        self.assertEqual(self.cpm["ruta_critica"], ["a", "c", "d", "e"])

    def test_todas_criticas_cuando_todo_es_secuencial(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(actividad("x", 2))
        proyecto.agregar(actividad("y", 3, ["x"]))
        proyecto.agregar(actividad("z", 1, ["y"]))
        cpm = calcular_cpm(proyecto)
        self.assertEqual(cpm["duracion"], 6)
        self.assertEqual(len(cpm["actividades_criticas"]), 3)

    def test_holgura_libre(self) -> None:
        proyecto = red_base()
        # F depende de A y termina antes del fin del proyecto: su holgura libre
        # es 12 - 5 = 7 dias.
        proyecto.agregar(actividad("f", 2, ["a"]))
        cpm = calcular_cpm(proyecto)
        fila = next(f for f in cpm["filas"] if f["id"] == "f")
        self.assertAlmostEqual(fila["ef"], 5.0)
        self.assertAlmostEqual(fila["holgura"], 7.0)
        self.assertAlmostEqual(fila["holgura_libre"], 7.0)

    def test_ciclo_detectado(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(actividad("a", 1, ["c"]))
        proyecto.agregar(actividad("b", 1, ["a"]))
        proyecto.agregar(actividad("c", 1, ["b"]))
        with self.assertRaises(CicloError):
            orden_topologico(proyecto)
        with self.assertRaises(CicloError):
            calcular_cpm(proyecto)

    def test_predecesora_inexistente_se_ignora_sin_romper(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(actividad("a", 2, ["no_existe"]))
        cpm = calcular_cpm(proyecto)
        self.assertEqual(cpm["duracion"], 2)
        self.assertEqual(cpm["ruta_critica"], ["a"])

    def test_actividad_paralela_no_extiende_el_proyecto(self) -> None:
        proyecto = red_base()
        proyecto.agregar(actividad("g", 20, ["a"]))
        cpm = calcular_cpm(proyecto)
        self.assertEqual(cpm["duracion"], 23)
        self.assertIn("g", cpm["actividades_criticas"])
        self.assertNotIn("e", cpm["actividades_criticas"])


class TestPERT(unittest.TestCase):
    def test_tiempo_esperado_y_varianza(self) -> None:
        actividad_pert = Actividad(
            id="a", nombre="A", optimista=2, probable=4, pesimista=12
        )
        self.assertAlmostEqual(actividad_pert.te, (2 + 16 + 12) / 6)
        self.assertAlmostEqual(actividad_pert.varianza, ((12 - 2) / 6) ** 2)
        self.assertAlmostEqual(actividad_pert.sigma, math.sqrt(100 / 36))

    def test_varianza_solo_de_la_ruta_critica(self) -> None:
        proyecto = Proyecto()
        # Dos ramas en paralelo: la ruta A->D es la mas larga; la varianza de
        # B no debe sumarse a sigma del proyecto.
        proyecto.agregar(Actividad("a", "A", optimista=1, probable=2, pesimista=3))
        proyecto.agregar(Actividad("b", "B", optimista=1, probable=1, pesimista=2))
        proyecto.agregar(
            Actividad("d", "D", predecesoras=["a", "b"],
                      optimista=4, probable=5, pesimista=6)
        )
        cpm = calcular_cpm(proyecto)
        var_esperada = ((3 - 1) / 6) ** 2 + ((6 - 4) / 6) ** 2
        # El motor redondea la varianza a 4 decimales para presentacion.
        self.assertAlmostEqual(cpm["varianza"], var_esperada, places=4)
        self.assertNotAlmostEqual(cpm["varianza"], var_esperada + ((2 - 1) / 6) ** 2, places=4)

    def test_probabilidad_normal(self) -> None:
        cpm = {"duracion": 100.0, "sigma": 10.0}
        self.assertAlmostEqual(probabilidad_exito(cpm, 100)["probabilidad"], 0.5, places=4)
        self.assertAlmostEqual(probabilidad_exito(cpm, 110)["probabilidad"], 0.8413, places=3)
        self.assertAlmostEqual(probabilidad_exito(cpm, 90)["probabilidad"], 0.1587, places=3)

    def test_plazo_para_probabilidad(self) -> None:
        cpm = {"duracion": 100.0, "sigma": 10.0}
        plazo = plazo_para_probabilidad(cpm, 0.8413)
        self.assertAlmostEqual(plazo, 110.0, delta=0.2)
        self.assertAlmostEqual(
            probabilidad_exito(cpm, plazo)["probabilidad"], 0.8413, places=3
        )

    def test_sigma_cero(self) -> None:
        cpm = {"duracion": 10.0, "sigma": 0.0}
        self.assertEqual(probabilidad_exito(cpm, 10)["probabilidad"], 1.0)
        self.assertEqual(probabilidad_exito(cpm, 9)["probabilidad"], 0.0)


class TestFlujoYSimulacion(unittest.TestCase):
    def test_flujo_reconcilia_con_presupuesto(self) -> None:
        proyecto = red_base()
        cpm = calcular_cpm(proyecto)
        detalle = [
            {"id": "a", "subtotal": 100.0},
            {"id": "b", "subtotal": 50.5},
            {"id": "c", "subtotal": 200.0},
            {"id": "d", "subtotal": 75.25},
            {"id": "e", "subtotal": 10.0},
        ]
        flujo = flujo_caja(cpm, detalle, administrativos=25.0)
        self.assertAlmostEqual(flujo[-1]["acumulado"], 460.75, delta=0.05)
        self.assertAlmostEqual(
            sum(semana["costo"] for semana in flujo), 460.75, delta=0.05
        )

    def test_duracion_fraccionaria_no_duplica_costo(self) -> None:
        proyecto = Proyecto()
        proyecto.agregar(
            Actividad("a", "A", optimista=1, probable=2, pesimista=4)
        )  # te = 2.1667
        cpm = calcular_cpm(proyecto)
        flujo = flujo_caja(cpm, [{"id": "a", "subtotal": 100.0}])
        self.assertAlmostEqual(flujo[-1]["acumulado"], 100.0, delta=0.02)

    def test_simulacion_acorta_tiempo_esperado(self) -> None:
        proyecto = red_base()
        original = calcular_cpm(proyecto)["duracion"]
        simulado = simular_reduccion(proyecto, {"a": 2})
        nuevo = calcular_cpm(simulado)["duracion"]
        self.assertAlmostEqual(nuevo, original - 2, places=2)


if __name__ == "__main__":
    unittest.main()
