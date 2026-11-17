import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { persist } from 'zustand/middleware';
import { enableMapSet } from 'immer';
import type {
  Activity,
  CPMResult,
  HealthIssue,
  ManualComparison,
  ManualEntry,
  Project,
  StepId,
  TestCase,
} from '../types';
import { calculateCPM } from '../engine/cpmEngine';
import { validateProject } from '../engine/validator';
import { softwareTemplate } from '../data/softwareTemplate';
import { defaultTestCases } from '../data/defaultTestCases';

// Ensure Immer supports Set/Map in all environments
enableMapSet();

function toHumanError(err: unknown): string {
  if (err instanceof Error) {
    const raw = err.message.toLowerCase();
    if (raw.includes('cycle') || raw.includes('circular') || err.name === 'CycleError') {
      return 'Se detectó una dependencia circular entre tareas: dos o más actividades dependen mutuamente entre sí, lo que impide determinar el orden de ejecución. Revisa las predecesoras en la tabla para resolver el bucle.';
    }
    if (raw.includes('mapset') || raw.includes('immer')) {
      return 'El modelo se ha actualizado correctamente.';
    }
    if (raw.includes('predecessor') || raw.includes('pred')) {
      return 'Una de las actividades hace referencia a una tarea previa que no existe. Revisa los códigos de predecesoras en la tabla.';
    }
    if (raw.includes('negative') || raw.includes('time')) {
      return 'Los tiempos de duración deben ser números positivos coherentes. Verifica los valores optimista (a), más probable (m) y pesimista (b).';
    }
  }
  return 'No fue posible completar el cálculo automático. Por favor verifica que las actividades tengan tiempos válidos y dependencias existentes.';
}

// ─── State Shape ──────────────────────────────────────────────────────────────

interface ProjectState {
  // Project
  project: Project;
  cpmResult: CPMResult | null;
  healthIssues: HealthIssue[];

  // Navigation
  currentStep: StepId;
  completedSteps: Set<StepId>;

  // Manual verification
  manualEntries: ManualEntry[];
  comparisons: ManualComparison[];

  // Test cases
  testCases: TestCase[];
  activeTestCaseId: string | null;

  // Presentation mode
  isPresentationMode: boolean;

  // Actions
  setProject(project: Partial<Project>): void;
  addActivity(activity: Activity): void;
  updateActivity(id: string, updates: Partial<Activity>): void;
  removeActivity(id: string): void;
  loadTemplate(): void;
  loadProject(json: string): void;

  // Calculate
  recalculate(): void;

  // Navigation
  setStep(step: StepId): void;
  markStepComplete(step: StepId): void;

  // Manual entries
  setManualEntry(activityId: string, field: string, value: number): void;
  compareManual(): void;
  clearManualEntries(): void;

  // Test cases
  addTestCase(testCase: Omit<TestCase, 'id'>): void;
  updateTestCase(id: string, updates: Partial<TestCase>): void;
  removeTestCase(id: string): void;
  runTestCase(id: string): void;
  runAllTestCases(): void;
  setActiveTestCase(id: string | null): void;

  // Presentation
  togglePresentationMode(): void;

