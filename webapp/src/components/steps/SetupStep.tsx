import { useProjectStore } from '../../store/useProjectStore';

export default function SetupStep() {
  const project = useProjectStore((s) => s.project);
  const setProject = useProjectStore((s) => s.setProject);
  const loadTemplate = useProjectStore((s) => s.loadTemplate);
  const setStep = useProjectStore((s) => s.setStep);
  const markStepComplete = useProjectStore((s) => s.markStepComplete);

  const handleContinue = () => {
    markStepComplete('setup');
    setStep('network');
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 py-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Planteamiento</h1>
        <p className="text-sm text-text-muted mt-1">
          Define los datos generales de tu proyecto antes de construir la red.
        </p>
      </div>

      {/* Project Info Card */}
      <div className="card p-6 space-y-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          Información del Proyecto
        </h2>

        <div className="space-y-1.5">
          <label className="text-xs text-text-muted" htmlFor="proj-name">
            Nombre del proyecto
          </label>
          <input
            id="proj-name"
            type="text"
            className="input-field"
            placeholder="Ej: Desarrollo de sistema ERP"
            value={project.name}
            onChange={(e) => setProject({ name: e.target.value })}
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs text-text-muted" htmlFor="proj-desc">
            Descripción
          </label>
          <textarea
            id="proj-desc"
            className="input-field min-h-[100px] resize-y"
            placeholder="Describe brevemente el alcance y objetivos del proyecto…"
            value={project.description}
            onChange={(e) => setProject({ description: e.target.value })}
          />
        </div>
      </div>

      {/* Constraints Card */}
      <div className="card p-6 space-y-5">
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          Restricciones Rápidas
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div className="space-y-1.5">
            <label className="text-xs text-text-muted" htmlFor="deadline">
              Fecha límite (días)
            </label>
            <input
              id="deadline"
              type="number"
              min={0}
              className="input-field"
              placeholder="30"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-text-muted" htmlFor="budget">
              Presupuesto (USD)
            </label>
            <input
              id="budget"
              type="number"
              min={0}
              className="input-field"
              placeholder="50000"
            />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <button
          type="button"
          className="btn-secondary flex items-center justify-center gap-2"
          onClick={loadTemplate}
        >
          <span className="text-base leading-none">📋</span>
          Cargar Plantilla de Software
        </button>

        <div className="flex-1" />

        <button
          type="button"
          className="btn-primary flex items-center justify-center gap-2"
          onClick={handleContinue}
        >
          Continuar
          <span className="text-sm">→</span>
        </button>
      </div>
    </div>
  );
}
