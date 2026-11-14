# Segunda etapa de perfeccionamiento

Fecha: 2026-11-13
Base: codigo existente de ECUAPROJECT (no se reconstruyo el sistema ni se
cambiaron los nombres de dominio). Se conservaron las 54 pruebas originales y se
ampliaron a 81.

## 1. Costos cantonales

**Problema.** El selector permitia elegir Ambato, Quito o Guayaquil, pero el
presupuesto aplicaba el mismo costo del catalogo: `tasas_cantonales` existia en
`parametros_ley.json` y no se usaba.

**Correccion.**

- Nuevo `core/costos_cantonales.py` con `resolver_tarifa`, `resumen_canton`,
  `datos_canton` y `lista_cantones`.
- `Actividad` incorpora `nivel` y `canton`; `Actividad.desde_catalogo` los toma
  del catalogo y el copiloto los completa desde el ID.
- `Proyecto.resumen_costos` resuelve la tarifa del canton y la pasa a
  `Actividad.costo_efectivo`, que evita sumar de nuevo componentes por m2 o por
  tamano de empresa cuando ya aplica una tarifa municipal.
- Se aplican tarifas propias a uso de suelo, patente, bomberos y construccion por
  m2. Los tramites municipales sin tarifa especifica conservan el costo de
  referencia y se marcan como tales.
- Si el canton no tiene tarifario, falta el area o el tramite no tiene tarifa, se
  devuelve una advertencia; no se extrapolan valores entre ciudades.
- La interfaz muestra el tarifario del canton en la barra lateral y la
  trazabilidad de cada tasa en Presupuesto; el Excel y el PDF incluyen esa
  trazabilidad.

## 2. Dependencias entre actividades

**Problema.** Al calcular, cargar un JSON o aplicar un plan, las predecesoras que
no existian se eliminaban en silencio. Eso podia cambiar la ruta critica y
ocultar un error de digitacion.

**Correccion.**

- `calcular_cpm` ya no llama a `reindexar_predecesoras` ni modifica el proyecto;
  devuelve `dependencias_huerfanas`.
- `Proyecto.from_dict` conserva todas las referencias; se agregan
  `dependencias_huerfanas()` y `limpiar_predecesoras_huerfanas()` (esta ultima
  solo si el usuario lo decide).
- `proyecto_desde_dataframe` y `copiloto_ia.aplicar_plan` conservan las
  referencias desconocidas.
- El validador emite `predecesora_inexistente` con un mensaje que explica que la
  dependencia se conservo. La pestana Actividades la lista en un panel aparte.
- Los ciclos se siguen detectando con el orden topologico (Kahn).

## 3. Auditoria del catalogo normativo

**Problema.** `verificar: false` se usaba incluso en tramites cantonales y varios
valores solo tenian el enlace a la pagina principal de la institucion,
presentandose como verificados.

**Correccion.**

- Cada uno de los 30 tramites declara `valor_tipo` (`oficial`, `estimacion`,
  `rango`, `mercado`), `fuente_tipo` (`portal_institucional` o `directa`) y
  `verificado_en`.
- 18 tramites con monto quedan marcados como estimacion y `verificar: true`; no
  se presenta una tarifa como oficial si solo existe el portal.
- Los tramites sin costo directo se mantienen como oficiales (el hecho
  verificado es que no generan tasa).
- Los tramites cantonales ya no declaran una entidad unica Ambato/Quito/Guayaquil.
- Fichas, validacion e informes muestran el tipo de valor y la fecha de revision.

**Limite.** No se contrasto cada ordenanza municipal individual. Se corrigio la
clasificacion para no afirmar mas de lo comprobado; queda pendiente incorporar el
enlace directo al tarifario de cada GAD.

## 4. Red CPM y Gantt

**Problema.** La red usaba una columna por nivel topologico y nodos sin carriles:
con actividades paralelas se superponian. El Gantt mostraba todos los nombres y
se volvia ilegible con muchas filas.

**Correccion.**

- Red con dos disposiciones: `tiempo` (eje en dias, carril distinto cuando dos
  actividades se solapan) y `dependencia` (niveles con orden por barycenter).
- Leyendas separadas para actividad privada, tramite publico y ruta critica;
  anillo exterior ademas del color para no depender solo del rojo.
- Etiquetas de codigo, tooltip con nombre, ES/EF, duracion, holgura y
  predecesoras; aristas criticas resaltadas solo si pertenecen a la ruta.
- Gantt con nombres truncados solo cuando hay muchas filas, orden estable,
  tooltip con LS/LF, leyenda por tipo y ruta critica, y linea de fin esperado.

## 5. Seguridad

**Problema.** `unsafe_allow_html=True` interpolaba nombres, mensajes y enlaces sin
escapar; el JSON de usuario se cargaba sin validar tipos ni limites.

**Correccion.**

- Nuevo `core/seguridad.py`: `escapar`, `url_segura` (solo http/https, sin
  credenciales ni caracteres de control), `cargar_json_bytes` (2 MB, UTF-8,
  profundidad maxima, rechazo de NaN/Infinity) y `validar_proyecto_json`
  (esquema, ids, duplicados, rangos, maximo de actividades y predecesoras).
- Todos los helpers de `ui/estilos.py` escapan el texto; los componentes y
  `app.py` escapan nombres, mensajes, IDs y URLs.
- La carga de proyecto valida antes de construir el modelo y muestra el error sin
  tumbar la aplicacion.
