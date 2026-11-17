import { useEffect } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { exportProjectZip } from '../utils/exportData';
import type { StepId } from '../types';

const STEPS_ORDER: StepId[] = ['setup', 'network', 'verify', 'test-cases', 'results'];

export function useKeyboard() {
  const isPresentationMode = useProjectStore((s) => s.isPresentationMode);
  const togglePresentationMode = useProjectStore((s) => s.togglePresentationMode);
  const recalculate = useProjectStore((s) => s.recalculate);
  const currentStep = useProjectStore((s) => s.currentStep);
  const setStep = useProjectStore((s) => s.setStep);
  const project = useProjectStore((s) => s.project);
  const cpmResult = useProjectStore((s) => s.cpmResult);
  const testCases = useProjectStore((s) => s.testCases);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept if user is typing in an input or textarea
      const target = e.target as HTMLElement | null;
      const isInput =
        target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);

      // Escape key: exit presentation mode
      if (e.key === 'Escape' && isPresentationMode) {
        e.preventDefault();
        togglePresentationMode();
        return;
      }

      // Ctrl + E: Toggle presentation mode
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'e') {
        e.preventDefault();
        togglePresentationMode();
        return;
      }

      // Ctrl + Enter: Recalculate
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        recalculate();
        return;
      }

      // Ctrl + S: Export ZIP data
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        exportProjectZip(project, cpmResult, testCases);
        return;
      }

      // Step navigation with Alt + Arrow keys (doesn't interfere with text editing)
      if (e.altKey && !isPresentationMode) {
        const currentIndex = STEPS_ORDER.indexOf(currentStep);
        if (e.key === 'ArrowRight' && currentIndex < STEPS_ORDER.length - 1) {
          e.preventDefault();
          setStep(STEPS_ORDER[currentIndex + 1]);
        } else if (e.key === 'ArrowLeft' && currentIndex > 0) {
          e.preventDefault();
          setStep(STEPS_ORDER[currentIndex - 1]);
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    isPresentationMode,
    togglePresentationMode,
    recalculate,
    currentStep,
    setStep,
    project,
    cpmResult,
    testCases,
  ]);
}
