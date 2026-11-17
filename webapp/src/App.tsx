import React, { useEffect } from 'react';
import Header from './components/layout/Header';
import SetupStep from './components/steps/SetupStep';
import NetworkStep from './components/steps/NetworkStep';
import VerifyStep from './components/steps/VerifyStep';
import TestCasesStep from './components/steps/TestCasesStep';
import ResultsStep from './components/steps/ResultsStep';
import HealthPanel from './components/panels/HealthPanel';
import DecisionPanel from './components/panels/DecisionPanel';
import ProgressPanel from './components/panels/ProgressPanel';
import PresentationMode from './components/presentation/PresentationMode';
import { useProjectStore } from './store/useProjectStore';
import { useKeyboard } from './hooks/useKeyboard';

export default function App() {
  const isPresentationMode = useProjectStore((s) => s.isPresentationMode);
  const currentStep = useProjectStore((s) => s.currentStep);
  const project = useProjectStore((s) => s.project);
  const loadTemplate = useProjectStore((s) => s.loadTemplate);

  // Activate keyboard shortcuts
  useKeyboard();

  // If initial project is empty, pre-load software template so the app doesn't start empty
  useEffect(() => {
    if (!project || project.activities.length === 0) {
      loadTemplate();
    }
  }, []);

  if (isPresentationMode) {
    return <PresentationMode />;
  }

  return (
    <div className="min-h-screen bg-surface-0 text-text-primary flex flex-col font-sans selection:bg-accent/30 selection:text-white">
      {/* Top Header */}
      <Header />

      {/* Main Workspace Container */}
      <main className="flex-1 max-w-[1520px] w-full mx-auto px-6 py-6">
        <div className="grid grid-cols-12 gap-6 items-start">
          {/* Main Task Flow View (8 cols on lg, full on sm) */}
          <div className="col-span-12 lg:col-span-8 space-y-6">
            {currentStep === 'setup' && <SetupStep />}
            {currentStep === 'network' && <NetworkStep />}
            {currentStep === 'verify' && <VerifyStep />}
            {currentStep === 'test-cases' && <TestCasesStep />}
            {currentStep === 'results' && <ResultsStep />}
          </div>

          {/* Smart Panels Sidebar (4 cols on lg, full on sm) */}
          <aside className="col-span-12 lg:col-span-4 space-y-4 sticky top-20">
            <DecisionPanel />
            <HealthPanel />
            <ProgressPanel />

            {/* Quick Shortcuts Helper Card */}
            <div className="p-3 rounded-lg bg-surface-1/40 border border-surface-4/40 text-3xs font-mono text-text-muted space-y-1">
              <div className="flex justify-between">
                <span>Atajos:</span>
                <span className="text-text-secondary">Ctrl+E: Modo Exposición · Ctrl+S: Exportar</span>
              </div>
              <div className="flex justify-between">
                <span>Navegación:</span>
                <span className="text-text-secondary">Alt + Flechas · Ctrl+Enter: Recalcular</span>
              </div>
            </div>
          </aside>
        </div>
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-surface-4/50 py-3 px-6 bg-surface-1/40 text-2xs text-text-muted text-center font-mono">
        PERT/CPM Studio · Modelo Determinístico y Probabilístico · Optimización de Proyectos
      </footer>
    </div>
  );
}
