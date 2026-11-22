# Plan de mejora de ECUAPROJECT

## 1. Diagnóstico frente al lineamiento

### Fortalezas actuales

- El motor CPM/PERT calcula tiempos esperados, varianzas, holguras y ruta crítica.
- La aplicación permite editar actividades, validar ciclos y conservar dependencias.
- Existen exportaciones a JSON, Excel y PDF, además de gráficos de red, Gantt y flujo de caja.
- Se dispone de pruebas automatizadas para cálculo, presupuesto, validación y exportación.

### Brechas prioritarias

1. **Informe académico incompleto.** El PDF actual es un informe ejecutivo apaisado; no contiene portada académica, resumen de 200 palabras, introducción, objetivos, marco teórico, metodología, desarrollo manual, resultados comparativos, conclusiones, recomendaciones, referencias y anexos en el orden exigido.
2. **Falta de trazabilidad experimental.** La aplicación calcula casos, pero no guía al usuario para registrar tres casos de prueba, incluido un caso límite, ni compara de forma explícita el cálculo manual con el resultado del software.
3. **Descarga fragmentada.** El usuario descarga archivos separados y no recibe un paquete completo con el proyecto, datos, resultados, informe y carta de presentación.
4. **Flujo poco guiado.** Las pestañas son funcionales, pero no muestran claramente el avance del trabajo ni qué requisito académico falta completar.
5. **Presentación orientada a operación, no a defensa.** Faltan un panel ejecutivo, una vista de evidencia para exposición y una ruta de demostración en vivo.
6. **Contenido de ejemplo desalineado.** El ejemplo de galpón es válido para CPM/PERT, pero debe existir también una plantilla de ciclo de vida de software para alinearse directamente con la carrera y el lineamiento.

## 2. Objetivo de la mejora

Convertir ECUAPROJECT en una herramienta de planificación CPM/PERT que produzca simultáneamente:

- un proyecto matemáticamente verificable;
- un flujo de trabajo guiado para completar los siete pasos prácticos;
- un informe académico compatible con las 12 secciones del lineamiento;
- un paquete descargable reproducible;
- una vista ejecutiva clara para la exposición de 15 minutos.

## 3. Rediseño de experiencia de usuario

### Navegación propuesta

1. **Inicio y proyecto**
   - Nombre, tema, unidad del sílabo, equipo, docente y fecha.
   - Selector de plantilla: ciclo de vida de software, despliegue de sistema o proyecto libre.
   - Indicador de avance académico.

2. **Planteamiento**
   - Problema, contexto, datos, variables, supuestos y restricciones.
   - Lista de verificación del paso 1.

3. **Modelo PERT/CPM**
   - Actividades, predecesoras y parámetros `a`, `m`, `b`.
   - Diagrama de red y explicación de las fórmulas.

4. **Solución manual**
   - Tabla editable para `ES`, `EF`, `LS`, `LF`, holgura y ruta crítica.
   - Campos para registrar el procedimiento manual y observaciones.

5. **Casos y validación**
   - Tres casos mínimos con entrada, resultado esperado, resultado obtenido y diferencia.
   - Caso límite obligatorio con validación visual.

6. **Resultados**
   - KPIs, Gantt, red, probabilidad, presupuesto y contraste manual/software.

7. **Informe y entrega**
   - Vista previa de las 12 secciones.
   - Validación de completitud.
   - Descarga del paquete completo.

### Paneles inteligentes

- **Panel de avance:** porcentaje de secciones completas, pasos prácticos terminados y advertencias pendientes.
- **Panel de salud del modelo:** errores, advertencias, actividades críticas, dependencias huérfanas y datos faltantes.
- **Panel de decisión:** duración esperada, costo, probabilidad de plazo y principales actividades críticas.
- **Panel de evidencia:** captura consolidada de entradas, cálculos, resultados y comparación.
- **Panel de entrega:** checklist de archivos generados y estado de cada exportación.

### Criterios visuales

- Mantener una sola paleta, jerarquía tipográfica y componentes reutilizables.
- Usar estados consistentes: completado, pendiente, advertencia y error.
- Sustituir mensajes técnicos por lenguaje orientado a la tarea del estudiante.
- Mostrar acciones primarias únicas por pantalla: `Continuar`, `Validar`, `Calcular` o `Generar entrega`.
- Mantener los detalles técnicos dentro de paneles secundarios o ayuda contextual.

## 4. Mejoras de exportación y entrega

### Carta de presentación

Agregar una carta de presentación generada con:

- Universidad Técnica de Ambato.
- Facultad, carrera y asignatura.
- Título del proyecto.
- Integrantes, docente y fecha.
- Breve descripción del problema, modelo utilizado y archivos incluidos.
- Declaración de integridad académica y uso de IA.

