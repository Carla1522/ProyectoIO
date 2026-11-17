import React from 'react';
import { useProjectStore } from '../../store/useProjectStore';

export default function HealthPanel() {
  const healthIssues = useProjectStore((s) => s.healthIssues);
  const activities = useProjectStore((s) => s.project.activities);

  const errors = healthIssues.filter((i) => i.severity === 'error');
  const warnings = healthIssues.filter((i) => i.severity === 'warning');
  const infos = healthIssues.filter((i) => i.severity === 'info');

  const isHealthy = activities.length > 0 && errors.length === 0 && warnings.length === 0;

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between border-b border-surface-4/60 pb-2.5">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Panel de Salud del Modelo
          </span>
        </div>
        {activities.length === 0 ? (
          <span className="text-2xs font-mono text-text-muted">Sin datos</span>
        ) : isHealthy ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-mono font-medium bg-success/10 text-success-light border border-success/20">
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            100% Consistente
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-2xs font-mono font-medium bg-surface-3 text-text-secondary border border-surface-4">
            {errors.length > 0 && <span className="text-critical-light">● {errors.length} errores</span>}
            {warnings.length > 0 && <span className="text-warn-light">● {warnings.length} avisos</span>}
          </span>
        )}
      </div>

      {activities.length === 0 ? (
        <p className="text-xs text-text-muted">
          Ingresa actividades en el paso 2 o carga la plantilla para comenzar la auditoría matemática.
        </p>
      ) : isHealthy ? (
        <div className="flex items-start gap-2.5 py-1 text-xs text-text-muted">
          <span className="text-success-light text-sm">✓</span>
          <div>
            <p className="text-text-secondary font-medium">Grafo Acíclico Dirigido (DAG) Válido</p>
            <p className="text-2xs text-text-muted mt-0.5">
              Sin dependencias circulares, sin nodos huérfanos y con distribución PERT consistente (a ≤ m ≤ b).
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
          {errors.map((issue) => (
            <div
              key={issue.id}
              className="flex items-start gap-2 p-2 rounded-md bg-critical/10 border border-critical/20 text-xs"
            >
              <span className="text-critical-light font-bold text-sm leading-none mt-0.5">✕</span>
              <div className="flex-1">
                <span className="text-critical-light font-medium block">{issue.message}</span>
                {issue.affectedActivities && issue.affectedActivities.length > 0 && (
                  <span className="text-2xs text-text-muted font-mono mt-0.5 block">
                    Afecta a: {issue.affectedActivities.join(', ')}
                  </span>
                )}
              </div>
            </div>
          ))}

          {warnings.map((issue) => (
            <div
              key={issue.id}
              className="flex items-start gap-2 p-2 rounded-md bg-warn/10 border border-warn/20 text-xs"
            >
              <span className="text-warn-light font-bold text-sm leading-none mt-0.5">⚠</span>
              <div className="flex-1">
                <span className="text-warn-light font-medium block">{issue.message}</span>
                {issue.affectedActivities && issue.affectedActivities.length > 0 && (
                  <span className="text-2xs text-text-muted font-mono mt-0.5 block">
                    Afecta a: {issue.affectedActivities.join(', ')}
                  </span>
                )}
              </div>
            </div>
          ))}

          {infos.map((issue) => (
            <div
              key={issue.id}
              className="flex items-start gap-2 p-2 rounded-md bg-accent/10 border border-accent/20 text-xs text-text-muted"
            >
              <span className="text-accent-light font-bold text-sm leading-none mt-0.5">ℹ</span>
              <span>{issue.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
