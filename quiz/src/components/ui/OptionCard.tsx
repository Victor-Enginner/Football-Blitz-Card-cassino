import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';

export type OptionCardProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'children'> & {
  children: ReactNode;
  description?: string;
};

export const OptionCard = forwardRef<HTMLInputElement, OptionCardProps>(function OptionCard(
  { children, description, className = '', ...props }, ref,
) {
  return (
    <label className={`relative block ${className}`}>
      <input ref={ref} type="radio" className="peer sr-only" {...props} />
      <span className="flex min-h-14 items-center gap-3 rounded-lg border border-card-border bg-card p-4 transition-colors peer-enabled:hover:border-muted-foreground peer-checked:border-primary peer-checked:bg-primary/10 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-accent peer-disabled:opacity-50">
        <span className="min-w-0 flex-1 text-sm font-medium">{children}
          {description && <span className="mt-1 block text-xs font-normal text-muted-foreground">{description}</span>}
        </span>
      </span>
      <span aria-hidden="true" className="pointer-events-none absolute right-0 top-0 hidden rounded-bl-lg rounded-tr-lg bg-primary px-1.5 text-xs text-white peer-checked:block">✓</span>
    </label>
  );
});
