import { useProjectStore } from '../../store/useProjectStore';
import type { Activity } from '../../types';
import { useMemo, useCallback } from 'react';

function computeTE(a: number, m: number, b: number): number {
  return (a + 4 * m + b) / 6;
}

function isInvalidEstimate(a: number, m: number, b: number): boolean {
  return a > m || m > b;
}

export default function NetworkStep() {
  const activities = useProjectStore((s) => s.project.activities);
  const addActivity = useProjectStore((s) => s.addActivity);
  const updateActivity = useProjectStore((s) => s.updateActivity);
  const removeActivity = useProjectStore((s) => s.removeActivity);
  const recalculate = useProjectStore((s) => s.recalculate);
  const setStep = useProjectStore((s) => s.setStep);
  const markStepComplete = useProjectStore((s) => s.markStepComplete);

  const handleAdd = useCallback(() => {
    const nextId = `A${activities.length + 1}`;
    addActivity({
      id: nextId,
      name: '',
      predecessors: [],
      optimistic: 0,
      mostLikely: 0,
      pessimistic: 0,
      cost: 0,
    });
  }, [activities.length, addActivity]);

  const handleGenerate = () => {
    recalculate();
    markStepComplete('network');
    setStep('verify');
  };

  const handlePredChange = (id: string, value: string) => {
    const preds = value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    updateActivity(id, { predecessors: preds });
  };

  const stats = useMemo(() => {
    const totalCost = activities.reduce((sum, a) => sum + a.cost, 0);
    const avgTE =
      activities.length > 0
        ? activities.reduce(
            (sum, a) => sum + computeTE(a.optimistic, a.mostLikely, a.pessimistic),
            0,
          ) / activities.length
        : 0;
    return { count: activities.length, totalCost, avgTE };
  }, [activities]);

  return (
    <div className="space-y-6 py-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Red PERT/CPM</h1>
          <p className="text-sm text-text-muted mt-1">
            Define las actividades, sus dependencias y estimaciones de tiempo.
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs text-text-muted">
          <span>
            <strong className="text-text-secondary">{stats.count}</strong>{' '}
            actividades
          </span>
          <span>
            Costo total:{' '}
            <strong className="text-text-secondary">
              ${stats.totalCost.toLocaleString()}
            </strong>
          </span>
          <span>
            TE promedio:{' '}
            <strong className="text-text-secondary">
              {stats.avgTE.toFixed(2)}
            </strong>
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-4 text-text-muted text-xs uppercase tracking-wider">
              <th className="px-3 py-3 text-left w-16">ID</th>
              <th className="px-3 py-3 text-left min-w-[140px]">Nombre</th>
              <th className="px-3 py-3 text-left min-w-[120px]">Predecesoras</th>
              <th className="px-3 py-3 text-center w-16">a</th>
              <th className="px-3 py-3 text-center w-16">m</th>
              <th className="px-3 py-3 text-center w-16">b</th>
              <th className="px-3 py-3 text-center w-20">te</th>
              <th className="px-3 py-3 text-center w-24">Costo</th>
              <th className="px-3 py-3 text-center w-16">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {activities.map((act: Activity) => {
              const te = computeTE(act.optimistic, act.mostLikely, act.pessimistic);
              const invalid = isInvalidEstimate(
                act.optimistic,
                act.mostLikely,
                act.pessimistic,
              );

              return (
                <tr
                  key={act.id}
                  className={`border-b border-surface-4/50 transition-colors ${
                    invalid
                      ? 'bg-critical/5 hover:bg-critical/10'
                      : 'hover:bg-surface-3/50'
                  }`}
                >
                  {/* ID */}
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      className="input-compact w-14"
                      value={act.id}
                      onChange={(e) =>
                        updateActivity(act.id, { id: e.target.value })
                      }
                    />
                  </td>

                  {/* Name */}
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      className="input-compact w-full text-left"
                      placeholder="Nombre de actividad"
                      value={act.name}
                      onChange={(e) =>
                        updateActivity(act.id, { name: e.target.value })
                      }
                    />
                  </td>

                  {/* Predecessors */}
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      className="input-compact w-full text-left"
                      placeholder="A1, A2"
                      value={act.predecessors.join(', ')}
                      onChange={(e) => handlePredChange(act.id, e.target.value)}
                    />
                  </td>

                  {/* a */}
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={0}
                      className="input-compact w-14"
                      value={act.optimistic || ''}
                      onChange={(e) =>
                        updateActivity(act.id, {
                          optimistic: Number(e.target.value) || 0,
                        })
                      }
                    />
                  </td>

                  {/* m */}
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={0}
                      className="input-compact w-14"
                      value={act.mostLikely || ''}
                      onChange={(e) =>
                        updateActivity(act.id, {
                          mostLikely: Number(e.target.value) || 0,
                        })
                      }
                    />
                  </td>

                  {/* b */}
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={0}
                      className="input-compact w-14"
                      value={act.pessimistic || ''}
                      onChange={(e) =>
                        updateActivity(act.id, {
                          pessimistic: Number(e.target.value) || 0,
                        })
                      }
                    />
                  </td>

                  {/* te (readonly) */}
                  <td className="px-3 py-2 text-center">
                    <span
                      className={`font-mono text-xs ${
                        invalid ? 'text-critical-light' : 'text-accent-light'
                      }`}
                    >
                      {te.toFixed(2)}
                    </span>
                  </td>

                  {/* Cost */}
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={0}
                      className="input-compact w-20"
                      value={act.cost || ''}
                      onChange={(e) =>
                        updateActivity(act.id, {
                          cost: Number(e.target.value) || 0,
                        })
                      }
                    />
                  </td>

                  {/* Delete */}
                  <td className="px-3 py-2 text-center">
                    <button
                      type="button"
                      className="btn-ghost text-critical-light hover:bg-critical/10"
                      onClick={() => removeActivity(act.id)}
                      title="Eliminar actividad"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              );
            })}

            {activities.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  className="text-center py-12 text-text-muted text-sm"
                >
                  No hay actividades aún. Agrega una para comenzar.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <button
          type="button"
          className="btn-secondary flex items-center gap-2"
          onClick={handleAdd}
        >
          <span className="text-base leading-none">＋</span>
          Agregar Actividad
        </button>

        <button
          type="button"
          className="btn-primary flex items-center gap-2"
          disabled={activities.length === 0}
          onClick={handleGenerate}
        >
          Generar Red
          <span className="text-sm">→</span>
        </button>
      </div>
    </div>
  );
}