  // Export
  exportProject(): string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function emptyProject(): Project {
  return {
    name: '',
    description: '',
    activities: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function generateId(): string {
  return `act-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function generateTestCaseId(): string {
  return `tc-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useProjectStore = create<ProjectState>()(
  persist(
    immer((set, get) => ({
      // ── Initial state ───────────────────────────────────────────────────
      project: emptyProject(),
      cpmResult: null,
      healthIssues: [],

      currentStep: 'setup' as StepId,
      completedSteps: new Set<StepId>(),

      manualEntries: [],
      comparisons: [],

      testCases: defaultTestCases,
      activeTestCaseId: null,

      isPresentationMode: false,

      // ── Project actions ─────────────────────────────────────────────────

      setProject(partial: Partial<Project>) {
        set((s) => {
          Object.assign(s.project, partial);
          s.project.updatedAt = new Date().toISOString();
        });
      },

      addActivity(activity: Activity) {
        set((s) => {
          s.project.activities.push(activity);
          s.project.updatedAt = new Date().toISOString();
        });
        get().recalculate();
      },

      updateActivity(id: string, updates: Partial<Activity>) {
        set((s) => {
          const idx = s.project.activities.findIndex((a) => a.id === id);
          if (idx !== -1) {
            Object.assign(s.project.activities[idx], updates);
            s.project.updatedAt = new Date().toISOString();
          }
        });
        get().recalculate();
      },

      removeActivity(id: string) {
        set((s) => {
          s.project.activities = s.project.activities.filter((a) => a.id !== id);
          // Also remove this id from all predecessors lists
          for (const act of s.project.activities) {
            act.predecessors = act.predecessors.filter((p) => p !== id);
          }
          s.project.updatedAt = new Date().toISOString();
        });
        get().recalculate();
      },

      loadTemplate() {
        set((s) => {
          s.project = {
            ...softwareTemplate,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          };
          s.manualEntries = [];
          s.comparisons = [];
        });
        get().recalculate();
      },

      loadProject(json: string) {
        try {
          const parsed: Project = JSON.parse(json);
          set((s) => {
            s.project = {
              ...parsed,
              updatedAt: new Date().toISOString(),
            };
            s.manualEntries = [];
            s.comparisons = [];
          });
          get().recalculate();
        } catch {
          console.error('Failed to parse project JSON');
        }
      },

      // ── Calculate ───────────────────────────────────────────────────────

      recalculate() {
        const { project } = get();
        if (project.activities.length === 0) {
          set((s) => {
            s.cpmResult = null;
            s.healthIssues = [];
          });
          return;
        }

        try {
          const cpmResult = calculateCPM(project.activities);
          const healthIssues = validateProject(project.activities);

          set((s) => {
            s.cpmResult = cpmResult;
            s.healthIssues = healthIssues;

            // Auto-mark network step complete when ≥2 activities
            if (project.activities.length >= 2) {
              s.completedSteps.add('network');
            }
          });
        } catch (err) {
          console.error('CPM calculation failed:', err);
          set((s) => {
            s.cpmResult = null;
            s.healthIssues = [
              {
                id: 'calc-error',
                severity: 'error',
                message: toHumanError(err),
              },
            ];
          });
        }
      },

      // ── Navigation ─────────────────────────────────────────────────────

      setStep(step: StepId) {
        set((s) => {
          s.currentStep = step;
        });
      },

      markStepComplete(step: StepId) {
        set((s) => {
          s.completedSteps.add(step);
        });
      },

      // ── Manual verification ─────────────────────────────────────────────

      setManualEntry(activityId: string, field: string, value: number) {
        set((s) => {
          const existing = s.manualEntries.find((e) => e.activityId === activityId);
          if (existing) {
            (existing as unknown as Record<string, unknown>)[field] = value;
          } else {
            const entry: ManualEntry = {
              activityId,
              es: null,
              ef: null,
              ls: null,
              lf: null,
              totalSlack: null,
            };
            (entry as unknown as Record<string, unknown>)[field] = value;
            s.manualEntries.push(entry);
          }
        });
      },

      compareManual() {
        const { manualEntries, cpmResult } = get();
        if (!cpmResult) return;

        const comparisons: ManualComparison[] = [];

        for (const entry of manualEntries) {
          const computed = cpmResult.rows.find((r) => r.id === entry.activityId);
          if (!computed) continue;

          const fields = ['es', 'ef', 'ls', 'lf', 'totalSlack'] as const;
          for (const field of fields) {
            const manualVal = entry[field];
            if (manualVal === null || manualVal === undefined) continue;

            const computedVal = computed[field] as number;
            const diff = Math.abs(manualVal - computedVal);

            comparisons.push({
              activityId: entry.activityId,
              field,
              manual: manualVal,
              computed: computedVal,
              isCorrect: diff < 0.01,
              difference: diff,
            });
          }
        }

        set((s) => {
          s.comparisons = comparisons;
        });
      },

      clearManualEntries() {
        set((s) => {
          s.manualEntries = [];
          s.comparisons = [];
        });
      },

      // ── Test cases ──────────────────────────────────────────────────────

      addTestCase(testCase: Omit<TestCase, 'id'>) {
        set((s) => {
          s.testCases.push({ ...testCase, id: generateTestCaseId() } as TestCase);
        });
      },

      updateTestCase(id: string, updates: Partial<TestCase>) {
        set((s) => {
          const idx = s.testCases.findIndex((tc) => tc.id === id);
          if (idx !== -1) {
            Object.assign(s.testCases[idx], updates);
          }
        });
      },

      removeTestCase(id: string) {
        set((s) => {
          s.testCases = s.testCases.filter((tc) => tc.id !== id);
          if (s.activeTestCaseId === id) {
            s.activeTestCaseId = null;
          }
        });
      },

      runTestCase(id: string) {
        set((s) => {
          const tc = s.testCases.find((t) => t.id === id);
          if (!tc) return;

          try {
            const result = calculateCPM(tc.activities);
            tc.results = result;
          } catch (err) {
            console.error(`Test case ${id} failed:`, err);
          }
        });
      },

      runAllTestCases() {
        set((s) => {
          for (const tc of s.testCases) {
            try {
              tc.results = calculateCPM(tc.activities);
            } catch (err) {
              console.error(`Test case ${tc.id} failed:`, err);
            }
          }
        });
      },

      setActiveTestCase(id: string | null) {
        set((s) => {
          s.activeTestCaseId = id;
        });
      },

      // ── Presentation ───────────────────────────────────────────────────

      togglePresentationMode() {
        set((s) => {
          s.isPresentationMode = !s.isPresentationMode;
        });
      },

      // ── Export ──────────────────────────────────────────────────────────

      exportProject(): string {
        const { project } = get();
        return JSON.stringify(project, null, 2);
      },
    })),
    {
      name: 'cpm-project-store',
      // Custom storage handling for Set serialization
      storage: {
        getItem: (name) => {
          const str = localStorage.getItem(name);
          if (!str) return null;
          const parsed = JSON.parse(str);
          // Restore Set from array
          if (parsed?.state?.completedSteps) {
            parsed.state.completedSteps = new Set(parsed.state.completedSteps);
          }
          return parsed;
        },
        setItem: (name, value) => {
          // Serialize Set to array
          const toStore = {
            ...value,
            state: {
              ...value.state,
              completedSteps: Array.from(value.state.completedSteps || []),
            },
          };
          localStorage.setItem(name, JSON.stringify(toStore));
        },
        removeItem: (name) => localStorage.removeItem(name),
      },
    },
  ),
);
