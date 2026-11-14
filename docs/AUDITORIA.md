# Auditoria tecnica de ECUAPROJECT (primera etapa)

> Este documento conserva el registro de la primera etapa. La segunda etapa
> (tarifas cantonales, dependencias conservadas, seguridad, red/Gantt y pruebas
> ampliadas) esta en `docs/INFORME_ETAPA2.md`. La suite paso de 54 a 81 pruebas.

Fecha de revision: 2026-11-13
Alcance: codigo existente (aprox. 2.700 lineas antes de la intervencion),
catalogo normativo, motor CPM/PERT, presupuesto, copiloto, interfaz e informes.
No se reemplazo el proyecto ni se cambiaron sus nombres de dominio: se corrigio
y amplio lo que ya existia.

## 1. Metodo

1. Lectura completa de `app.py`, `core/`, `services/`, `ui/` y `data/`.
2. Reproduccion de los calculos con un proyecto de 34 actividades y 18 tramites
   (ejemplo "galpon de muebles"): se compararon resultados a mano, se reviso la
   conciliacion del flujo de caja y se ejecutaron las vistas con `AppTest`.
3. Contraste de los parametros legales contra fuentes oficiales (SBU, IESS,
   IVA) y revision del catalogo de tramites.
4. Correccion por etapas y creacion de una suite de regresion con `unittest`.

## 2. Hallazgos corregidos

| # | Severidad | Hallazgo | Correccion |
|---|---|---|---|
| 1 | Alta | El flujo de caja no cuadraba con el presupuesto: USD 39.800,35 frente a USD 40.037,78. | Se distribuyen los gastos administrativos y el solapamiento diario; el ultimo acumulado coincide con la base. |
| 2 | Alta | La varianza PERT sumaba todas las actividades con holgura cero, sobreestimando sigma cuando hay rutas criticas en paralelo. | Se elige la ruta critica de mayor varianza y sigma se calcula solo con ella. |
| 3 | Alta | La regla legal omitia el requisito cuando el tramite no existia en el proyecto, en lugar de reportarlo. | `validador` emite ERROR por requisito ausente y distingue tramite fuera de catalogo. |
| 4 | Alta | El factor de mano de obra era 1,3357 fijo, sin relacion con los componentes legales. | Se calcula desde `costo_empleador.componentes`: 41,31% -> 1,4131, con nota del supuesto del decimo cuarto. |
| 5 | Media | El presupuesto mezclaba inversion privada, tasas publicas e IVA; el IVA podia aplicarse a tramites. | Separacion `directos + equipos + mano de obra + administrativos`, luego tramites, y IVA solo sobre la inversion privada. |
| 6 | Media | Faltaba la categoria de equipos y el desglose de mano de obra en el resumen. | Campos `costo_equipos` y desglose `directos/equipos/mano_obra_incluida/privada/base/iva/total`. |
| 7 | Media | El simulador recortaba `m` sin mantener la relacion PERT y podia producir `a > m > b`. | Reduce `te` y escala `a`, `m` y `b` proporcionalmente; la holgura se recalcula. |
| 8 | Media | La persistencia en JSON podia entrar en bucle de reruns y perder el proyecto. | Guardado con huella (`hashlib`) y bandera de carga; sin `st.rerun` circular. |
| 9 | Media | `st.stop()` dentro de pestañas cortaba la aplicacion completa ante un error de datos. | Validacion y mensajes por seccion; el resto de pestañas sigue disponible. |
| 10 | Media | El copiloto añadia dos veces el mensaje del usuario al historial enviado al LLM. | Historial normalizado una sola vez antes de la llamada. |
| 11 | Media | El plan de IA se aplicaba sin revision humana y sin normalizar tiempos ni costos. | Tabla editable + boton *Aprobar e incorporar plan*; normalizacion de `a/m/b`, costos e ids. |
| 12 | Media | Los informes no incluian ruta critica, probabilidad ni observaciones, y el PDF no tenia Gantt. | Excel de 7 hojas y PDF con tabla CPM, Gantt vectorial, presupuesto, fuentes y observaciones. |
| 13 | Baja | SBU 2026 desactualizado (470) y IVA sin fecha de vigencia. | SBU 482 y IVA 15% con fuente y fecha de verificacion. |
| 14 | Baja | Emojis decorativos, degradados y tarjetas excesivas en la interfaz. | Paleta sobria, tipografia y componentes discretos en `ui/estilos.py` y `.streamlit/config.toml`. |
| 15 | Baja | Sin pruebas automatizadas. | 54 pruebas `unittest` de CPM/PERT, presupuesto, validador, copiloto e informes. |

