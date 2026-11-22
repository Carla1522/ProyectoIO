// ─── Project Health Validator ─────────────────────────────────────────────────
// Validador de salud e integridad del proyecto en lenguaje claro y accesible.

import type { Activity, HealthIssue, HealthSeverity } from '../types';

let issueCounter = 0;

/** Crea un registro de observación con un ID determinista. */
function issue(
  severity: HealthSeverity,
  message: string,
  affectedActivities?: string[],
): HealthIssue {
  return {
    id: `issue-${++issueCounter}`,
    severity,
    message,
    affectedActivities,
  };
}

// ─── Detección de Ciclos (DFS de 3 colores) ──────────────────────────────────

function detectCycles(activities: Activity[], idSet: Set<string>): HealthIssue[] {
  const issues: HealthIssue[] = [];

  const WHITE = 0; // No visitado
  const GRAY = 1;  // En la pila actual de recursión
  const BLACK = 2; // Totalmente explorado

  const color = new Map<string, number>();
  const adjList = new Map<string, string[]>();

  for (const act of activities) {
    color.set(act.id, WHITE);
    if (!adjList.has(act.id)) adjList.set(act.id, []);
    for (const pred of act.predecessors) {
      if (idSet.has(pred)) {
        if (!adjList.has(pred)) adjList.set(pred, []);
        adjList.get(pred)!.push(act.id);
      }
    }
  }

  const cycleMembers = new Set<string>();

  function dfs(node: string, stack: string[]): void {
    color.set(node, GRAY);
    stack.push(node);

    for (const neighbor of adjList.get(node) ?? []) {
      const c = color.get(neighbor);
      if (c === GRAY) {
        // Se encontró un ciclo: recolectar nodos participantes
        const cycleStart = stack.indexOf(neighbor);
        for (let i = cycleStart; i < stack.length; i++) {
          cycleMembers.add(stack[i]);
        }
      } else if (c === WHITE) {
        dfs(neighbor, stack);
      }
    }

    stack.pop();
    color.set(node, BLACK);
  }

  for (const act of activities) {
    if (color.get(act.id) === WHITE) {
      dfs(act.id, []);
    }
  }

  if (cycleMembers.size > 0) {
    issues.push(
      issue(
        'error',
        `Existe una dependencia circular o bucle infinito que involucra a: ${Array.from(cycleMembers).join(', ')}. Una tarea no puede requerir el término de otra que a su vez dependa de ella.`,
        Array.from(cycleMembers),
      ),
    );
  }

  return issues;
}

// ─── Validador Principal del Modelo ──────────────────────────────────────────

/**
 * Revisa el proyecto y genera alertas comprensibles para el usuario.
 * Detecta: identificadores duplicados, tareas previas inexistentes, tiempos
 * inconsistentes (a ≤ m ≤ b), actividades aisladas y bucles de precedencia.
 */
export function validateProject(activities: Activity[]): HealthIssue[] {
  issueCounter = 0;
  const issues: HealthIssue[] = [];

  if (activities.length === 0) return issues;

  const idSet = new Set<string>();
  const idCounts = new Map<string, number>();

  // ── Identificadores Duplicados ─────────────────────────────────────────
  for (const act of activities) {
    idCounts.set(act.id, (idCounts.get(act.id) ?? 0) + 1);
    idSet.add(act.id);
  }

  for (const [id, count] of idCounts) {
    if (count > 1) {
      issues.push(
        issue(
          'error',
          `El código de actividad "${id}" está repetido ${count} veces. Cada actividad debe tener un identificador único para construir la red.`,
          [id],
        ),
      );
    }
  }

  // ── Predecesoras Inexistentes (Huérfanas) ───────────────────────────────
  for (const act of activities) {
    for (const pred of act.predecessors) {
      if (!idSet.has(pred)) {
        issues.push(
          issue(
            'error',
            `La actividad "${act.id}" tiene como predecesora a "${pred}", pero dicha tarea no existe en la tabla de actividades.`,
            [act.id],
          ),
        );
      }
    }
  }

  // ── Tiempos y Datos Faltantes ──────────────────────────────────────────
  for (const act of activities) {
    // Tiempos negativos
    if (act.optimistic < 0 || act.mostLikely < 0 || act.pessimistic < 0) {
      issues.push(
        issue(
          'error',
          `La actividad "${act.id}" tiene estimaciones de tiempo negativas. Las duraciones en días deben ser mayores o iguales a cero.`,
          [act.id],
        ),
      );
    }

    // Tiempos en cero absoluto
    if (act.optimistic === 0 && act.mostLikely === 0 && act.pessimistic === 0) {
      issues.push(
        issue(
          'warning',
          `La actividad "${act.id}" tiene duración cero en todos sus escenarios (a=0, m=0, b=0). Conviene asignarle un tiempo estimado en días.`,
          [act.id],
        ),
      );
    }

    // Coherencia PERT: a ≤ m ≤ b
    if (act.optimistic > act.mostLikely || act.mostLikely > act.pessimistic) {
      issues.push(
        issue(
          'warning',
          `En la actividad "${act.id}", el orden de los tiempos es inconsistente: el tiempo optimista (a=${act.optimistic}) debe ser menor o igual al más probable (m=${act.mostLikely}), y este menor o igual al pesimista (b=${act.pessimistic}).`,
          [act.id],
        ),
      );
    }

    // Nombre faltante
    if (!act.name || act.name.trim() === '') {
      issues.push(
        issue(
          'info',
          `La actividad "${act.id}" aún no tiene un nombre o descripción que facilite su identificación.`,
          [act.id],
        ),
      );
    }
  }

  // ── Actividades Aisladas ───────────────────────────────────────────────
  const hasSuccessors = new Set<string>();
  const roots: string[] = [];

  for (const act of activities) {
    for (const pred of act.predecessors) {
      hasSuccessors.add(pred);
    }
    if (act.predecessors.length === 0) {
      roots.push(act.id);
    }
  }

  if (activities.length > 1) {
    for (const act of activities) {
      const isRoot = act.predecessors.length === 0;
      const hasSuc = hasSuccessors.has(act.id);
      if (isRoot && !hasSuc) {
        issues.push(
          issue(
            'warning',
            `La actividad "${act.id}" está desconectada del flujo principal: no tiene predecesoras y ninguna otra tarea depende de ella.`,
            [act.id],
          ),
        );
      }
    }
  }

  // ── Dependencias Circulares ────────────────────────────────────────────
  issues.push(...detectCycles(activities, idSet));

  return issues;
}