La carta debe aparecer como primera página del PDF académico y como archivo independiente dentro del paquete.

### Informe académico

Crear un modo de exportación `Informe académico` con las 12 secciones obligatorias, en orientación vertical, con portada, numeración, tablas y anexos. El PDF ejecutivo actual debe conservarse como `Resumen ejecutivo`.

### Paquete descargable

El botón principal debe generar un ZIP con nombres seguros y consistentes:

```text
ECUAPROJECT_<proyecto>/
├── carta_presentacion.pdf
├── informe_academico.pdf
├── resumen_ejecutivo.pdf
├── resultados.xlsx
├── proyecto.json
├── casos_prueba.json
├── tabla_cpm_pert.csv
├── codigo_fuente/
└── README_entrega.txt
```

El paquete debe:

- usar el nombre del proyecto sanitizado;
- incluir todos los archivos aun cuando una exportación opcional falle, informando el archivo faltante;
- comprobar que el JSON descargado puede volver a cargarse;
- incluir fecha de generación y versión del esquema;
- evitar credenciales, claves de IA y secretos.

## 5. Cumplimiento de los siete pasos prácticos

Implementar un checklist persistente:

1. Planteamiento del problema.
2. Modelo matemático/técnico.
3. Solución manual.
4. Implementación informática.
5. Tres casos de prueba y caso límite.
6. Contrastación y validación.
7. Análisis crítico, limitaciones y mejoras.

El generador de informe no debe marcar una sección como completa si faltan sus datos mínimos. Las validaciones deben ser explícitas y no bloquear la edición del proyecto.

## 6. Plantillas académicas recomendadas

Agregar una plantilla principal para Software:

- levantamiento de requisitos;
- análisis y diseño;
- desarrollo;
- pruebas;
- despliegue;
- documentación y capacitación.

Esta plantilla permite demostrar el modelo PERT/CPM con un problema directamente relacionado con la carrera. Se conservarán las plantillas de construcción, negocio y proyecto libre como opciones adicionales.

## 7. Plan de ejecución por fases

### Fase 1 — Base de datos académica y flujo

- Crear modelo de metadatos académicos.
- Crear checklist de los siete pasos y las 12 secciones.
- Crear plantilla de ciclo de vida de software.
- Agregar panel de avance y panel de salud.

**Criterio de aceptación:** un proyecto nuevo puede identificar tema, unidad, equipo, caso límite y estado de cada requisito.

### Fase 2 — Casos experimentales y contrastación

- Crear editor de casos de prueba.
- Incluir caso base, caso ampliado y caso límite.
- Ejecutar cada caso con el motor CPM/PERT.
- Comparar resultado manual y software con tolerancia configurable.

**Criterio de aceptación:** el sistema no permite generar la entrega académica sin tres casos documentados y una comparación por caso.

### Fase 3 — Informe académico y carta

- Implementar las 12 secciones en el generador de PDF.
- Añadir portada y carta de presentación.
- Añadir referencias, declaración de IA y anexos.
- Numerar tablas, figuras y ecuaciones del informe.

**Criterio de aceptación:** el PDF se genera en el orden exigido, contiene las 12 secciones y muestra los datos del proyecto sin valores inventados.

### Fase 4 — Descarga reproducible

- Generar ZIP de entrega.
- Validar round-trip del JSON.
- Añadir manifest de archivos y versión.
- Informar errores parciales sin producir una descarga engañosa.

**Criterio de aceptación:** el ZIP contiene proyecto, informe, carta, resultados, casos y datos; el proyecto puede volver a cargarse.

### Fase 5 — Rediseño visual y presentación

- Reorganizar la navegación por etapas.
- Aplicar paneles inteligentes y estados uniformes.
- Crear vista `Modo exposición` con KPIs, ruta crítica y demostración sugerida.
- Revisar responsive, textos y consistencia visual.

**Criterio de aceptación:** un usuario nuevo puede completar el flujo sin conocer la estructura interna del código y puede demostrar un caso en menos de cinco minutos.

### Fase 6 — Validación final

- Ejecutar las pruebas unitarias existentes.
- Agregar pruebas para checklist, casos, carta, informe y ZIP.
- Probar carga de un proyecto descargado.
- Revisar manualmente el PDF contra el lineamiento.

## 8. Prioridad

1. Informe académico de 12 secciones y carta de presentación.
2. Paquete ZIP de entrega reproducible.
3. Casos de prueba y contrastación.
4. Plantilla de ciclo de vida de software.
5. Panel de avance y navegación por etapas.
6. Vista de exposición y refinamiento visual.

## 9. Resultado esperado

La versión mejorada no solo calculará una ruta crítica: acompañará al equipo desde el planteamiento hasta la defensa, conservará la evidencia del procedimiento manual, validará los casos experimentales y entregará un paquete académico completo, coherente y reutilizable.
