import React, { useState } from 'react';
import { useProjectStore } from '../../store/useProjectStore';
import type { ComputedActivity } from '../../types';

export default function VerifyStep() {
  const cpmResult = useProjectStore((s) => s.cpmResult);
  const manualEntries = useProjectStore((s) => s.manualEntries);
  const comparisons = useProjectStore((s) => s.comparisons);
  const setManualEntry = useProjectStore((s) => s.setManualEntry);
  const compareManual = useProjectStore((s) => s.compareManual);
  const clearManualEntries = useProjectStore((s) => s.clearManualEntries);
  const markStepComplete = useProjectStore((s) => s.markStepComplete);
  const setStep = useProjectStore((s) => s.setStep);

  const [hasCompared, setHasCompared] = useState(false);

  if (!cpmResult || cpmResult.rows.length === 0) {
    return (
      <div className="card p-8 text-center max-w-xl mx-auto my-12 space-y-4">
        <div className="text-3xl">⚠</div>
        <h2 className="text-lg font-bold text-text-primary">Red no calculada</h2>
        <p className="text-sm text-text-muted">
          Debes definir al menos dos actividades y generar la red en el Paso 2 antes de realizar la verificación de cálculos manuales.
        </p>
        <button onClick={() => setStep('network')} className="btn-primary">
          Ir a Red PERT/CPM →
        </button>
      </div>
    );
  }

  const rows = cpmResult.rows;

  // Auto-fill button for testing/demonstration
  const handleAutoFill = () => {
    rows.forEach((row) => {
      setManualEntry(row.id, 'es', row.es);
      setManualEntry(row.id, 'ef', row.ef);
      setManualEntry(row.id, 'ls', row.ls);
      setManualEntry(row.id, 'lf', row.lf);
      setManualEntry(row.id, 'totalSlack', row.totalSlack);
    });
    setHasCompared(false);
  };

  const handleRunComparison = () => {
    compareManual();
    setHasCompared(true);
    markStepComplete('verify');
  };

  // Find comparison for a given activity and field
  const getFieldComparison = (activityId: string, field: string) => {
    return comparisons.find((c) => c.activityId === activityId && c.field === field);
  };

  // Get manual value from store
  const getManualVal = (activityId: string, field: 'es' | 'ef' | 'ls' | 'lf' | 'totalSlack'): string => {
    const entry = manualEntries.find((e) => e.activityId === activityId);
    if (!entry) return '';
    const val = entry[field];
    return val === null || val === undefined ? '' : String(val);
  };

  // Stats calculation
  const totalCompared = comparisons.length;
  const correctCount = comparisons.filter((c) => c.isCorrect).length;
  const accuracy = totalCompared > 0 ? Math.round((correctCount / totalCompared) * 100) : null;

  return (
    <div className="space-y-6">
      {/* Step Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <span>Solución Manual vs. Motor Matemático</span>
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Ingresa tus cálculos manuales de pasada hacia adelante (ES, EF), hacia atrás (LS, LF) y holguras para contrastarlos visualmente contra el algoritmo.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleAutoFill}
            className="btn-secondary text-xs"
            title="Rellena automáticamente los campos con los valores calculados por el motor para agilizar pruebas"
          >
            ⚡ Auto-llenar
          </button>
          <button
            onClick={() => {
              clearManualEntries();
              setHasCompared(false);
            }}
            className="btn-ghost text-xs text-text-muted hover:text-text-primary"
          >
            Limpiar
          </button>
          <button
            onClick={handleRunComparison}
            className="btn-primary text-xs flex items-center gap-1.5"
          >
            <span>⚖</span>
            <span>Comparar Cálculos</span>
          </button>
        </div>
      </div>

      {/* Comparison Scorecard Banner */}
      {hasCompared && (
        <div className="card p-4 bg-surface-2 border-surface-4 flex flex-wrap items-center justify-between gap-4 animate-fade-in">
          <div className="flex items-center gap-4">
            <div
              className={`w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold font-mono ${
                accuracy === 100
                  ? 'bg-success/20 text-success-light border border-success/30'
                  : accuracy && accuracy >= 70
                  ? 'bg-warn/20 text-warn-light border border-warn/30'
                  : 'bg-critical/20 text-critical-light border border-critical/30'
              }`}
            >
              {accuracy}%
            </div>
            <div>
              <h3 className="text-sm font-semibold text-text-primary">
                {accuracy === 100
                  ? '¡Cálculos Manuales 100% Exactos!'
                  : accuracy && accuracy >= 70
                  ? 'Cálculos mayormente correctos con discrepancias leves'
                  : 'Se detectaron discrepancias significativas'}
              </h3>
              <p className="text-xs text-text-muted mt-0.5">
                {correctCount} de {totalCompared} campos verificados coinciden con la tolerancia matemática (&lt; 0.01).
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1 text-success-light">
              <span className="w-2 h-2 rounded-full bg-success" /> {correctCount} Correctos
            </span>
            <span className="flex items-center gap-1 text-critical-light">
              <span className="w-2 h-2 rounded-full bg-critical" /> {totalCompared - correctCount} Discrepancias
            </span>
            <button
              onClick={() => {
                markStepComplete('verify');
                setStep('test-cases');
              }}
              className="btn-secondary text-xs ml-2"
            >
              Continuar a Casos de Prueba →
            </button>
          </div>
        </div>
      )}

      {/* Verification Matrix Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-surface-3/80 border-b border-surface-4 text-text-secondary font-semibold">
                <th className="py-2.5 px-3">Actividad</th>
                <th className="py-2.5 px-2 text-center">Duración (te)</th>
                <th className="py-2.5 px-2 text-center bg-surface-1/40">ES Manual</th>
                <th className="py-2.5 px-2 text-center bg-surface-1/40">EF Manual</th>
                <th className="py-2.5 px-2 text-center bg-surface-2/40">LS Manual</th>
                <th className="py-2.5 px-2 text-center bg-surface-2/40">LF Manual</th>
                <th className="py-2.5 px-2 text-center bg-surface-1/40">Holgura Manual</th>
                <th className="py-2.5 px-3 text-right">Referencia Algoritmo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-4/40 font-mono">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-surface-3/30 transition-colors">
                  {/* Activity Info */}
                  <td className="py-2.5 px-3 font-sans">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-accent-light font-semibold">{row.code}</span>
                      <span className="text-text-primary text-xs font-medium">{row.name}</span>
                      {row.isCritical && (
                        <span className="badge-critical text-3xs font-mono">CRÍTICA</span>
                      )}
                    </div>
                  </td>

                  {/* te */}
                  <td className="py-2.5 px-2 text-center text-text-muted">
                    {row.te.toFixed(2)}
                  </td>

                  {/* ES Manual Input */}
                  <td className="py-2 px-1 text-center bg-surface-1/20">
                    <InputField
                      activityId={row.id}
                      field="es"
                      value={getManualVal(row.id, 'es')}
                      comp={getFieldComparison(row.id, 'es')}
                      hasCompared={hasCompared}
                      onChange={(val) => setManualEntry(row.id, 'es', val)}
                    />
                  </td>

                  {/* EF Manual Input */}
                  <td className="py-2 px-1 text-center bg-surface-1/20">
                    <InputField
                      activityId={row.id}
                      field="ef"
                      value={getManualVal(row.id, 'ef')}
                      comp={getFieldComparison(row.id, 'ef')}
                      hasCompared={hasCompared}
                      onChange={(val) => setManualEntry(row.id, 'ef', val)}
                    />
                  </td>

                  {/* LS Manual Input */}
                  <td className="py-2 px-1 text-center bg-surface-2/20">
                    <InputField
                      activityId={row.id}
                      field="ls"
                      value={getManualVal(row.id, 'ls')}
                      comp={getFieldComparison(row.id, 'ls')}
                      hasCompared={hasCompared}
                      onChange={(val) => setManualEntry(row.id, 'ls', val)}
                    />
                  </td>

                  {/* LF Manual Input */}
                  <td className="py-2 px-1 text-center bg-surface-2/20">
                    <InputField
                      activityId={row.id}
                      field="lf"
                      value={getManualVal(row.id, 'lf')}
                      comp={getFieldComparison(row.id, 'lf')}
                      hasCompared={hasCompared}
                      onChange={(val) => setManualEntry(row.id, 'lf', val)}
                    />
                  </td>

                  {/* Total Slack Manual Input */}
                  <td className="py-2 px-1 text-center bg-surface-1/20">
                    <InputField
                      activityId={row.id}
                      field="totalSlack"
                      value={getManualVal(row.id, 'totalSlack')}
                      comp={getFieldComparison(row.id, 'totalSlack')}
                      hasCompared={hasCompared}
                      onChange={(val) => setManualEntry(row.id, 'totalSlack', val)}
                    />
                  </td>

                  {/* Engine Target Value Summary */}
                  <td className="py-2.5 px-3 text-right text-2xs text-text-muted">
                    <span title="ES, EF | LS, LF | Holgura calculada por el motor">
                      [{row.es.toFixed(1)}, {row.ef.toFixed(1)}] | [{row.ls.toFixed(1)}, {row.lf.toFixed(1)}] | H:{row.totalSlack.toFixed(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// Subcomponent for input field with color-coded comparison status
function InputField({
  value,
  comp,
  hasCompared,
  onChange,
}: {
  activityId: string;
  field: string;
  value: string;
  comp?: { isCorrect: boolean; computed: number; difference: number };
  hasCompared: boolean;
  onChange: (val: number) => void;
}) {
  let borderClass = 'border-surface-4';
  let bgClass = 'bg-surface-1';

  if (hasCompared && comp) {
    if (comp.isCorrect) {
      borderClass = 'border-success/60 text-success-light font-bold';
      bgClass = 'bg-success/10';
    } else {
      borderClass = 'border-critical/60 text-critical-light font-bold';
      bgClass = 'bg-critical/10';
    }
  }

  return (
    <div className="relative inline-block w-16">
      <input
        type="number"
        step="0.1"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        placeholder="—"
        className={`w-full py-1 px-1.5 text-center text-xs rounded border transition-all ${borderClass} ${bgClass} focus:outline-none focus:ring-1 focus:ring-accent/40`}
      />
      {hasCompared && comp && !comp.isCorrect && (
        <span
          className="absolute -bottom-4 left-1/2 -translate-x-1/2 text-3xs font-mono text-critical-light whitespace-nowrap"
          title={`Valor correcto calculado por el motor: ${comp.computed.toFixed(2)}`}
        >
          {comp.computed.toFixed(1)}
        </span>
      )}
    </div>
  );
}
