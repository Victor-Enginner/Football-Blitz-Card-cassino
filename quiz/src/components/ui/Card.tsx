import { forwardRef, type HTMLAttributes } from 'react';

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function Card(
  { className = '', ...props }, ref,
) {
  return <div ref={ref} className={`rounded-2xl border border-card-border bg-card/80 p-5 text-card-foreground shadow-lg shadow-black/50 backdrop-blur-md ${className}`} {...props} />;
});
