import React from 'react';
import { useProjectStore } from '../../store/useProjectStore';
import type { StepId } from '../../types';

interface StepCheck {
  id: StepId;
  title: string;
  detail: string;
}

const CHECKLIST: StepCheck[] = [
  { id: 'setup', title: '1. Planteamiento', detail: 'Definición de nombre, alcance y restricciones iniciales' },
  { id: 'network', title: '2. Red PERT/CPM', detail: 'Ingreso tabular de tiempos (a, m, b) y dependencias' },
  { id: 'verify', title: '3. Verificación Manual', detail: 'Contraste visual de cálculos manuales vs motor' },
  { id: 'test-cases', title: '4. Casos de Prueba', detail: 'Validación en al menos 3 casos y caso límite' },
  { id: 'results', title: '5. Decisión y Resultados', detail: 'Ruta crítica, Gantt y análisis de probabilidad' },
];

export default function ProgressPanel() {
  const currentStep = useProjectStore((s) => s.currentStep);
  const completedSteps = useProjectStore((s) => s.completedSteps);
  const setStep = useProjectStore((s) => s.setStep);

  const completedCount = completedSteps.size;
  const progressPercent = Math.round((completedCount / CHECKLIST.length) * 100);

  return (
    <div className="card p-4 space-y-3.5">
      <div className="flex items-center justify-between border-b border-surface-4/60 pb-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Panel de Avance Práctico
        </span>
        <span className="text-2xs font-mono font-medium text-accent-light">
          {completedCount} / {CHECKLIST.length} completados ({progressPercent}%)
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-surface-3 h-1.5 rounded-full overflow-hidden">
        <div
          className="bg-accent h-full transition-all duration-300 rounded-full"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Steps Checklist */}
      <div className="space-y-2">
        {CHECKLIST.map((step) => {
          const isDone = completedSteps.has(step.id);
          const isCurrent = currentStep === step.id;

          return (
            <button
              key={step.id}
              onClick={() => setStep(step.id)}
              className={`w-full text-left flex items-start gap-2.5 p-2 rounded-lg transition-all text-xs ${
                isCurrent
                  ? 'bg-surface-3 border border-accent/40 shadow-sm'
                  : 'hover:bg-surface-3/50 border border-transparent'
              }`}
            >
              <div
                className={`w-4 h-4 rounded-full flex items-center justify-center text-2xs mt-0.5 shrink-0 transition-colors ${
                  isDone
                    ? 'bg-success/20 text-success-light font-bold'
                    : isCurrent
                    ? 'border-2 border-accent text-accent'
                    : 'bg-surface-4 text-text-muted'
                }`}
              >
                {isDone ? '✓' : isCurrent ? '●' : '○'}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span
                    className={`font-medium truncate ${
                      isCurrent
                        ? 'text-accent-light'
                        : isDone
                        ? 'text-text-primary'
                        : 'text-text-muted'
                    }`}
                  >
                    {step.title}
                  </span>
                  {isCurrent && (
                    <span className="text-3xs font-mono px-1.5 py-0.2 bg-accent/20 text-accent-light rounded">
                      ACTUAL
                    </span>
                  )}
                </div>
                <p className="text-2xs text-text-muted truncate mt-0.5">{step.detail}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
