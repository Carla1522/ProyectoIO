// ─── CPM / PERT Calculation Engine ───────────────────────────────────────────
// Pure functions: topological sort (Kahn), forward/backward pass, critical path.

import type { Activity, ComputedActivity, CPMResult } from '../types';

/** Floating-point comparison tolerance */
const EPSILON = 1e-9;

// ─── Error types ─────────────────────────────────────────────────────────────

export class CycleError extends Error {
  constructor(
    message = 'Se detectó una dependencia circular entre tareas: una actividad depende de otra que a su vez requiere su finalización.'
  ) {
    super(message);
    this.name = 'CycleError';
  }
}

// ─── PERT helper formulas ────────────────────────────────────────────────────

/** PERT expected time: te = (a + 4m + b) / 6 */
export function calculateTE(a: number, m: number, b: number): number {
  return (a + 4 * m + b) / 6;
}

/** PERT variance: σ² = ((b - a) / 6)² */
export function calculateVariance(a: number, b: number): number {
  const range = (b - a) / 6;
  return range * range;
}

// ─── Topological Sort (Kahn's algorithm) ─────────────────────────────────────

/**
 * Returns activity IDs in topological order.
 * @throws {CycleError} if the dependency graph contains a cycle.
 */
export function topologicalSort(activities: Activity[]): string[] {
  // Build adjacency list and in-degree map
  const inDegree = new Map<string, number>();
  const successors = new Map<string, string[]>();

  for (const act of activities) {
    if (!inDegree.has(act.id)) inDegree.set(act.id, 0);
    if (!successors.has(act.id)) successors.set(act.id, []);

    for (const pred of act.predecessors) {
      // Only count predecessors that exist in our activity set
      if (!successors.has(pred)) successors.set(pred, []);
      successors.get(pred)!.push(act.id);
      inDegree.set(act.id, (inDegree.get(act.id) ?? 0) + 1);
    }
  }

  // Seed the queue with nodes that have no incoming edges
  const queue: string[] = [];
  for (const act of activities) {
    if ((inDegree.get(act.id) ?? 0) === 0) {
      queue.push(act.id);
    }
  }

  const sorted: string[] = [];

  while (queue.length > 0) {
    const current = queue.shift()!;
    sorted.push(current);

    for (const succ of successors.get(current) ?? []) {
      const newDeg = (inDegree.get(succ) ?? 1) - 1;
      inDegree.set(succ, newDeg);
      if (newDeg === 0) {
        queue.push(succ);
      }
    }
  }

  if (sorted.length !== activities.length) {
    throw new CycleError();
  }

  return sorted;
}

// ─── Critical-path finder ────────────────────────────────────────────────────

/**
 * Traces back through the network to find the critical path.
 * When multiple critical predecessors exist, chooses the one with the highest
 * cumulative variance (conservative PERT approach).
 */
function findCriticalPath(
  rows: Map<string, ComputedActivity>,
  order: string[],
): string[] {
  // Find terminal activities (those that are critical and whose EF equals project duration)
  const allIds = new Set(order);
  const hasSuccessor = new Set<string>();
  for (const row of rows.values()) {
    for (const pred of row.predecessors) {
      if (allIds.has(pred)) hasSuccessor.add(pred);
    }
  }

  // End nodes on the critical path
  const criticalRows = Array.from(rows.values()).filter(r => r.isCritical);
  const endNodes = criticalRows.filter(r => !hasSuccessor.has(r.id));

  if (endNodes.length === 0) return [];

  // Pick the end node with the highest variance accumulation
  // (For a single critical path this is usually the only terminal node)
  let traceEnd = endNodes[0];
  if (endNodes.length > 1) {
    // Accumulate variance along each possible path from start; pick highest
    const varAccum = computeVarianceAccum(rows, order);
    for (const node of endNodes) {
      if ((varAccum.get(node.id) ?? 0) > (varAccum.get(traceEnd.id) ?? 0)) {
        traceEnd = node;
      }
    }
  }

  // Trace backwards from the chosen terminal
  const varAccum = computeVarianceAccum(rows, order);
  const path: string[] = [];
  let current: ComputedActivity | undefined = traceEnd;

  while (current) {
    path.unshift(current.id);

    // Among critical predecessors, pick the one with the highest accumulated variance
    let bestPred: ComputedActivity | undefined;
    let bestVar = -1;

    for (const predId of current.predecessors) {
      const pred = rows.get(predId);
      if (pred && pred.isCritical) {
        const v = varAccum.get(pred.id) ?? 0;
        if (v > bestVar) {
          bestVar = v;
          bestPred = pred;
        }
      }
    }

    current = bestPred;
  }

  return path;
}