## 3. Archivos modificados

- `app.py`: orquestacion, calculo unico, cinco pestañas, presupuesto por
  categorias, exportaciones y conciliacion del flujo.
- `core/modelo.py`: dominio, clasificacion de costos, factor de cargas y
  `resumen_costos`.
- `core/calculos_cpm_pert.py`: topologico, ES/EF/LS/LF, holgura libre, ruta
  critica ponderada, PERT, flujo y simulador.
- `core/validador.py`: integridad del grafo, autodependencias, costos, salario
  bajo SBU, catalogo y reglas legales.
- `services/copiloto_ia.py`: Gemini/OpenAI, planificador local, normalizacion y
  aprobacion del plan.
- `services/exportador.py`: Excel y PDF completos.
- `ui/estilos.py` (nuevo), `ui/componentes.py`, `ui/graficos.py`: identidad,
  navegacion, tablas, catalogo, red, Gantt, campana y flujo.
- `data/parametros_ley.json` (v2026.2) y `data/base_ecuador.json` (v2026.2,
  30 tramites).
- `.streamlit/config.toml` (nuevo): tema.
- `README.md` y este documento.
- `tests/` (nuevo): `test_cpm_pert.py`, `test_presupuesto.py`,
  `test_validador_copiloto.py`, `test_informes.py`.

## 4. Verificacion ejecutada

```bash
python -m unittest discover -s tests -v
# Ran 54 tests ... OK

python -m py_compile app.py core/*.py services/*.py ui/*.py
# sin errores
```

`AppTest` sobre `app.py`: 0 excepciones, 5 pestañas (Definicion, Actividades,
Cronograma, Riesgo y plazo, Presupuesto), 16 metricas, 0 errores mostrados y 1
advertencia de datos.

Proyecto de ejemplo, resultados comprobados:

| Concepto | Valor |
|---|---|
| Actividades / tramites | 34 / 18 |
| Duracion esperada | 94,83 dias |
| Sigma | 6,5807 |
| Actividades criticas | 11 |
| Costos directos | USD 34.650,00 |
| Equipos | USD 0,00 |
| Mano de obra cargada | USD 4.724,54 |
| Administrativos (5%) | USD 1.968,73 |
| Inversion privada | USD 41.343,27 |
| Tramites y tasas | USD 922,00 |
| IVA | USD 0,00 |
| Total | USD 42.265,27 |
| Ultimo acumulado del flujo | USD 42.265,27 (coincide con la base) |

Las pruebas cubren valores CPM resueltos a mano (incluidas actividades
paralelas y multiples predecesoras), deteccion de ciclos, formulas PERT,
probabilidad normal y su inversa, presupuesto sin duplicaciones, descuentos
ARCSA/PYME, reglas legales, planes del copiloto, exportadores y graficos.

## 5. Supuestos y decisiones

- Duraciones PERT independientes y proyecto normal sobre la ruta critica; se
  advierte la limitacion con rutas casi criticas.
- Gastos administrativos: 5% editable sobre costos directos privados, no es una
  tasa legal.
- Decimo cuarto estimado como 1 SBU/12 sobre un sueldo de referencia igual al
  SBU; el factor baja para sueldos mayores.
- IVA solo sobre inversion privada; los tramites y tasas publicas no lo llevan.
- `unittest` de la biblioteca estandar para no agregar dependencias.

## 6. Limites y pendientes

1. **Tasas municipales y de bomberos:** son referencias de ordenanza
   (`verificar: true`); no se validaron una por una contra cada GAD. La interfaz
   y los informes lo advierten.
2. **Copiloto con IA:** el modo local esta probado; la llamada real a Gemini u
   OpenAI no se ejecuto por no disponer de clave. El contrato JSON, la
   normalizacion y la aprobacion si estan cubiertos por pruebas.
3. **PERT vs. Monte Carlo:** no se implemento simulacion Monte Carlo; queda como
   mejora para proyectos con rutas en paralelo de duracion similar.
4. **Persistencia:** el estado vive en `session_state` y en JSON local; no hay
   base de datos ni autenticacion multiusuario.
5. **Graficos en los informes:** el PDF incluye el Gantt; la red, la campana y
   el flujo se consultan en pantalla, y el Excel contiene los datos tabulares
   que los respaldan, no las figuras.
6. **Aviso de Streamlit:** resuelto en la segunda etapa. La interfaz usa
   `width="stretch"` y `requirements.txt` exige Streamlit 1.49 o superior, por lo
   que ya no aparece el aviso de `use_container_width`.
