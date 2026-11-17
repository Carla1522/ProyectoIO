import React, { useRef } from 'react';
import { useProjectStore } from '../../store/useProjectStore';
import StepIndicator from '../ui/StepIndicator';
import { exportProjectZip } from '../../utils/exportData';
import type { Step, StepId } from '../../types';

const STEPS_CONFIG: { id: StepId; label: string; description: string }[] = [
  { id: 'setup', label: '1. Planteamiento', description: 'Variables y supuestos' },
  { id: 'network', label: '2. Red PERT/CPM', description: 'Actividades y tiempos' },
  { id: 'verify', label: '3. Verificación', description: 'Manual vs Motor' },
  { id: 'test-cases', label: '4. Casos de Prueba', description: 'Validación experimental' },
  { id: 'results', label: '5. Resultados', description: 'Ruta crítica y probabilidad' },
];

export default function Header() {
  const currentStep = useProjectStore((s) => s.currentStep);
  const completedSteps = useProjectStore((s) => s.completedSteps);
  const setStep = useProjectStore((s) => s.setStep);
  const loadTemplate = useProjectStore((s) => s.loadTemplate);
  const loadProject = useProjectStore((s) => s.loadProject);
  const togglePresentationMode = useProjectStore((s) => s.togglePresentationMode);
  const project = useProjectStore((s) => s.project);
  const cpmResult = useProjectStore((s) => s.cpmResult);
  const testCases = useProjectStore((s) => s.testCases);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const steps: Step[] = STEPS_CONFIG.map((cfg) => ({
    ...cfg,
    isActive: currentStep === cfg.id,
    isComplete: completedSteps.has(cfg.id),
  }));

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        loadProject(content);
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleExportZip = async () => {
    await exportProjectZip(project, cpmResult, testCases);
  };

  return (
    <header className="sticky top-0 z-40 w-full bg-surface-1/90 backdrop-blur border-b border-surface-4 px-6 py-2.5 transition-all">
      <div className="max-w-[1520px] mx-auto flex items-center justify-between gap-4">
        {/* Brand / Title */}
        <div className="flex items-center gap-3 min-w-[220px]">
          <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent font-mono font-bold text-sm">
            Δt
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm tracking-tight text-text-primary">
                PERT/CPM Studio
              </span>
              <span className="px-1.5 py-0.2 text-2xs font-mono bg-surface-3 text-text-muted rounded border border-surface-4">
                PRO
              </span>
            </div>
            <p className="text-2xs text-text-muted hidden sm:block">Planificación y Optimización Matemática</p>
          </div>
        </div>

        {/* Center: Step Navigation Flow */}
        <div className="hidden lg:flex flex-1 justify-center max-w-2xl px-4">
          <StepIndicator steps={steps} currentStep={currentStep} onStepClick={setStep} />
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          {/* Quick template button */}
          <button
            onClick={() => loadTemplate()}
            className="btn-ghost flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary border border-surface-4/60 hover:border-surface-4"
            title="Cargar proyecto base de ciclo de vida de desarrollo de software"
          >
            <span>⚡</span>
            <span className="hidden md:inline">Plantilla Software</span>
          </button>

          {/* Import / Load JSON */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleImportFile}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="btn-ghost flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary border border-surface-4/60 hover:border-surface-4"
            title="Cargar archivo proyecto.json previamente exportado"
          >
            <span>↑</span>
            <span className="hidden sm:inline">Cargar</span>
          </button>

          {/* Export ZIP Button */}
          <button
            onClick={handleExportZip}
            className="btn-ghost flex items-center gap-1.5 text-xs text-accent-light hover:text-white bg-accent/10 hover:bg-accent/20 border border-accent/20"
            title="Descargar paquete .ZIP con proyecto.json, resultados.xlsx, tabla_cpm_pert.csv y casos_prueba.json"
          >
            <span>↓</span>
            <span className="font-medium">Exportar (.ZIP)</span>
          </button>

          {/* Modo Exposición Button */}
          <button
            onClick={() => togglePresentationMode()}
            className="btn-primary flex items-center gap-1.5 text-xs py-1.5 px-3 bg-gradient-to-r from-accent to-accent-dim shadow-sm"
            title="Iniciar Modo Exposición a pantalla completa para defensa en vivo"
          >
            <span>▶</span>
            <span className="font-semibold">Modo Exposición</span>
          </button>
        </div>
      </div>

      {/* Mobile Step Bar */}
      <div className="lg:hidden mt-2 pt-2 border-t border-surface-4/50 flex justify-center">
        <StepIndicator steps={steps} currentStep={currentStep} onStepClick={setStep} />
      </div>
    </header>
  );
}
