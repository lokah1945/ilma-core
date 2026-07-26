interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  icon?: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

export default function StatCard({
  title,
  value,
  subtitle,
  trend,
  trendValue,
  icon,
  variant = 'default',
}: StatCardProps) {
  const variantStyles = {
    default: {
      border: 'var(--border-color)',
      iconBg: 'rgba(0, 212, 255, 0.1)',
      iconColor: 'var(--accent-cyan)',
      valueColor: 'var(--text-primary)',
    },
    success: {
      border: 'rgba(0, 186, 124, 0.3)',
      iconBg: 'rgba(0, 186, 124, 0.1)',
      iconColor: 'var(--accent-green)',
      valueColor: 'var(--accent-green)',
    },
    warning: {
      border: 'rgba(255, 212, 0, 0.3)',
      iconBg: 'rgba(255, 212, 0, 0.1)',
      iconColor: 'var(--accent-yellow)',
      valueColor: 'var(--accent-yellow)',
    },
    danger: {
      border: 'rgba(244, 33, 46, 0.3)',
      iconBg: 'rgba(244, 33, 46, 0.1)',
      iconColor: 'var(--accent-red)',
      valueColor: 'var(--accent-red)',
    },
    info: {
      border: 'rgba(29, 155, 240, 0.3)',
      iconBg: 'rgba(29, 155, 240, 0.1)',
      iconColor: 'var(--accent-blue)',
      valueColor: 'var(--accent-blue)',
    },
  };

  const style = variantStyles[variant];

  const trendColors = {
    up: 'var(--accent-green)',
    down: 'var(--accent-red)',
    neutral: 'var(--text-muted)',
  };

  const trendIcons = {
    up: '↑',
    down: '↓',
    neutral: '→',
  };

  return (
    <div 
      className="glass-card p-5 relative overflow-hidden"
      style={{ borderColor: style.border }}
    >
      {/* Background Glow */}
      <div 
        className="absolute top-0 right-0 w-32 h-32 rounded-full opacity-20 blur-3xl"
        style={{ background: style.iconColor }}
      />

      <div className="relative">
        <div className="flex items-start justify-between mb-3">
          <div 
            className="w-12 h-12 rounded-xl flex items-center justify-center"
            style={{ background: style.iconBg }}
          >
            {icon && (
              <div style={{ color: style.iconColor }}>
                {icon}
              </div>
            )}
          </div>
          
          {trend && trendValue && (
            <div 
              className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full"
              style={{ 
                background: `${trendColors[trend]}15`,
                color: trendColors[trend] 
              }}
            >
              <span>{trendIcons[trend]}</span>
              <span>{trendValue}</span>
            </div>
          )}
        </div>

        <div className="space-y-1">
          <p 
            className="text-sm font-medium"
            style={{ color: 'var(--text-secondary)' }}
          >
            {title}
          </p>
          <p 
            className="text-3xl font-bold"
            style={{ color: style.valueColor }}
          >
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {subtitle && (
            <p 
              className="text-xs"
              style={{ color: 'var(--text-muted)' }}
            >
              {subtitle}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
