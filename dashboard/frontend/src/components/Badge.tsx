interface BadgeProps {
  label: string;
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'default';
  size?: 'sm' | 'md';
  dot?: boolean;
  style?: React.CSSProperties;
}

export default function Badge({ label, variant = 'default', size = 'sm', dot = false, style }: BadgeProps) {
  const variantStyles = {
    default: 'bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border-color)]',
    success: 'bg-[rgba(0,186,124,0.15)] text-[var(--accent-green)] border-[rgba(0,186,124,0.3)]',
    warning: 'bg-[rgba(255,212,0,0.15)] text-[var(--accent-yellow)] border-[rgba(255,212,0,0.3)]',
    danger: 'bg-[rgba(244,33,46,0.15)] text-[var(--accent-red)] border-[rgba(244,33,46,0.3)]',
    info: 'bg-[rgba(29,155,240,0.15)] text-[var(--accent-blue)] border-[rgba(29,155,240,0.3)]',
    purple: 'bg-[rgba(120,86,255,0.15)] text-[#7856ff] border-[rgba(120,86,255,0.3)]',
  };

  const dotColors = {
    default: 'var(--text-muted)',
    success: 'var(--accent-green)',
    warning: 'var(--accent-yellow)',
    danger: 'var(--accent-red)',
    info: 'var(--accent-blue)',
    purple: '#7856ff',
  };

  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-2.5 py-1',
  };

  return (
    <span 
      className={`inline-flex items-center gap-1.5 rounded-md font-medium border ${variantStyles[variant]} ${sizeStyles[size]}`}
      style={style}
    >
      {dot && (
        <span 
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: dotColors[variant] }}
        />
      )}
      {label}
    </span>
  );
}
