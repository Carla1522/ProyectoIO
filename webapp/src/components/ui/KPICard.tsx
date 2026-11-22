import type { KPI } from '../../types';

const borderColors: Record<string, string> = {
  accent: 'border-l-accent',
  critical: 'border-l-critical',
  success: 'border-l-success',
  warn: 'border-l-warn',
  neutral: 'border-l-surface-4',
};

const valueColors: Record<string, string> = {
  accent: 'text-accent-light',
  critical: 'text-critical-light',
  success: 'text-success-light',
  warn: 'text-warn-light',
  neutral: 'text-text-primary',
};

export default function KPICard({ label, value, subtext, color = 'accent' }: KPI) {
  return (
    <div
      className={`card border-l-2 ${borderColors[color ?? 'accent']} px-4 py-3`}
    >
      <span className="text-2xs uppercase tracking-wider text-text-muted">
        {label}
      </span>
      <p
        className={`text-2xl font-semibold font-mono mt-0.5 ${
          valueColors[color ?? 'accent']
        }`}
      >
        {value}
      </p>
      {subtext && (
        <span className="text-2xs text-text-muted mt-1 block">{subtext}</span>
      )}
    </div>
  );
}
