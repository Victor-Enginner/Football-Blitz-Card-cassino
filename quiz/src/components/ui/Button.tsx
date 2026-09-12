import { forwardRef, type ButtonHTMLAttributes } from 'react';

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'outline';
};

const variants = {
  primary: 'border-primary bg-primary text-primary-foreground hover:border-primary-hover hover:bg-primary-hover',
  secondary: 'border-card-border bg-card text-foreground hover:bg-muted',
  outline: 'border-card-border bg-transparent text-foreground hover:bg-card',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', type = 'button', className = '', ...props }, ref,
) {
  return <button ref={ref} type={type} className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border px-4 py-3 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent active:translate-y-px disabled:pointer-events-none disabled:opacity-50 ${variants[variant]} ${className}`} {...props} />;
});