/** Compute accumulated variance along longest-variance paths (forward) */
function computeVarianceAccum(
  rows: Map<string, ComputedActivity>,
  order: string[],
): Map<string, number> {
  const accum = new Map<string, number>();

  for (const id of order) {
    const row = rows.get(id)!;
    let maxPredVar = 0;
    for (const predId of row.predecessors) {
      const predRow = rows.get(predId);
      if (predRow) {
        maxPredVar = Math.max(maxPredVar, accum.get(predId) ?? 0);
      }
    }
    accum.set(id, maxPredVar + row.variance);
  }

  return accum;
}

// ─── Main CPM calculation ────────────────────────────────────────────────────

/**
 * Full CPM/PERT calculation: forward pass, backward pass, slacks, critical path.
 * @throws {CycleError} if the dependency graph contains a cycle.
 */
export function calculateCPM(activities: Activity[]): CPMResult {
  if (activities.length === 0) {
    return {
      rows: [],
      duration: 0,
      criticalPath: [],
      criticalActivities: [],
      variance: 0,
      sigma: 0,
      order: [],
    };
  }

  const order = topologicalSort(activities);

  // Build a map of activity data keyed by ID
  const actMap = new Map<string, Activity>();
  for (const act of activities) actMap.set(act.id, act);

  // Initialise computed rows
  const rows = new Map<string, ComputedActivity>();
  let codeIndex = 1;
  for (const id of order) {
    const act = actMap.get(id)!;
    const te = calculateTE(act.optimistic, act.mostLikely, act.pessimistic);
    const variance = calculateVariance(act.optimistic, act.pessimistic);
    rows.set(id, {
      ...act,
      code: `A${codeIndex++}`,
      te,
      variance,
      sigma: Math.sqrt(variance),
      es: 0,
      ef: 0,
      ls: 0,
      lf: 0,
      totalSlack: 0,
      freeSlack: 0,
      isCritical: false,
    });
  }

  // ── Forward pass ─────────────────────────────────────────────────────────
  for (const id of order) {
    const row = rows.get(id)!;
    let maxPredEF = 0;
    for (const predId of row.predecessors) {
      const pred = rows.get(predId);
      if (pred) {
        maxPredEF = Math.max(maxPredEF, pred.ef);
      }
    }
    row.es = maxPredEF;
    row.ef = row.es + row.te;
  }

  // Project duration = max EF
  let projectDuration = 0;
  for (const row of rows.values()) {
    projectDuration = Math.max(projectDuration, row.ef);
  }

  // ── Backward pass ────────────────────────────────────────────────────────
  // Build set of successors for each activity
  const successorMap = new Map<string, string[]>();
  for (const id of order) successorMap.set(id, []);
  for (const id of order) {
    const row = rows.get(id)!;
    for (const predId of row.predecessors) {
      if (successorMap.has(predId)) {
        successorMap.get(predId)!.push(id);
      }
    }
  }

  // Initialise LF of terminal activities to project duration
  for (const id of order) {
    const succs = successorMap.get(id) ?? [];
    if (succs.length === 0) {
      rows.get(id)!.lf = projectDuration;
    }
  }

  // Traverse in reverse topological order
  for (let i = order.length - 1; i >= 0; i--) {
    const id = order[i];
    const row = rows.get(id)!;
    const succs = successorMap.get(id) ?? [];

    if (succs.length > 0) {
      let minSuccLS = Infinity;
      for (const succId of succs) {
        minSuccLS = Math.min(minSuccLS, rows.get(succId)!.ls);
      }
      row.lf = minSuccLS;
    }

    row.ls = row.lf - row.te;
  }

  // ── Compute slacks and criticality ────────────────────────────────────────
  for (const id of order) {
    const row = rows.get(id)!;
    row.totalSlack = row.ls - row.es;

    // Free slack = min(ES of successors) - EF of this activity
    const succs = successorMap.get(id) ?? [];
    if (succs.length > 0) {
      let minSuccES = Infinity;
      for (const succId of succs) {
        minSuccES = Math.min(minSuccES, rows.get(succId)!.es);
      }
      row.freeSlack = minSuccES - row.ef;
    } else {
      // Terminal activities: free slack = project duration - EF
      row.freeSlack = projectDuration - row.ef;
    }

    row.isCritical = Math.abs(row.totalSlack) < EPSILON;
  }

  // ── Critical path ─────────────────────────────────────────────────────────
  const criticalPath = findCriticalPath(rows, order);

  const criticalActivities = Array.from(rows.values())
    .filter(r => r.isCritical)
    .map(r => r.id);

  // Project variance = sum of variances on the critical path
  let projectVariance = 0;
  for (const id of criticalPath) {
    projectVariance += rows.get(id)!.variance;
  }

  // Build output rows in topological order
  const resultRows: ComputedActivity[] = order.map(id => rows.get(id)!);

  return {
    rows: resultRows,
    duration: projectDuration,
    criticalPath,
    criticalActivities,
    variance: projectVariance,
    sigma: Math.sqrt(projectVariance),
    order,
  };
}
