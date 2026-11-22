import React, { useState, useMemo } from 'react';
import { useProjectStore } from '../../store/useProjectStore';
import { probabilityOfSuccess } from '../../engine/probability';
import KPICard from '../ui/KPICard';
import type { ComputedActivity } from '../../types';

export default function ResultsStep() {
  const cpmResult = useProjectStore((s) => s.cpmResult);
  const project = useProjectStore((s) => s.project);
  const setStep = useProjectStore((s) => s.setStep);

  const [targetDeadline, setTargetDeadline] = useState<number>(() =>
    cpmResult ? Math.ceil(cpmResult.duration) : 30
  );
  const [activeTab, setActiveTab] = useState<'network' | 'gantt' | 'table' | 'prob'>('network');

  if (!cpmResult || cpmResult.rows.length === 0) {
    return (
      <div className="card p-8 text-center max-w-xl mx-auto my-12 space-y-4">
        <div className="text-3xl">📊</div>
        <h2 className="text-lg font-bold text-text-primary">Sin resultados que mostrar</h2>
        <p className="text-sm text-text-muted">
          Genera primero la red de actividades en el Paso 2 para calcular la ruta crítica, el cronograma de Gantt y la probabilidad estadística.
        </p>
        <button onClick={() => setStep('network')} className="btn-primary">
          Ir a Red PERT/CPM →
        </button>
      </div>
    );
  }

  const prob = probabilityOfSuccess(cpmResult, targetDeadline || Math.ceil(cpmResult.duration));
  const totalCost = project.activities.reduce((s, a) => s + (a.cost || 0), 0);

  return (
    <div className="space-y-6">
      {/* Top Title & Quick Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-text-primary">
            Resultados del Modelo PERT / CPM
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Programación temporal basada en el tiempo esperado ponderado y aproximación estadística por el Teorema del Límite Central.
          </p>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex bg-surface-2 p-1 rounded-lg border border-surface-4 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('network')}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
              activeTab === 'network'
                ? 'bg-accent text-white shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Diagrama de Red
          </button>
          <button
            onClick={() => setActiveTab('gantt')}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
              activeTab === 'gantt'
                ? 'bg-accent text-white shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Diagrama de Gantt
          </button>
          <button
            onClick={() => setActiveTab('table')}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
              activeTab === 'table'
                ? 'bg-accent text-white shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Tabla Matemática
          </button>
          <button
            onClick={() => setActiveTab('prob')}
            className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
              activeTab === 'prob'
                ? 'bg-accent text-white shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Curva de Riesgo
          </button>
        </div>
      </div>

      {/* KPI Highlights Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPICard
          label="Duración Esperada"
          value={`${cpmResult.duration.toFixed(1)} días`}
          subtext="Longitud de la ruta crítica"
          color="accent"
        />
        <KPICard
          label="Desviación Estándar (σ)"
          value={`${cpmResult.sigma.toFixed(2)} d`}
          subtext={`Varianza σ² = ${cpmResult.variance.toFixed(2)}`}
          color="neutral"
        />
        <KPICard
          label="Actividades Críticas"
          value={`${cpmResult.criticalActivities.length} / ${cpmResult.rows.length}`}
          subtext="Holgura total = 0"
          color="critical"
        />
        <KPICard
          label="Presupuesto Estimado"
          value={`$${totalCost.toLocaleString('en-US')}`}
          subtext="Inversión total programada"
          color="success"
        />
      </div>

      {/* Tab 1: Network Diagram */}
      {activeTab === 'network' && (
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-4/60 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-text-primary">
                Grafo de Actividades en Nodos (AON)
              </h2>
              <p className="text-2xs text-text-muted mt-0.5">
                Los nodos en rojo componen la Ruta Crítica determinada por el algoritmo de pasada hacia atrás.
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5 font-mono text-2xs text-critical-light">
                <span className="w-2.5 h-2.5 rounded bg-critical border border-critical-light" /> Ruta Crítica
              </span>
              <span className="flex items-center gap-1.5 font-mono text-2xs text-text-muted">
                <span className="w-2.5 h-2.5 rounded bg-surface-3 border border-surface-4" /> Con Holgura
              </span>
            </div>
          </div>

          <div className="overflow-x-auto py-4 flex justify-center">
            <NetworkDiagramSVG cpmResult={cpmResult} />
          </div>
        </div>
      )}

      {/* Tab 2: Gantt Chart */}
      {activeTab === 'gantt' && (
        <div className="card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-surface-4/60 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-text-primary">
                Cronograma de Barras (Diagrama de Gantt)
              </h2>
              <p className="text-2xs text-text-muted mt-0.5">
                Barra continua: Tiempo esperado (te). Línea punteada: Holgura total disponible.
              </p>
            </div>
            <span className="text-2xs font-mono text-text-muted">
              Fin Esperado: {cpmResult.duration.toFixed(1)} días
            </span>
          </div>

          <GanttChartHTML cpmResult={cpmResult} />
        </div>
      )}

      {/* Tab 3: Detailed Table */}
      {activeTab === 'table' && (
        <div className="card overflow-hidden">
          <div className="p-4 border-b border-surface-4/60 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">
              Matriz Computacional CPM / PERT
            </h2>
            <button
              onClick={() => {
                const csvHeaders = ['Codigo', 'Actividad', 'Predecesoras', 'a', 'm', 'b', 'te', 'varianza', 'ES', 'EF', 'LS', 'LF', 'Holgura Total', 'Es Critica'];
                const rows = cpmResult.rows.map((r) => [
                  r.code, `"${r.name}"`, `"${r.predecessors.join(', ')}"`, r.optimistic, r.mostLikely, r.pessimistic, r.te.toFixed(2), r.variance.toFixed(4), r.es.toFixed(2), r.ef.toFixed(2), r.ls.toFixed(2), r.lf.toFixed(2), r.totalSlack.toFixed(2), r.isCritical ? 'SI' : 'NO'
                ]);
                const csv = [csvHeaders.join(','), ...rows.map(r => r.join(','))].join('\n');
                const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = 'tabla_cpm_pert.csv';
                link.click();
              }}
              className="btn-ghost text-xs text-text-secondary hover:text-text-primary border border-surface-4"
            >
              Descargar CSV
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse font-mono">
              <thead>
                <tr className="bg-surface-3/80 border-b border-surface-4 text-text-secondary font-semibold font-sans">
                  <th className="py-2.5 px-3">Cód</th>
                  <th className="py-2.5 px-3">Actividad</th>
                  <th className="py-2.5 px-2 text-center">Pred.</th>
                  <th className="py-2.5 px-2 text-center">a</th>
                  <th className="py-2.5 px-2 text-center">m</th>
                  <th className="py-2.5 px-2 text-center">b</th>
                  <th className="py-2.5 px-2 text-center text-accent-light">te</th>
                  <th className="py-2.5 px-2 text-center">σ²</th>
                  <th className="py-2.5 px-2 text-center bg-surface-1/40">ES</th>
                  <th className="py-2.5 px-2 text-center bg-surface-1/40">EF</th>
                  <th className="py-2.5 px-2 text-center bg-surface-2/40">LS</th>
                  <th className="py-2.5 px-2 text-center bg-surface-2/40">LF</th>
                  <th className="py-2.5 px-2 text-center text-warn-light">Holgura</th>
                  <th className="py-2.5 px-3 text-center">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-4/40">
                {cpmResult.rows.map((row) => (
                  <tr
                    key={row.id}
                    className={`transition-colors ${
                      row.isCritical
                        ? 'bg-critical/5 hover:bg-critical/10 text-text-primary'
                        : 'hover:bg-surface-3/30 text-text-secondary'
                    }`}
                  >
                    <td className="py-2.5 px-3 font-bold text-accent-light">{row.code}</td>
                    <td className="py-2.5 px-3 font-sans font-medium text-text-primary truncate max-w-xs">
                      {row.name}
                    </td>
                    <td className="py-2.5 px-2 text-center text-text-muted">
                      {row.predecessors.join(', ') || '—'}
                    </td>
                    <td className="py-2.5 px-2 text-center">{row.optimistic}</td>
                    <td className="py-2.5 px-2 text-center">{row.mostLikely}</td>
                    <td className="py-2.5 px-2 text-center">{row.pessimistic}</td>
                    <td className="py-2.5 px-2 text-center font-bold text-accent-light">
                      {row.te.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-2 text-center text-text-muted">{row.variance.toFixed(3)}</td>
                    <td className="py-2.5 px-2 text-center bg-surface-1/20">{row.es.toFixed(2)}</td>
                    <td className="py-2.5 px-2 text-center bg-surface-1/20">{row.ef.toFixed(2)}</td>
                    <td className="py-2.5 px-2 text-center bg-surface-2/20">{row.ls.toFixed(2)}</td>
                    <td className="py-2.5 px-2 text-center bg-surface-2/20">{row.lf.toFixed(2)}</td>
                    <td className="py-2.5 px-2 text-center font-bold">
                      {row.totalSlack === 0 ? (
                        <span className="text-critical-light">0.00</span>
                      ) : (
                        <span className="text-warn-light">{row.totalSlack.toFixed(2)}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center font-sans">
                      {row.isCritical ? (
                        <span className="badge-critical text-3xs font-mono font-bold">CRÍTICA</span>
                      ) : (
                        <span className="text-2xs text-text-muted">Holgura</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Probability & Risk */}
      {activeTab === 'prob' && (
        <div className="card p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-4/60 pb-4">
            <div>
              <h2 className="text-sm font-semibold text-text-primary">
                Análisis de Probabilidad y Riesgo Estadístico
              </h2>
              <p className="text-2xs text-text-muted mt-0.5">
                P(T ≤ Plazo) evaluado con la distribución normal estándar Z = (Plazo - Te) / σ sobre la ruta crítica.
              </p>
            </div>

            {/* Target Deadline Input */}
            <div className="flex items-center gap-3">
              <label className="text-xs text-text-secondary whitespace-nowrap">
                Plazo Objetivo (días):
              </label>
              <input
                type="number"
                step="0.5"
                min="1"
                value={targetDeadline}
                onChange={(e) => setTargetDeadline(parseFloat(e.target.value) || 0)}
                className="input-field w-24 text-center font-mono font-bold text-accent-light"
              />
            </div>
          </div>

          {/* Probability Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card p-4 bg-surface-1 border-surface-4/60 text-center space-y-1">
              <span className="text-2xs uppercase tracking-wider text-text-muted font-medium">
                Probabilidad de Cumplimiento
              </span>
              <div
                className={`text-3xl font-mono font-bold ${
                  prob.probability >= 0.8
                    ? 'text-success-light'
                    : prob.probability >= 0.5
                    ? 'text-warn-light'
                    : 'text-critical-light'
                }`}
              >
                {(prob.probability * 100).toFixed(1)}%
              </div>
              <p className="text-2xs text-text-muted">
                {prob.probability >= 0.8
                  ? 'Compromiso altamente viable con colchón de seguridad'
                  : prob.probability >= 0.5
                  ? 'Viable pero vulnerable a demoras en ruta crítica'
                  : 'Alto riesgo de incumplimiento; requiere compresión'}
              </p>
            </div>

            <div className="card p-4 bg-surface-1 border-surface-4/60 text-center space-y-1">
              <span className="text-2xs uppercase tracking-wider text-text-muted font-medium">
                Desviación Estándar (Z)
              </span>
              <div className="text-3xl font-mono font-bold text-accent-light">
                {prob.z.toFixed(2)} σ
              </div>
              <p className="text-2xs text-text-muted">
                Unidades de desviación respecto a la media de {cpmResult.duration.toFixed(1)} días
              </p>
            </div>

            <div className="card p-4 bg-surface-1 border-surface-4/60 text-center space-y-1">
              <span className="text-2xs uppercase tracking-wider text-text-muted font-medium">
                Margen Temporal
              </span>
              <div className="text-3xl font-mono font-bold text-text-primary">
                {prob.slackVsDeadline >= 0 ? `+${prob.slackVsDeadline.toFixed(1)}` : prob.slackVsDeadline.toFixed(1)} d
              </div>
              <p className="text-2xs text-text-muted">
                Diferencia contra la duración esperada {cpmResult.duration.toFixed(1)} días
              </p>
            </div>
          </div>

          {/* Pure SVG Gaussian Bell Curve */}
          <div className="py-4 flex justify-center">
            <GaussianBellCurve
              mean={cpmResult.duration}
              sigma={cpmResult.sigma}
              deadline={targetDeadline}
              probability={prob.probability}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Pure SVG Network Diagram ──────────────────────────────────────────────────
function NetworkDiagramSVG({ cpmResult }: { cpmResult: { rows: ComputedActivity[]; criticalPath: string[] } }) {
  const { rows, criticalPath } = cpmResult;

  // Compute depth (layer) for each activity based on predecessors
  const levels = useMemo(() => {
    const depths = new Map<string, number>();
    rows.forEach((r) => depths.set(r.id, 0));

    // Multiple passes to resolve depth
    for (let i = 0; i < rows.length; i++) {
      rows.forEach((r) => {
        let maxPredDepth = -1;
        r.predecessors.forEach((p) => {
          if (depths.has(p)) {
            maxPredDepth = Math.max(maxPredDepth, depths.get(p)!);
          }
        });
        depths.set(r.id, maxPredDepth + 1);
      });
    }

    // Group into columns
    const columns: ComputedActivity[][] = [];
    rows.forEach((r) => {
      const d = depths.get(r.id) || 0;
      if (!columns[d]) columns[d] = [];
      columns[d].push(r);
    });

    return columns;
  }, [rows]);

  const nodeWidth = 120;
  const nodeHeight = 54;
  const colGap = 80;
  const rowGap = 40;

  const totalCols = levels.length;
  const maxRowsInCol = Math.max(...levels.map((c) => c.length), 1);

  const svgWidth = Math.max(780, totalCols * (nodeWidth + colGap) + 80);
  const svgHeight = Math.max(380, maxRowsInCol * (nodeHeight + rowGap) + 60);

  // Calculate coordinates for each node
  const nodeCoords = useMemo(() => {
    const coords = new Map<string, { x: number; y: number }>();
    levels.forEach((col, colIdx) => {
      const colHeight = col.length * (nodeHeight + rowGap) - rowGap;
      const startY = (svgHeight - colHeight) / 2;

      col.forEach((act, rowIdx) => {
        const x = 50 + colIdx * (nodeWidth + colGap);
        const y = startY + rowIdx * (nodeHeight + rowGap);
        coords.set(act.id, { x, y });
      });
    });
    return coords;
  }, [levels, svgHeight]);

  const criticalSet = new Set(criticalPath);

  return (
    <svg width={svgWidth} height={svgHeight} className="overflow-visible font-sans select-none">
      <defs>
        <marker
          id="arrow-normal"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#3f3f46" />
        </marker>
        <marker
          id="arrow-critical"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
        </marker>
      </defs>

      {/* Render Edges */}
      {rows.map((target) => {
        const targetPos = nodeCoords.get(target.id);
        if (!targetPos) return null;

        return target.predecessors.map((predId) => {
          const sourcePos = nodeCoords.get(predId);
          if (!sourcePos) return null;

          const isCriticalEdge =
            criticalSet.has(predId) && criticalSet.has(target.id) && target.isCritical;

          const startX = sourcePos.x + nodeWidth;
          const startY = sourcePos.y + nodeHeight / 2;
          const endX = targetPos.x;
          const endY = targetPos.y + nodeHeight / 2;

          const midX = (startX + endX) / 2;
          const pathD = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;

          return (
            <path
              key={`${predId}->${target.id}`}
              d={pathD}
              fill="none"
              stroke={isCriticalEdge ? '#ef4444' : '#3f3f46'}
              strokeWidth={isCriticalEdge ? 2.5 : 1.2}
              markerEnd={isCriticalEdge ? 'url(#arrow-critical)' : 'url(#arrow-normal)'}
              strokeDasharray={isCriticalEdge ? undefined : undefined}
            />
          );
        });
      })}

      {/* Render Nodes */}
      {rows.map((act) => {
        const pos = nodeCoords.get(act.id);
        if (!pos) return null;

        const isCrit = act.isCritical;

        return (
          <g key={act.id} transform={`translate(${pos.x}, ${pos.y})`}>
            {/* Box */}
            <rect
              width={nodeWidth}
              height={nodeHeight}
              rx={8}
              fill={isCrit ? '#1c1012' : '#18181b'}
              stroke={isCrit ? '#ef4444' : '#27272a'}
              strokeWidth={isCrit ? 2 : 1}
              className="transition-all"
            />

            {/* Header: Code & te */}
            <text x="10" y="18" fill={isCrit ? '#f87171' : '#818cf8'} fontSize="11" fontWeight="bold" fontFamily="monospace">
              {act.code}
            </text>
            <text x={nodeWidth - 10} y="18" fill="#a1a1aa" fontSize="10" fontFamily="monospace" textAnchor="end">
              {act.te.toFixed(1)}d
            </text>

            {/* Name */}
            <text x="10" y="34" fill="#fafafa" fontSize="10" fontWeight="500">
              {act.name.length > 14 ? act.name.slice(0, 13) + '…' : act.name}
            </text>

            {/* ES/EF Footer */}
            <text x="10" y="47" fill="#71717a" fontSize="8" fontFamily="monospace">
              ES:{act.es.toFixed(0)} EF:{act.ef.toFixed(0)}
            </text>
            <text x={nodeWidth - 10} y="47" fill={act.totalSlack === 0 ? '#ef4444' : '#f59e0b'} fontSize="8" fontFamily="monospace" textAnchor="end">
              H:{act.totalSlack.toFixed(0)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Pure HTML/CSS Gantt Chart ─────────────────────────────────────────────────
function GanttChartHTML({ cpmResult }: { cpmResult: { rows: ComputedActivity[]; duration: number } }) {
  const { rows, duration } = cpmResult;
  const maxTime = Math.max(duration, 1);

  return (
    <div className="space-y-2 font-mono text-xs">
      {/* Time Scale Header */}
      <div className="flex items-center text-3xs text-text-muted border-b border-surface-4 pb-1 pl-48 pr-4">
        <span className="w-1/4">0d</span>
        <span className="w-1/4 text-center">{(maxTime * 0.25).toFixed(0)}d</span>
        <span className="w-1/4 text-center">{(maxTime * 0.5).toFixed(0)}d</span>
        <span className="w-1/4 text-center">{(maxTime * 0.75).toFixed(0)}d</span>
        <span className="text-right">Fin: {maxTime.toFixed(0)}d</span>
      </div>

      {/* Activity Bars */}
      <div className="space-y-1.5 max-h-96 overflow-y-auto pr-2">
        {rows.map((row) => {
          const leftPct = (row.es / maxTime) * 100;
          const widthPct = Math.max((row.te / maxTime) * 100, 1.5);
          const slackPct = (row.totalSlack / maxTime) * 100;

          return (
            <div key={row.id} className="flex items-center gap-3 py-1 hover:bg-surface-3/30 rounded px-1">
              {/* Activity Label */}
              <div className="w-44 flex items-center justify-between text-2xs truncate shrink-0 font-sans">
                <span className="font-mono font-bold text-accent-light mr-1.5">{row.code}</span>
                <span className="text-text-primary truncate flex-1">{row.name}</span>
                {row.isCritical && (
                  <span className="text-critical-light font-mono font-bold text-3xs ml-1">●</span>
                )}
              </div>

              {/* Bar track */}
              <div className="flex-1 bg-surface-1/80 h-5 rounded relative overflow-hidden border border-surface-4/40">
                {/* Duration bar */}
                <div
                  className={`absolute top-0 bottom-0 rounded flex items-center justify-center text-3xs font-bold text-white transition-all ${
                    row.isCritical
                      ? 'bg-critical shadow-sm'
                      : 'bg-accent/80 hover:bg-accent'
                  }`}
                  style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                  title={`${row.name}: ES=${row.es.toFixed(1)}, EF=${row.ef.toFixed(1)}, te=${row.te.toFixed(1)}`}
                >
                  {row.te >= 2 && `${row.te.toFixed(1)}d`}
                </div>

                {/* Slack extension line */}
                {row.totalSlack > 0 && (
                  <div
                    className="absolute top-1/2 -translate-y-1/2 h-1 border-b border-dashed border-warn-light/70"
                    style={{ left: `${leftPct + widthPct}%`, width: `${slackPct}%` }}
                    title={`Holgura Total: ${row.totalSlack.toFixed(1)} días`}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Pure SVG Gaussian Bell Curve ──────────────────────────────────────────────
function GaussianBellCurve({
  mean,
  sigma,
  deadline,
  probability,
}: {
  mean: number;
  sigma: number;
  deadline: number;
  probability: number;
}) {
  const width = 560;
  const height = 180;
  const padding = 40;

  const effSigma = Math.max(sigma, 0.5);
  const minX = mean - 3.5 * effSigma;
  const maxX = mean + 3.5 * effSigma;

  const points: { x: number; y: number }[] = [];
  const numSteps = 80;

  for (let i = 0; i <= numSteps; i++) {
    const val = minX + (i / numSteps) * (maxX - minX);
    const z = (val - mean) / effSigma;
    const yVal = Math.exp(-0.5 * z * z); // normal distribution peak

    const svgX = padding + ((val - minX) / (maxX - minX)) * (width - 2 * padding);
    const svgY = height - padding - yVal * (height - 2 * padding);
    points.push({ x: svgX, y: svgY });
  }

  const pathD = `M ${points.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' L ')}`;

  // Shaded area under the curve up to deadline
  const deadlineSvgX =
    padding + (Math.max(minX, Math.min(deadline, maxX)) - minX) / (maxX - minX) * (width - 2 * padding);

  const shadedPoints = points.filter((p) => p.x <= deadlineSvgX);
  const shadedPathD =
    shadedPoints.length > 0
      ? `M ${shadedPoints[0].x} ${height - padding} L ${shadedPoints
          .map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
          .join(' L ')} L ${deadlineSvgX} ${height - padding} Z`
      : '';

  const meanSvgX = padding + ((mean - minX) / (maxX - minX)) * (width - 2 * padding);

  return (
    <svg width={width} height={height} className="select-none font-sans overflow-visible">
      {/* Shaded probability region */}
      {shadedPathD && (
        <path
          d={shadedPathD}
          fill={probability >= 0.8 ? '#22c55e' : probability >= 0.5 ? '#f59e0b' : '#ef4444'}
          fillOpacity="0.2"
        />
      )}

      {/* Axis baseline */}
      <line
        x1={padding}
        y1={height - padding}
        x2={width - padding}
        y2={height - padding}
        stroke="#3f3f46"
        strokeWidth="1"
      />

      {/* Bell curve line */}
      <path d={pathD} fill="none" stroke="#6366f1" strokeWidth="2.5" />

      {/* Mean Marker */}
      <line
        x1={meanSvgX}
        y1={padding}
        x2={meanSvgX}
        y2={height - padding}
        stroke="#6366f1"
        strokeDasharray="3 3"
      />
      <text
        x={meanSvgX}
        y={height - padding + 15}
        fill="#a1a1aa"
        fontSize="10"
        fontFamily="monospace"
        textAnchor="middle"
      >
        Te = {mean.toFixed(1)}d
      </text>

      {/* Deadline Marker */}
      <line
        x1={deadlineSvgX}
        y1={padding}
        x2={deadlineSvgX}
        y2={height - padding}
        stroke="#ef4444"
        strokeWidth="2"
      />
      <text
        x={deadlineSvgX}
        y={height - padding + 15}
        fill="#f87171"
        fontSize="10"
        fontWeight="bold"
        fontFamily="monospace"
        textAnchor="middle"
      >
        Plazo: {deadline}d
      </text>
    </svg>
  );
}
