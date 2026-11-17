import type { TestCase } from '../types';

/**
 * Default test cases for the CPM engine.
 *
 * te formula: (a + 4m + b) / 6
 */
export const defaultTestCases: TestCase[] = [
  // ── Case 1: Simple Linear Network ──────────────────────────────────────────
  {
    id: 'tc-linear',
    name: 'Red Simple Lineal',
    description:
      '4 actividades secuenciales (A→B→C→D). Todas se encuentran en la ruta crítica.',
    isEdgeCase: false,
    activities: [
      // te = (2+16+6)/6 = 4
      { id: 'A', name: 'Actividad A', optimistic: 2, mostLikely: 4, pessimistic: 6, cost: 1000, predecessors: [] },
      // te = (3+20+7)/6 = 5
      { id: 'B', name: 'Actividad B', optimistic: 3, mostLikely: 5, pessimistic: 7, cost: 1500, predecessors: ['A'] },
      // te = (1+12+5)/6 = 3
      { id: 'C', name: 'Actividad C', optimistic: 1, mostLikely: 3, pessimistic: 5, cost: 800, predecessors: ['B'] },
      // te = (2+16+6)/6 = 4
      { id: 'D', name: 'Actividad D', optimistic: 2, mostLikely: 4, pessimistic: 6, cost: 1200, predecessors: ['C'] },
    ],
    expectedDuration: 16, // 4+5+3+4
    expectedCriticalPath: ['A', 'B', 'C', 'D'],
  },

  // ── Case 2: Parallel Paths ─────────────────────────────────────────────────
  {
    id: 'tc-parallel',
    name: 'Rutas Paralelas',
    description:
      '5 actividades con 2 rutas paralelas que convergen. Solo una ruta es crítica.',
    isEdgeCase: false,
    activities: [
      // te = 2
      { id: 'A', name: 'Inicio', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 500, predecessors: [] },
      // te = 6
      { id: 'B', name: 'Ruta Larga', optimistic: 4, mostLikely: 6, pessimistic: 8, cost: 2000, predecessors: ['A'] },
      // te = 2
      { id: 'C', name: 'Ruta Corta', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 800, predecessors: ['A'] },
      // te = 3
      { id: 'D', name: 'Convergencia', optimistic: 2, mostLikely: 3, pessimistic: 4, cost: 1200, predecessors: ['B', 'C'] },
      // te = 2
      { id: 'E', name: 'Cierre', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 600, predecessors: ['D'] },
    ],
    expectedDuration: 13, // A→B→D→E = 2+6+3+2
    expectedCriticalPath: ['A', 'B', 'D', 'E'],
  },

  // ── Case 3: Software Project (template copy) ──────────────────────────────
  {
    id: 'tc-software',
    name: 'Proyecto de Software',
    description:
      'Copia de la plantilla SDLC con 11 actividades, rutas paralelas frontend/backend y auditoría de seguridad.',
    isEdgeCase: false,
    activities: [
      { id: 'REQ', name: 'Análisis de Requisitos', optimistic: 3, mostLikely: 5, pessimistic: 9, cost: 2000, predecessors: [] },
      { id: 'DIS', name: 'Diseño de Arquitectura', optimistic: 2, mostLikely: 4, pessimistic: 7, cost: 3000, predecessors: ['REQ'] },
      { id: 'DB', name: 'Diseño de Base de Datos', optimistic: 1, mostLikely: 3, pessimistic: 5, cost: 1500, predecessors: ['REQ'] },
      { id: 'FRONT', name: 'Desarrollo Frontend', optimistic: 5, mostLikely: 8, pessimistic: 14, cost: 8000, predecessors: ['DIS'] },
      { id: 'BACK', name: 'Desarrollo Backend', optimistic: 4, mostLikely: 7, pessimistic: 12, cost: 7000, predecessors: ['DIS', 'DB'] },
      { id: 'API', name: 'Integración de APIs', optimistic: 2, mostLikely: 3, pessimistic: 6, cost: 2500, predecessors: ['BACK'] },
      { id: 'INT', name: 'Pruebas de Integración', optimistic: 2, mostLikely: 4, pessimistic: 7, cost: 2000, predecessors: ['FRONT', 'API'] },
      { id: 'SEC', name: 'Auditoría de Seguridad', optimistic: 1, mostLikely: 2, pessimistic: 4, cost: 3000, predecessors: ['BACK'] },
      { id: 'UAT', name: 'Pruebas de Aceptación', optimistic: 1, mostLikely: 3, pessimistic: 5, cost: 1500, predecessors: ['INT', 'SEC'] },
      { id: 'DEP', name: 'Despliegue a Producción', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 2000, predecessors: ['UAT'] },
      { id: 'MON', name: 'Monitoreo Post-Despliegue', optimistic: 1, mostLikely: 2, pessimistic: 4, cost: 1000, predecessors: ['DEP'] },
    ],
  },

  // ── Case 4: Edge Case — Near-Identical Path Durations ─────────────────────
  // Path 1: A → B → C → F        te = 2 + 8 + 5 + 2 = 17.00
  // Path 2: A → D → E → C → F    te = 2 + 3.83 + 4 + 5 + 2 = 16.83
  // Difference: 0.17 days (< 0.5) ✓
  {
    id: 'tc-edge-convergence',
    name: 'Caso Límite: Convergencia de Rutas',
    description:
      '6 actividades con dos rutas paralelas de duración casi idéntica (diferencia <0.5 días). Prueba la precisión del motor CPM.',
    isEdgeCase: true,
    activities: [
      // te = (1+8+3)/6 = 2
      { id: 'A', name: 'Inicio del Proyecto', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 500, predecessors: [] },
      // te = (6+32+10)/6 = 8
      { id: 'B', name: 'Ruta Directa', optimistic: 6, mostLikely: 8, pessimistic: 10, cost: 3000, predecessors: ['A'] },
      // te = (2+16+5)/6 = 23/6 ≈ 3.833
      { id: 'D', name: 'Fase Alternativa I', optimistic: 2, mostLikely: 4, pessimistic: 5, cost: 1800, predecessors: ['A'] },
      // te = (3+16+5)/6 = 4
      { id: 'E', name: 'Fase Alternativa II', optimistic: 3, mostLikely: 4, pessimistic: 5, cost: 2000, predecessors: ['D'] },
      // te = (3+20+7)/6 = 5
      { id: 'C', name: 'Integración Final', optimistic: 3, mostLikely: 5, pessimistic: 7, cost: 2500, predecessors: ['B', 'E'] },
      // te = (1+8+3)/6 = 2
      { id: 'F', name: 'Cierre y Entrega', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 800, predecessors: ['C'] },
    ],
    expectedDuration: 17, // Path 1 (critical): A→B→C→F = 2+8+5+2
    expectedCriticalPath: ['A', 'B', 'C', 'F'],
  },
];
