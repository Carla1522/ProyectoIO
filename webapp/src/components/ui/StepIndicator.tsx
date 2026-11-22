import type { Step, StepId } from '../../types';

interface StepIndicatorProps {
  steps: Step[];
  currentStep: StepId;
  onStepClick: (id: StepId) => void;
}

export default function StepIndicator({
  steps,
  currentStep,
  onStepClick,
}: StepIndicatorProps) {
  return (
    <div className="flex items-center gap-0">
      {steps.map((step, i) => {
        const isActive = step.id === currentStep;
        const isComplete = step.isComplete;

        return (
          <div key={step.id} className="flex items-center">
            {/* Connector line */}
            {i > 0 && (
              <div
                className={`w-8 h-px mx-1 transition-colors ${
                  isComplete || isActive ? 'bg-accent/60' : 'bg-surface-4'
                }`}
              />
            )}

            {/* Step circle + label */}
            <button
              type="button"
              onClick={() => onStepClick(step.id)}
              className="flex flex-col items-center gap-1 group cursor-pointer"
              title={step.description}
            >
              <div
                className={`
                  w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all
                  ${
                    isComplete
                      ? 'bg-accent text-white'
                      : isActive
                        ? 'border-2 border-accent text-accent-light animate-pulse-slow'
                        : 'bg-surface-3 text-text-muted group-hover:bg-surface-4'
                  }
                `}
              >
                {isComplete ? '✓' : i + 1}
              </div>
              <span
                className={`text-2xs whitespace-nowrap transition-colors ${
                  isActive
                    ? 'text-accent-light font-medium'
                    : isComplete
                      ? 'text-text-secondary'
                      : 'text-text-muted'
                }`}
              >
                {step.label}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