- El nombre del archivo descargado se sanea.

## 6. Copiloto de IA

**Correccion.**

- `conversar` devuelve `modo`: `api`, `local` o `respaldo_local`. La interfaz
  muestra el origen de cada respuesta, de modo que un plan simulado nunca se
  presenta como respuesta real de la API.
- `_clasificar_error` traduce 401/403, 404, 429, timeout, falta de `requests` y
  JSON invalido a mensajes accionables; el detalle tecnico se recorta.
- `probar_conexion` hace una llamada minima de verificacion (modelo en Gemini,
  lista de modelos en OpenAI) y nunca lanza excepciones.
- La respuesta del modelo se normaliza (`_normalizar_respuesta_ia`): tipos,
  limites y proyecto; un tramite con ID fuera del catalogo se degrada a actividad
  privada en lugar de presupuestarse como tasa publica.
- La clave nunca se devuelve a la interfaz: solo `clave_configurada`.

**Limite.** La llamada real a Gemini/OpenAI no se ejecuto porque no hay clave en
el entorno. El modo local, el contrato JSON, la clasificacion de errores y la
aprobacion estan cubiertos por pruebas.

## 7. Identidad visual

- Paleta sobria conservada y unificada; tipografia con numeros tabulares y fuente
  monoespaciada para IDs y etiquetas.
- Encabezado con marca, titulo y contexto; franja de metadatos del proyecto.
- Secciones con marca lateral discreta; metricas sin sombras ni degradados.
- Pestanas, tablas, formularios, expanders y chat con bordes finos y espaciado
  consistente.
- Se eliminaron emojis decorativos y el aviso de obsolescencia de
  `use_container_width` (migracion a `width="stretch"`).

## 8. Persistencia y session_state

- `nuevo_proyecto_sesion` reemplaza el proyecto, incrementa `_proyecto_revision`
  y limpia el plan pendiente.
- Los editores usan una clave por revision, de modo que cargar otro proyecto no
  reutiliza el estado del editor anterior.
- El editor del plan usa una clave derivada del conjunto de IDs.
- La carga de JSON calcula una huella SHA-256 para evitar el bucle de reruns.
- El escenario se guarda con el proyecto y se restaura al cargar.

## 9. Motores CPM/PERT

No se cambiaron las formulas. Se verifico que:

- `te`, varianza y sigma siguen igual;
- ES/EF/LS/LF, holgura total y libre conservan los valores resueltos a mano;
- la ruta critica de mayor varianza sigue siendo la usada para sigma;
- el motor ya no muta el grafo al calcular.
- La simulacion de aceleracion conserva `0 <= a <= m <= b`.

## 10. Informes

- Excel: resumen con canton, hoja de cronograma con grafico de barras apiladas,
  formatos numericos, suma del detalle y diferencia de conciliacion, y fuentes
  con origen del costo y fecha de revision.
- PDF: tablero de indicadores, tabla de probabilidad, Gantt vectorial con
  leyenda, presupuesto, trazabilidad de tasas cantonales, fuentes con tipo de
  valor, observaciones y pie con numeracion de paginas.
- Los datos exportados provienen del mismo `cpm`, `costos` y `flujo` que muestra
  la aplicacion; no se recalculan dentro del exportador.

## 11. Verificacion ejecutada

```text
python -m unittest discover -s tests
Ran 81 tests ... OK

python -m py_compile app.py core/*.py services/*.py ui/*.py
sin errores

AppTest(app.py)
0 excepciones · 5 pestanas · 16 metricas · 0 errores visibles
1 advertencia esperada (probabilidad entre 50% y 80%)

Streamlit real
streamlit run app.py --server.port 8599
/_stcore/health -> ok
GET / -> 200
proceso detenido y puerto liberado
```

Proyecto de ejemplo con Ambato y 300 m2:

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
| Tramites y tasas | USD 1.812,00 |
| IVA | USD 0,00 |
| Total | USD 43.155,27 |
| Ultimo acumulado del flujo | USD 43.155,27 (diferencia 0,00) |

El cambio de tramites (922 -> 1.812) se explica por la tasa de construccion por
m2 del canton (3,50 x 300 = 1.050) y por dejar de usar un unico valor nacional
para bomberos (15 en Ambato en lugar de 25).

## 12. Pruebas agregadas

- `tests/test_costos_cantonales.py`: tarifas por canton, construccion por m2,
  ausencia de area, canton desconocido, trazabilidad en el presupuesto y
  metadatos del catalogo.
- `tests/test_persistencia_seguridad.py`: CPM sin mutaciones, dependencias
  conservadas al cargar/editar/aplicar, round-trip a disco, limpieza explicita,
  escapado HTML, URLs peligrosas, limites de tamano, NaN, ids invalidos,
  duplicados, rangos numericos y esquema del escenario.

## 13. Pendientes reales

1. Verificar cada tarifa municipal contra la ordenanza y el tarifario del GAD;
   hoy son referencias declaradas como tales.
2. Incorporar enlaces directos al documento de cada tasa cuando esten
   disponibles; el catalogo ya distingue `portal_institucional` de `directa`.
3. Ejecutar el copiloto con claves reales de Gemini y OpenAI para validar cuotas,
   modelos y latencia; el contrato y el respaldo local ya estan probados.
4. Monte Carlo para proyectos con rutas casi criticas en paralelo.
5. Persistencia multiusuario (base de datos y autenticacion) si se despliega.
