// ─── Core Domain Types ───────────────────────────────────────────────────────
// Shared across engine, store, and all components

export interface Activity {
  id: string;
  name: string;
  predecessors: string[];
  optimistic: number;   // a
  mostLikely: number;   // m
  pessimistic: number;  // b
  cost: number;
}

export interface ComputedActivity extends Activity {
  code: string;         // A1, A2, ...
  te: number;           // (a + 4m + b) / 6
  variance: number;     // ((b - a) / 6)²
  sigma: number;
  es: number;
  ef: number;
  ls: number;
  lf: number;
  totalSlack: number;
  freeSlack: number;
  isCritical: boolean;
}

export interface CPMResult {
  rows: ComputedActivity[];
  duration: number;
  criticalPath: string[];
  criticalActivities: string[];
  variance: number;
  sigma: number;
  order: string[];
}

export interface ProbabilityResult {
  z: number;
  probability: number;
  deadline: number;
  expectedDuration: number;
  sigma: number;
  slackVsDeadline: number;
}

// ─── Manual Calculation Verification ─────────────────────────────────────────

export interface ManualEntry {
  activityId: string;
  es: number | null;
  ef: number | null;
  ls: number | null;
  lf: number | null;
  totalSlack: number | null;
}

export interface ManualComparison {
  activityId: string;
  field: string;
  manual: number;
  computed: number;
  isCorrect: boolean;
  difference: number;
}

// ─── Test Cases ──────────────────────────────────────────────────────────────

export interface TestCase {
  id: string;
  name: string;
  description: string;
  activities: Activity[];
  isEdgeCase: boolean;
  expectedDuration?: number;
  expectedCriticalPath?: string[];
  results?: CPMResult;
  manualEntries?: ManualEntry[];
  comparisons?: ManualComparison[];
}

// ─── Project ─────────────────────────────────────────────────────────────────

export interface Project {
  name: string;
  description: string;
  activities: Activity[];
  createdAt: string;
  updatedAt: string;
}

// ─── Health Panel ────────────────────────────────────────────────────────────

export type HealthSeverity = 'error' | 'warning' | 'info';

export interface HealthIssue {
  id: string;
  severity: HealthSeverity;
  message: string;
  affectedActivities?: string[];
}

// ─── Step Navigation ─────────────────────────────────────────────────────────

export type StepId = 'setup' | 'network' | 'verify' | 'test-cases' | 'results';

export interface Step {
  id: StepId;
  label: string;
  description: string;
  isComplete: boolean;
  isActive: boolean;
}

// ─── KPI ─────────────────────────────────────────────────────────────────────

export interface KPI {
  label: string;
  value: string;
  subtext?: string;
  trend?: 'up' | 'down' | 'neutral';
  color?: 'accent' | 'critical' | 'success' | 'warn' | 'neutral';
}
