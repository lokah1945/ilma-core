import { ReactNode } from 'react';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  action?: ReactNode;
  height?: number;
}

export default function ChartCard({
  title,
  subtitle,
  children,
  action,
  height = 300,
}: ChartCardProps) {
  return (
    <div className="chart-container">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 
            className="text-base font-semibold"
            style={{ color: 'var(--text-primary)' }}
          >
            {title}
          </h3>
          {subtitle && (
            <p 
              className="text-sm mt-0.5"
              style={{ color: 'var(--text-muted)' }}
            >
              {subtitle}
            </p>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      
      <div style={{ height }}>
        {children}
      </div>
    </div>
  );
}
