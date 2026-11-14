# ECUAPROJECT

Sistema de planificacion y presupuestacion de proyectos con motor CPM/PERT,
catalogo normativo ecuatoriano y copiloto de IA con aprobacion humana.

La aplicacion permite describir un proyecto en lenguaje natural, recibir una
propuesta de actividades y tramites, editarla, y obtener ruta critica, holguras,
diagrama de red, Gantt, probabilidad de cumplir un plazo, presupuesto por
naturaleza del costo e informes en Excel y PDF.

## Requisitos e instalacion

Python 3.10 o superior y Streamlit 1.49 o superior (la interfaz usa `width="stretch"`,
que reemplaza al obsoleto `use_container_width`).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

La aplicacion abre en `http://localhost:8501`.

### Copiloto con IA (opcional)

Sin clave la aplicacion funciona completa en modo local: usa plantillas y el
catalogo normativo, sin inventar tramites. Para activar la entrevista
conversacional configure `GEMINI_API_KEY` u `OPENAI_API_KEY`, por variable de
entorno o en `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "..."
# AI_PROVIDER = "gemini"    # auto | gemini | openai | local
# AI_MODEL = "..."
```

El prompt incluye el catalogo como contexto y prohibe inventar tramites o
tasas. La respuesta se interpreta como JSON, se normaliza (tiempos, costos,
ids) y **nunca se aplica automaticamente**: la interfaz muestra una tabla
editable y exige el boton *Aprobar e incorporar plan*. Todos los calculos se
ejecutan despues con el motor matematico.

## Flujo de uso

1. **Definicion.** Nombre, descripcion y entrevista con el copiloto. Tambien
   existe un planificador local que arma un plan base con el catalogo.
2. **Actividades.** Tabla editable con PERT (`a / m / b`), costos directos,
   equipos, trabajadores y costo diario. Validacion de ciclos, dependencias,
   tiempos, salarios bajo el SBU y reglas legales.
3. **Cronograma.** ES/EF/LS/LF, holguras total y libre, ruta critica, red y
   Gantt calculados desde el grafo.
4. **Riesgo y plazo.** `Z`, probabilidad normal de cumplimiento, plazo para una
   probabilidad objetivo y simulador de aceleracion sobre la ruta critica.
5. **Presupuesto.** Costos directos, equipos, mano de obra cargada, gastos
   administrativos, tramites, IVA y total; flujo de caja semanal conciliado con
   el presupuesto; fuentes normativas; exportacion Excel/PDF.

## Estructura

```text
app.py                       # aplicacion Streamlit y orquestacion del calculo
data/base_ecuador.json       # 30 tramites con predecesoras, PERT, costos y fuentes
data/parametros_ley.json     # SBU, IESS, IVA, costo empleador y tasas de referencia
core/modelo.py               # Actividad y Proyecto; clasificacion y calculo de costos
core/calculos_cpm_pert.py    # topologico, ES/EF/LS/LF, holguras, ruta, PERT, flujo
core/validador.py            # integridad del grafo, reglas legales y catalogo
core/costos_cantonales.py    # tarifas por canton y advertencias de verificacion
core/seguridad.py            # escapado HTML, URLs y validacion del JSON de usuario
services/copiloto_ia.py      # Gemini/OpenAI + planificador local + normalizacion
services/exportador.py       # Excel (openpyxl) y PDF con Gantt (reportlab)
ui/estilos.py                # paleta, tipografia y CSS compartido
ui/componentes.py            # navegacion lateral, chat, tablas, catalogo, JSON
ui/graficos.py               # red, Gantt, campana normal y flujo de caja (Plotly)
tests/                       # 81 pruebas unitarias con unittest
```

## Modelo matematico

- Tiempo esperado: `te = (a + 4m + b) / 6`
- Varianza: `sigma^2 = ((b - a) / 6)^2`
- Pasada hacia adelante: `ES = max(EF de predecesoras)`, `EF = ES + te`
- Pasada hacia atras: `LF = min(LS de sucesoras)`, `LS = LF - te`
- Holgura total: `HT = LS - ES`; holgura libre: `HL = min(ES sucesoras) - EF`
- Ruta critica: actividades con `HT = 0`. Si hay varias, se reporta la de
  mayor varianza y `sigma^2` se calcula solo con esa ruta (sumar todas las
  actividades criticas sobreestima la desviacion).
