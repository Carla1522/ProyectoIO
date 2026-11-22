// ─── Manual vs Computed Comparison ───────────────────────────────────────────
// Compare student-entered manual values against engine-computed results.

import type { ManualEntry, ComputedActivity, ManualComparison } from '../types';

/** Tolerance for floating-point rounding when marking correctness. */
const TOLERANCE = 0.01;

/** Fields to compare between manual entries and computed activities. */
const COMPARED_FIELDS: (keyof Pick<ManualEntry, 'es' | 'ef' | 'ls' | 'lf' | 'totalSlack'>)[] = [
  'es',
  'ef',
  'ls',
  'lf',
  'totalSlack',
];

/**
 * Compares each manual entry field against the corresponding computed value.
 * Only compares fields where the manual value is not null.
 *
 * @returns An array of comparison results, one per (activity, field) pair.
 */
export function compareManualEntries(
  manual: ManualEntry[],
  computed: ComputedActivity[],
): ManualComparison[] {
  // Index computed activities by ID for O(1) lookup
  const computedMap = new Map<string, ComputedActivity>();
  for (const c of computed) computedMap.set(c.id, c);

  const results: ManualComparison[] = [];

  for (const entry of manual) {
    const comp = computedMap.get(entry.activityId);
    if (!comp) continue; // No matching computed activity; skip

    for (const field of COMPARED_FIELDS) {
      const manualValue = entry[field];
      if (manualValue === null || manualValue === undefined) continue;

      const computedValue = comp[field] as number;
      const difference = Math.abs(manualValue - computedValue);
      const isCorrect = difference < TOLERANCE;

      results.push({
        activityId: entry.activityId,
        field,
        manual: manualValue,
        computed: computedValue,
        isCorrect,
        difference,
      });
    }
  }

  return results;
}
