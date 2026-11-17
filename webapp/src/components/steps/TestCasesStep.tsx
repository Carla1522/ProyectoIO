import React, { useState } from 'react';
import { useProjectStore } from '../../store/useProjectStore';
import { calculateCPM } from '../../engine/cpmEngine';
import type { TestCase, CPMResult } from '../../types';

export default function TestCasesStep() {
  const testCases = useProjectStore((s) => s.testCases);
  const runTestCase = useProjectStore((s) => s.runTestCase);
  const runAllTestCases = useProjectStore((s) => s.runAllTestCases);
  const addTestCase = useProjectStore((s) => s.addTestCase);
  const loadProject = useProjectStore((s) => s.loadProject);
  const setStep = useProjectStore((s) => s.setStep);
  const markStepComplete = useProjectStore((s) => s.markStepComplete);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);

  // Results cache for cases executed in this component
  const [executedResults, setExecutedResults] = useState<Record<string, CPMResult>>({});

  const handleRunCase = (tc: TestCase) => {
    runTestCase(tc.id);
    try {
      const res = calculateCPM(tc.activities);
      setExecutedResults((prev) => ({ ...prev, [tc.id]: res }));
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunAll = () => {
    runAllTestCases();
    const map: Record<string, CPMResult> = {};
    testCases.forEach((tc) => {
      try {
        map[tc.id] = calculateCPM(tc.activities);
      } catch (err) {
        console.error(err);
      }
    });
    setExecutedResults(map);
    markStepComplete('test-cases');
  };

  const handleLoadIntoEditor = (tc: TestCase) => {
    const projectData = {
      name: tc.name,
      description: tc.description,
      activities: tc.activities,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    loadProject(JSON.stringify(projectData));
    setStep('network');
  };

  return (
    <div className="space-y-6">
      {/* Step Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <span>Motor de Pruebas y Validación Experimental</span>
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Validación sistemática del motor matemático mediante un banco de pruebas de referencia y un caso límite de convergencia crítica.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowNewModal(true)}
            className="btn-secondary text-xs flex items-center gap-1.5"
          >
            <span>+</span>
            <span>Registrar Caso de Prueba</span>
          </button>
          <button
            onClick={handleRunAll}
            className="btn-primary text-xs flex items-center gap-1.5"
          >
            <span>▶</span>
            <span>Ejecutar Todas las Pruebas</span>
          </button>
        </div>
      </div>

      {/* Grid of Test Cases */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {testCases.map((tc) => {
          const res = executedResults[tc.id];
          const isEdge = tc.isEdgeCase;
          const isExpanded = expandedId === tc.id;

          // Verification criteria
          const isPassed =
            res &&
            (!tc.expectedDuration || Math.abs(res.duration - tc.expectedDuration) < 0.05) &&
            (!tc.expectedCriticalPath ||
              tc.expectedCriticalPath.join(',') === res.criticalPath.join(','));

          return (
            <div
              key={tc.id}
              className={`card p-5 transition-all flex flex-col justify-between ${
                isEdge
                  ? 'border-warn/40 bg-gradient-to-b from-warn/5 to-surface-2 hover:border-warn/60'
                  : 'hover:border-accent/30'
              }`}
            >
              <div className="space-y-3">
                {/* Card Header */}
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-text-primary">{tc.name}</span>
                      {isEdge && (
                        <span className="px-2 py-0.5 rounded-full text-3xs font-mono font-bold bg-warn/15 text-warn-light border border-warn/30 animate-pulse">
                          CASO LÍMITE
                        </span>
                      )}
                    </div>
                    <p className="text-2xs text-text-muted mt-1 leading-relaxed">
                      {tc.description}
                    </p>
                  </div>

                  {res && (
                    <span
                      className={`px-2 py-0.5 rounded text-3xs font-mono font-bold shrink-0 ${
                        isPassed
                          ? 'bg-success/15 text-success-light border border-success/30'
                          : 'bg-critical/15 text-critical-light border border-critical/30'
                      }`}
                    >
                      {isPassed ? '✓ CONFORME' : '✕ DISCREPANCIA'}
                    </span>
                  )}
                </div>

                {/* Case Properties */}
                <div className="bg-surface-1/60 p-3 rounded-lg border border-surface-4/40 space-y-1.5 text-xs font-mono">
                  <div className="flex items-center justify-between text-2xs">
                    <span className="text-text-muted">Actividades en el Grafo:</span>
                    <span className="text-text-primary font-bold">{tc.activities.length} nodos</span>
                  </div>

                  {tc.expectedDuration !== undefined && (
                    <div className="flex items-center justify-between text-2xs">
                      <span className="text-text-muted">Duración Teórica Esperada:</span>
                      <span className="text-accent-light font-bold">{tc.expectedDuration} días</span>
                    </div>
                  )}

                  {tc.expectedCriticalPath && (
                    <div className="flex items-center justify-between text-2xs">
                      <span className="text-text-muted">Ruta Crítica Esperada:</span>
                      <span className="text-text-secondary truncate max-w-[180px]">
                        {tc.expectedCriticalPath.join(' → ')}
                      </span>
                    </div>
                  )}

                  {/* Execution Results if executed */}
                  {res && (
                    <div className="pt-2 border-t border-surface-4/40 space-y-1">
                      <div className="flex items-center justify-between text-2xs">
                        <span className="text-text-muted">Duración Calculada:</span>
                        <span className="text-text-primary font-bold">{res.duration.toFixed(2)} días</span>
                      </div>
                      <div className="flex items-center justify-between text-2xs">
                        <span className="text-text-muted">Ruta Calculada:</span>
                        <span className="text-critical-light font-bold truncate max-w-[180px]">
                          {res.criticalPath.join(' → ')}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-2xs">
                        <span className="text-text-muted">Desviación σ:</span>
                        <span className="text-text-muted">{res.sigma.toFixed(3)} días</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-4 pt-3 border-t border-surface-4/40 flex items-center justify-between gap-2">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : tc.id)}
                  className="text-2xs text-text-muted hover:text-text-primary transition-colors"
                >
                  {isExpanded ? 'Ocultar actividades ▲' : 'Ver actividades (' + tc.activities.length + ') ▼'}
                </button>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleLoadIntoEditor(tc)}
                    className="btn-ghost text-2xs text-text-secondary hover:text-text-primary border border-surface-4"
                    title="Carga este caso en el editor del Paso 2 para ver su red y Gantt interactivo"
                  >
                    Cargar en Editor
                  </button>
                  <button
                    onClick={() => handleRunCase(tc)}
                    className="btn-secondary text-2xs"
                  >
                    Ejecutar Prueba
                  </button>
                </div>
              </div>

              {/* Expanded Activities List */}
              {isExpanded && (
                <div className="mt-3 pt-3 border-t border-surface-4/40 text-2xs font-mono max-h-40 overflow-y-auto space-y-1">
                  {tc.activities.map((a) => (
                    <div
                      key={a.id}
                      className="flex items-center justify-between py-0.5 px-2 bg-surface-1 rounded border border-surface-4/30"
                    >
                      <span className="text-accent-light font-bold">{a.id}</span>
                      <span className="text-text-secondary font-sans truncate mx-2">{a.name}</span>
                      <span className="text-text-muted">
                        [{a.optimistic}, {a.mostLikely}, {a.pessimistic}] | Pred: {a.predecessors.join(',') || '—'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Modal for adding a new test case */}
      {showNewModal && (
        <NewTestCaseModal
          onClose={() => setShowNewModal(false)}
          onSave={(newCase) => {
            addTestCase(newCase);
            setShowNewModal(false);
          }}
        />
      )}
    </div>
  );
}

// Modal component to register new test cases
function NewTestCaseModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (tc: Omit<TestCase, 'id'>) => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isEdgeCase, setIsEdgeCase] = useState(false);
  const [expectedDuration, setExpectedDuration] = useState<number | undefined>(undefined);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    // Create a minimal 3-node sequence as starting activities
    onSave({
      name: name.trim(),
      description: description.trim() || 'Caso de prueba personalizado',
      isEdgeCase,
      expectedDuration,
      activities: [
        { id: 'T1', name: 'Inicio', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 500, predecessors: [] },
        { id: 'T2', name: 'Proceso', optimistic: 2, mostLikely: 4, pessimistic: 6, cost: 1000, predecessors: ['T1'] },
        { id: 'T3', name: 'Cierre', optimistic: 1, mostLikely: 2, pessimistic: 3, cost: 500, predecessors: ['T2'] },
      ],
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="card p-6 max-w-md w-full space-y-4 animate-slide-up">
        <div className="flex items-center justify-between border-b border-surface-4 pb-3">
          <h3 className="text-sm font-bold text-text-primary">Registrar Nuevo Caso de Prueba</h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary text-sm">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div className="space-y-1">
            <label className="text-text-muted">Nombre del Caso</label>
            <input
              type="text"
              required
              className="input-field"
              placeholder="Ej: Prueba de Grafo Desconectado"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <label className="text-text-muted">Hipótesis / Descripción</label>
            <textarea
              className="input-field min-h-[70px]"
              placeholder="Describe qué aspecto del modelo matemático se busca contrastar…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <label className="text-text-muted">Duración Teórica Esperada (Opcional)</label>
            <input
              type="number"
              step="0.1"
              className="input-field"
              placeholder="Ej: 15.0"
              value={expectedDuration === undefined ? '' : expectedDuration}
              onChange={(e) => setExpectedDuration(e.target.value ? parseFloat(e.target.value) : undefined)}
            />
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="edge-checkbox"
              checked={isEdgeCase}
              onChange={(e) => setIsEdgeCase(e.target.checked)}
              className="accent-accent"
            />
            <label htmlFor="edge-checkbox" className="text-text-secondary select-none cursor-pointer">
              Marcar como Caso Límite (Edge Case)
            </label>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-surface-4">
            <button type="button" onClick={onClose} className="btn-secondary text-xs">
              Cancelar
            </button>
            <button type="submit" className="btn-primary text-xs">
              Guardar Caso
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