- Probabilidad: `Z = (plazo - Te) / sigma`, `P = Phi(Z)`.

**Supuestos PERT.** Duraciones independientes, media y varianza segun las
formulas anteriores, y duracion del proyecto aproximada por una normal sobre la
ruta critica (teorema central del limite). La aproximacion pierde precision con
rutas casi criticas en paralelo o actividades correlacionadas; para esos casos
el propio informe lo advierte y se recomienda Monte Carlo.

## Presupuesto

El presupuesto separa partidas y evita duplicaciones:

```text
inversion privada = costos directos + equipos + mano de obra cargada + administrativos
base              = inversion privada + tramites y tasas
total             = base + IVA (solo sobre la inversion privada)
```

- La mano de obra usa el factor de costo empleador calculado desde sus
  componentes en `parametros_ley.json`, no un valor fijo desconectado.
- Los gastos administrativos son un porcentaje editable sobre los costos
  directos privados; no se aplican a tasas publicas.
- El IVA no se aplica a tramites ni tasas publicas.
- Las tasas municipales se resuelven por canton: uso de suelo, patente,
  bomberos y construccion por m2 usan el tarifario del GAD seleccionado. Si el
  canton no tiene datos o falta el area, se conserva el costo de referencia del
  catalogo y se muestra una advertencia; nunca se copian valores entre ciudades.
- El flujo de caja distribuye cada actividad por solapamiento diario y
  prorratea los gastos administrativos, de modo que su total coincide con el
  presupuesto.

## Datos normativos verificados

Consultados y contrastados el 2026-11-13:

| Parametro | Valor | Fuente |
|---|---|---|
| SBU 2026 | USD 482.00 | Acuerdo Ministerial MDT-2025-195 (15-dic-2025; R.O. Suplemento 187, 18-dic-2025) |
| Aporte patronal IESS | 11.15% | Resolucion C.D. 501, texto C.D. 515 |
| Aporte personal IESS | 9.45% | Resolucion C.D. 501, texto C.D. 515 |
| Fondos de reserva | 8.33% | IESS |
| IECE + SECAP | 1.00% | IESS |
| IVA general | 15% | SRI Circular NAC-DGECCGC25-00000006 (26-dic-2025) |

El catalogo incluye SRI, Supercias, IESS, Ministerio del Trabajo, ARCSA, MAATE,
SENADI, GAD municipales, Cuerpos de Bomberos y servicios basicos. Cada registro
tiene entidad, normativa, URL, fecha de revision y dos campos que evitan
confundir un dato con una estimacion:

- `valor_tipo`: `oficial`, `estimacion`, `rango` o `mercado`.
- `fuente_tipo`: `directa` o `portal_institucional`.

Un monto solo se marca como oficial si existe una fuente directa del valor. Si
solo se dispone del portal institucional, queda como estimacion y la interfaz,
la validacion y los informes lo advierten.

**Limite explicito:** las tasas municipales, de bomberos y sectoriales son
referencias de ordenanza; no se verificaron una por una contra cada GAD. La
interfaz y los informes muestran la advertencia y la fuente para que el usuario
confirme el valor vigente. La herramienta no sustituye asesoria legal.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las **81 pruebas** cubren ES/EF/LS/LF con valores resueltos a mano, actividades
paralelas, multiples predecesoras, holgura libre, ciclos, PERT y probabilidad
normal, varianza por ruta, conciliacion del flujo, presupuesto sin
duplicaciones, descuentos ARCSA/PYME, reglas legales, planes del copiloto,
exportadores y graficos. La segunda etapa agrega pruebas de tarifas por canton,
dependencias inexistentes conservadas, carga segura de JSON, escapado de HTML,
URLs peligrosas y persistencia.

## Estado y pendientes

Ver `docs/AUDITORIA.md` para la primera etapa y `docs/INFORME_ETAPA2.md` para la
segunda (tarifas cantonales, seguridad, dependencias, graficos y pruebas).
Pendientes principales: verificar cada ordenanza municipal contra su tarifario,
Monte Carlo, autenticacion multiusuario y persistencia en base de datos.

## Limpieza del entregable

El proyecto no versiona entornos, caches ni salidas. Antes de comprimirlo:

```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
rm -rf .tools .venv informes
```

`.tools/` es un interprete portable local excluido por `.gitignore`; no debe
incluirse en la entrega. Solo se necesita `requirements.txt` para reproducir el
entorno en otra computadora.
