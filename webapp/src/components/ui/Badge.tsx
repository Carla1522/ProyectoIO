import type { ReactNode } from 'react';

interface BadgeProps {
  variant: 'critical' | 'success' | 'warn' | 'accent' | 'neutral';
  children: ReactNode;
}

const classes: Record<BadgeProps['variant'], string> = {
  critical: 'badge-critical',
  success: 'badge-success',
  warn: 'badge-warn',
  accent: 'badge-accent',
  neutral: 'badge bg-surface-3 text-text-secondary',
};

export default function Badge({ variant, children }: BadgeProps) {
  return <span className={classes[variant]}>{children}</span>;
}
