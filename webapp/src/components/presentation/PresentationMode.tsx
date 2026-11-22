import React, { useState } from 'react';
import { useProjectStore } from '../../store/useProjectStore';
import { probabilityOfSuccess } from '../../engine/probability';
import KPICard from '../ui/KPICard';

export default function PresentationMode() {
  const project = useProjectStore((s) => s.project);
  const cpmResult = useProjectStore((s) => s.cpmResult);
  const togglePresentationMode = useProjectStore((s) => s.togglePresentationMode);

  const [activeView, setActiveView] = useState<'network' | 'gantt'>('network');

  if (!cpmResult || cpmResult.rows.length === 0) {
    return (
      <div className="fixed inset-0 z-50 bg-surface-0 flex flex-col items-center justify-center p-6 space-y-4">
        <h2 className="text-xl font-bold text-text-primary">Red no calculada</h2>
        <p className="text-sm text-text-muted">Genera la red en el editor antes de iniciar la presentación.</p>
        <button onClick={togglePresentationMode} className="btn-primary">
          Regresar al Editor
        </button>
      </div>
    );
  }

  const prob = probabilityOfSuccess(cpmResult, Math.ceil(cpmResult.duration));
  const totalCost = project.activities.reduce((s, a) => s + (a.cost || 0), 0);
  const criticalCount = cpmResult.criticalActivities.length;

  return (
    <div className="fixed inset-0 z-50 bg-surface-0 text-text-primary flex flex-col overflow-hidden select-none animate-fade-in font-sans">
      {/* Top Presentation Bar */}
      <header className="h-16 px-8 border-b border-surface-4/60 bg-surface-1/90 backdrop-blur flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-9 h-9 rounded-lg bg-accent/20 border border-accent/40 flex items-center justify-center text-accent font-mono font-bold text-base">
            CPM
          </div>
          <div>
            <h1 className="text-base font-bold text-text-primary tracking-tight">
              {project.name || 'Defensa de Planificación PERT/CPM'}
            </h1>
            <p className="text-2xs font-mono text-text-muted">
              Duración Esperada: {cpmResult.duration.toFixed(1)} días · Desviación: ±{cpmResult.sigma.toFixed(2)}d
            </p>
          </div>
        </div>

        {/* View Switcher in Presentation */}
        <div className="flex items-center gap-3">
          <div className="flex bg-surface-2 p-1 rounded-lg border border-surface-4">
            <button
              onClick={() => setActiveView('network')}
              className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all ${
                activeView === 'network'
                  ? 'bg-accent text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Diagrama de Red
            </button>
            <button
              onClick={() => setActiveView('gantt')}
              className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all ${
                activeView === 'gantt'
                  ? 'bg-accent text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Cronograma Gantt
            </button>
          </div>

          <button
            onClick={togglePresentationMode}
            className="btn-secondary text-xs flex items-center gap-1.5 px-3 py-1.5 border border-surface-4 hover:border-text-secondary"
            title="Presiona ESC o clic para salir"
          >
            <span>✕</span>
            <span>Salir (ESC)</span>
          </button>
        </div>
      </header>

      {/* Main Presentation Stage */}
      <div className="flex-1 p-6 grid grid-cols-12 gap-6 overflow-hidden">
        {/* Visual Stage: Network or Gantt (9 cols) */}
        <div className="col-span-12 lg:col-span-9 card p-6 bg-surface-1/60 border-surface-4/80 flex flex-col justify-between overflow-hidden">
          <div className="flex items-center justify-between border-b border-surface-4/60 pb-3 shrink-0">
            <span className="text-xs font-bold uppercase tracking-wider text-text-secondary">
              {activeView === 'network' ? 'Ruta Crítica en Grafo de Red (AON)' : 'Cronograma y Holguras (Gantt)'}
            </span>
            <span className="text-xs font-mono text-critical-light font-semibold">
              Ruta: {cpmResult.criticalPath.join(' → ')}
            </span>
          </div>

          {/* Visualization Canvas */}
          <div className="flex-1 overflow-auto py-4 flex items-center justify-center">
            {activeView === 'network' ? (
              <PresentationNetworkSVG cpmResult={cpmResult} />
            ) : (
              <PresentationGantt cpmResult={cpmResult} />
            )}
          </div>

          {/* Bottom Critical Chain Ticker */}
          <div className="pt-3 border-t border-surface-4/60 flex items-center justify-between shrink-0 text-xs">
            <div className="flex items-center gap-2 overflow-x-auto py-1">
              <span className="text-2xs font-mono uppercase text-critical-light font-bold">Secuencia Crítica:</span>
              {cpmResult.criticalPath.map((actId, idx) => {
                const act = cpmResult.rows.find((r) => r.id === actId);
                return (
                  <React.Fragment key={actId}>
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-critical/15 text-critical-light border border-critical/30 font-mono text-xs font-semibold">
                      {act?.code || actId} ({act?.te.toFixed(1)}d)
                    </span>
                    {idx < cpmResult.criticalPath.length - 1 && (
                      <span className="text-text-muted font-mono">→</span>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
            <span className="text-2xs font-mono text-text-muted hidden sm:block">
              {cpmResult.criticalPath.length} actividades críticas
            </span>
          </div>
        </div>

        {/* Strategic KPIs & Highlights (3 cols) */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4 overflow-y-auto">
          {/* Main Strategic KPIs */}
          <div className="space-y-3">
            <KPICard
              label="Duración Crítica Total"
              value={`${cpmResult.duration.toFixed(1)} d`}
              subtext={`Varianza acumulada σ² = ${cpmResult.variance.toFixed(2)}`}
              color="accent"
            />
            <KPICard
              label="Presupuesto Estimado"
              value={`$${totalCost.toLocaleString('en-US')}`}
              subtext={`${cpmResult.rows.length} actividades programadas`}
              color="neutral"
            />
            <KPICard
              label="Impacto Crítico"
              value={`${criticalCount} de ${cpmResult.rows.length}`}
              subtext={`${((criticalCount / (cpmResult.rows.length || 1)) * 100).toFixed(0)}% sin holgura permitida`}
              color="critical"
            />
            <KPICard
              label="Probabilidad en Plazo"
              value={`${(prob.probability * 100).toFixed(0)}%`}
              subtext={`Z = ${prob.z.toFixed(2)} σ`}
              color="success"
            />
          </div>

          {/* Live Defense Key Takeaway Card */}
          <div className="card p-4 bg-gradient-to-br from-surface-2 to-surface-1 border-accent/20 space-y-2.5 flex-1">
            <span className="text-2xs font-bold uppercase tracking-wider text-accent-light">
              Dictamen para Defensa
            </span>
            <p className="text-xs text-text-secondary leading-relaxed">
              El proyecto cuenta con una ruta crítica de <strong className="text-text-primary">{cpmResult.criticalPath.length} actividades consecutivas</strong>. 
              Cualquier retraso en esta cadena desplaza directamente la entrega final más allá de los <strong className="text-accent-light">{cpmResult.duration.toFixed(1)} días</strong>.
            </p>
            <div className="pt-2 border-t border-surface-4/40 space-y-1 text-2xs text-text-muted">
              <div className="flex justify-between">
                <span>Desviación estándar:</span>
                <span className="font-mono text-text-primary font-bold">±{cpmResult.sigma.toFixed(2)} días</span>
              </div>
              <div className="flex justify-between">
                <span>Intervalo de confianza (95%):</span>
                <span className="font-mono text-text-primary font-bold">
                  {(cpmResult.duration - 1.96 * cpmResult.sigma).toFixed(1)} - {(cpmResult.duration + 1.96 * cpmResult.sigma).toFixed(1)} d
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Network Diagram for Presentation ──────────────────────────────────────────
function PresentationNetworkSVG({ cpmResult }: { cpmResult: any }) {
  const { rows, criticalPath } = cpmResult;

  // Compute depth
  const depths = new Map<string, number>();
  rows.forEach((r: any) => depths.set(r.id, 0));
  for (let i = 0; i < rows.length; i++) {
    rows.forEach((r: any) => {
      let maxPredDepth = -1;
      r.predecessors.forEach((p: string) => {
        if (depths.has(p)) maxPredDepth = Math.max(maxPredDepth, depths.get(p)!);
      });
      depths.set(r.id, maxPredDepth + 1);
    });
  }

  const columns: any[][] = [];
  rows.forEach((r: any) => {
    const d = depths.get(r.id) || 0;
    if (!columns[d]) columns[d] = [];
    columns[d].push(r);
  });

  const nodeWidth = 140;
  const nodeHeight = 60;
  const colGap = 90;
  const rowGap = 45;

  const totalCols = columns.length;
  const maxRowsInCol = Math.max(...columns.map((c) => c.length), 1);

  const svgWidth = Math.max(840, totalCols * (nodeWidth + colGap) + 80);
  const svgHeight = Math.max(420, maxRowsInCol * (nodeHeight + rowGap) + 60);

  const coords = new Map<string, { x: number; y: number }>();
  columns.forEach((col, colIdx) => {
    const colHeight = col.length * (nodeHeight + rowGap) - rowGap;
    const startY = (svgHeight - colHeight) / 2;
    col.forEach((act, rowIdx) => {
      const x = 50 + colIdx * (nodeWidth + colGap);
      const y = startY + rowIdx * (nodeHeight + rowGap);
      coords.set(act.id, { x, y });
    });
  });

  const criticalSet = new Set(criticalPath);

  return (
    <svg width={svgWidth} height={svgHeight} className="overflow-visible select-none">
      <defs>
        <marker id="pres-arrow-normal" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#3f3f46" />
        </marker>
        <marker id="pres-arrow-critical" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
        </marker>
      </defs>

      {/* Edges */}
      {rows.map((target: any) => {
        const targetPos = coords.get(target.id);
        if (!targetPos) return null;

        return target.predecessors.map((predId: string) => {
          const sourcePos = coords.get(predId);
          if (!sourcePos) return null;

          const isCriticalEdge = criticalSet.has(predId) && criticalSet.has(target.id) && target.isCritical;
          const startX = sourcePos.x + nodeWidth;
          const startY = sourcePos.y + nodeHeight / 2;
          const endX = targetPos.x;
          const endY = targetPos.y + nodeHeight / 2;
          const midX = (startX + endX) / 2;

          return (
            <path
              key={`${predId}->${target.id}`}
              d={`M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`}
              fill="none"
              stroke={isCriticalEdge ? '#ef4444' : '#3f3f46'}
              strokeWidth={isCriticalEdge ? 3 : 1.2}
              markerEnd={isCriticalEdge ? 'url(#pres-arrow-critical)' : 'url(#pres-arrow-normal)'}
            />
          );
        });
      })}

      {/* Nodes */}
      {rows.map((act: any) => {
        const pos = coords.get(act.id);
        if (!pos) return null;
        const isCrit = act.isCritical;

        return (
          <g key={act.id} transform={`translate(${pos.x}, ${pos.y})`}>
            <rect
              width={nodeWidth}
              height={nodeHeight}
              rx={10}
              fill={isCrit ? '#241013' : '#18181b'}
              stroke={isCrit ? '#ef4444' : '#27272a'}
              strokeWidth={isCrit ? 2.5 : 1}
            />
            <text x="12" y="20" fill={isCrit ? '#f87171' : '#818cf8'} fontSize="13" fontWeight="bold" fontFamily="monospace">
              {act.code}
            </text>
            <text x={nodeWidth - 12} y="20" fill="#a1a1aa" fontSize="11" fontFamily="monospace" textAnchor="end">
              {act.te.toFixed(1)}d
            </text>
            <text x="12" y="38" fill="#fafafa" fontSize="11" fontWeight="600">
              {act.name.length > 15 ? act.name.slice(0, 14) + '…' : act.name}
            </text>
            <text x="12" y="52" fill="#71717a" fontSize="9" fontFamily="monospace">
              ES:{act.es.toFixed(0)} EF:{act.ef.toFixed(0)}
            </text>
            <text x={nodeWidth - 12} y="52" fill={act.totalSlack === 0 ? '#ef4444' : '#f59e0b'} fontSize="9" fontFamily="monospace" textAnchor="end">
              H:{act.totalSlack.toFixed(0)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Gantt for Presentation ────────────────────────────────────────────────────
function PresentationGantt({ cpmResult }: { cpmResult: any }) {
  const { rows, duration } = cpmResult;
  const maxTime = Math.max(duration, 1);

  return (
    <div className="w-full max-w-4xl space-y-2.5 font-mono text-xs">
      <div className="flex items-center text-3xs text-text-muted border-b border-surface-4 pb-1 pl-48 pr-4">
        <span className="w-1/4">0d</span>
        <span className="w-1/4 text-center">{(maxTime * 0.25).toFixed(0)}d</span>
        <span className="w-1/4 text-center">{(maxTime * 0.5).toFixed(0)}d</span>
        <span className="w-1/4 text-center">{(maxTime * 0.75).toFixed(0)}d</span>
        <span className="text-right">Fin: {maxTime.toFixed(0)}d</span>
      </div>

      <div className="space-y-2 max-h-[380px] overflow-y-auto pr-2">
        {rows.map((row: any) => {
          const leftPct = (row.es / maxTime) * 100;
          const widthPct = Math.max((row.te / maxTime) * 100, 2);
          const slackPct = (row.totalSlack / maxTime) * 100;

          return (
            <div key={row.id} className="flex items-center gap-3 py-1">
              <div className="w-44 flex items-center justify-between text-xs font-sans shrink-0">
                <span className="font-mono font-bold text-accent-light mr-1.5">{row.code}</span>
                <span className="text-text-primary truncate flex-1">{row.name}</span>
                {row.isCritical && (
                  <span className="badge-critical text-3xs ml-1 font-mono">CRÍTICA</span>
                )}
              </div>

              <div className="flex-1 bg-surface-2/80 h-6 rounded relative overflow-hidden border border-surface-4/40">
                <div
                  className={`absolute top-0 bottom-0 rounded flex items-center justify-center text-3xs font-bold text-white ${
                    row.isCritical ? 'bg-critical shadow-sm' : 'bg-accent/80'
                  }`}
                  style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                >
                  {row.te >= 1.5 && `${row.te.toFixed(1)}d`}
                </div>
                {row.totalSlack > 0 && (
                  <div
                    className="absolute top-1/2 -translate-y-1/2 h-1 border-b border-dashed border-warn-light/80"
                    style={{ left: `${leftPct + widthPct}%`, width: `${slackPct}%` }}
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
