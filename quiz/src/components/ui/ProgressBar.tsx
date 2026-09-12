export interface ProgressBarProps {
  value: number;
  max?: number;
  label: string;
  className?: string;
}

export function ProgressBar({ value, max = 100, label, className = '' }: ProgressBarProps) {
  const safeMax = Number.isFinite(max) && max > 0 ? max : 100;
  const safeValue = Number.isFinite(value) ? Math.min(safeMax, Math.max(0, value)) : 0;
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={safeMax}
      aria-valuenow={safeValue} className={`h-2 overflow-hidden rounded-full bg-muted ${className}`}>
      <div className="h-full rounded-full bg-primary transition-[width] duration-300 motion-reduce:transition-none"
        style={{ width: `${(safeValue / safeMax) * 100}%` }} />
    </div>
  );
}
