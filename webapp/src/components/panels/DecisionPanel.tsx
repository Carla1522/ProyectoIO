import React, { useState } from 'react';
import { useProjectStore } from '../../store/useProjectStore';
import { probabilityOfSuccess } from '../../engine/probability';
import KPICard from '../ui/KPICard';

export default function DecisionPanel() {
  const cpmResult = useProjectStore((s) => s.cpmResult);
  const activities = useProjectStore((s) => s.project.activities);

  const defaultDeadline = cpmResult ? Math.ceil(cpmResult.duration) : 30;
  const [targetDeadline, setTargetDeadline] = useState<number>(defaultDeadline);

  if (!cpmResult || activities.length === 0) {
    return (
      <div className="card p-4 space-y-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Panel de Decisión Estratégica
        </span>
        <p className="text-xs text-text-muted">
          Los indicadores clave de decisión se calcularán automáticamente al definir la red en el paso 2.
        </p>
      </div>
    );
  }

  const currentDeadline = targetDeadline || Math.ceil(cpmResult.duration);
  const prob = probabilityOfSuccess(cpmResult, currentDeadline);
  const totalCost = activities.reduce((sum, a) => sum + (a.cost || 0), 0);
  const criticalCount = cpmResult.criticalActivities.length;
  const totalCount = activities.length;

  const probColor =
    prob.probability >= 0.8 ? 'success' : prob.probability >= 0.5 ? 'warn' : 'critical';

  return (
    <div className="card p-4 space-y-4">
      <div className="flex items-center justify-between border-b border-surface-4/60 pb-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Panel de Decisión Estratégica
        </span>
        <span className="text-2xs font-mono text-text-muted">
          Ruta: {cpmResult.criticalPath.join(' → ')}
        </span>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 gap-2.5">
        <KPICard
          label="Plazo Esperado"
          value={`${cpmResult.duration.toFixed(1)} d`}
          subtext={`Varianza σ² = ${cpmResult.variance.toFixed(2)}`}
          color="accent"
        />
        <KPICard
          label="Presupuesto Total"
          value={`$${totalCost.toLocaleString('en-US')}`}
          subtext={`${totalCount} actividades programadas`}
          color="neutral"
        />
        <KPICard
          label="Actividades Críticas"
          value={`${criticalCount} / ${totalCount}`}
          subtext={`${((criticalCount / (totalCount || 1)) * 100).toFixed(0)}% de impacto directo`}
          color="critical"
        />
        <KPICard
          label={`P(T ≤ ${currentDeadline}d)`}
          value={`${(prob.probability * 100).toFixed(1)}%`}
          subtext={`Z = ${prob.z.toFixed(2)} · Holgura: ${prob.slackVsDeadline >= 0 ? '+' : ''}${prob.slackVsDeadline.toFixed(1)}d`}
          color={probColor}
        />
      </div>

      {/* Interactive Quick Probability Slider */}
      <div className="bg-surface-1/60 p-2.5 rounded-lg border border-surface-4/40 space-y-2">
        <div className="flex items-center justify-between text-2xs">
          <span className="text-text-muted font-medium">Simular Fecha Límite de Entrega:</span>
          <span className="font-mono text-text-primary font-bold">
            {currentDeadline} días ({prob.slackVsDeadline >= 0 ? '+' : ''}
            {prob.slackVsDeadline.toFixed(1)}d margen)
          </span>
        </div>
        <input
          type="range"
          min={Math.max(1, Math.floor(cpmResult.duration - 3 * cpmResult.sigma))}
          max={Math.ceil(cpmResult.duration + 3 * cpmResult.sigma)}
          step="0.5"
          value={currentDeadline}
          onChange={(e) => setTargetDeadline(parseFloat(e.target.value))}
          className="w-full accent-accent h-1.5 bg-surface-3 rounded cursor-pointer"
        />
      </div>
    </div>
  );
}
