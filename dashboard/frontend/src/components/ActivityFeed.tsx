import { ReactNode } from 'react';

interface ActivityItem {
  id: string;
  timestamp: string;
  description: string;
  status: 'success' | 'warning' | 'error' | 'info';
  icon?: ReactNode;
}

interface ActivityFeedProps {
  items: ActivityItem[];
  maxItems?: number;
  loading?: boolean;
}

export default function ActivityFeed({ items, maxItems = 10, loading = false }: ActivityFeedProps) {
  const displayItems = items.slice(0, maxItems);

  const statusColors = {
    success: 'var(--accent-green)',
    warning: 'var(--accent-yellow)',
    error: 'var(--accent-red)',
    info: 'var(--accent-blue)',
  };

  const statusGlow = {
    success: 'rgba(0, 186, 124, 0.3)',
    warning: 'rgba(255, 212, 0, 0.3)',
    error: 'rgba(244, 33, 46, 0.3)',
    info: 'rgba(29, 155, 240, 0.3)',
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="skeleton w-8 h-8 rounded-full" />
            <div className="flex-1 space-y-2">
              <div className="skeleton h-4 w-3/4 rounded" />
              <div className="skeleton h-3 w-1/4 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (displayItems.length === 0) {
    return (
      <div 
        className="text-center py-8"
        style={{ color: 'var(--text-muted)' }}
      >
        <svg 
          className="w-12 h-12 mx-auto mb-3 opacity-50"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
        <p>No recent activity</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {displayItems.map((item, index) => (
        <div
          key={item.id}
          className="flex items-start gap-3 p-3 rounded-lg transition-colors hover:bg-[var(--bg-card)]"
          style={{ animationDelay: `${index * 50}ms` }}
        >
          <div 
            className="relative"
          >
            <div 
              className="w-8 h-8 rounded-full flex items-center justify-center"
              style={{ 
                background: `${statusColors[item.status]}20`,
                color: statusColors[item.status]
              }}
            >
              {item.icon || (
                <div 
                  className="w-2 h-2 rounded-full"
                  style={{ background: statusColors[item.status] }}
                />
              )}
            </div>
            {index < displayItems.length - 1 && (
              <div 
                className="absolute top-10 left-1/2 -translate-x-1/2 w-px h-4"
                style={{ background: 'var(--border-color)' }}
              />
            )}
          </div>
          
          <div className="flex-1 min-w-0">
            <p 
              className="text-sm leading-snug"
              style={{ color: 'var(--text-primary)' }}
            >
              {item.description}
            </p>
            <p 
              className="text-xs mt-1"
              style={{ color: 'var(--text-muted)' }}
            >
              {formatTimestamp(item.timestamp)}
            </p>
          </div>
          
          <div 
            className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
            style={{ 
              background: statusColors[item.status],
              boxShadow: `0 0 8px ${statusGlow[item.status]}`
            }}
          />
        </div>
      ))}
    </div>
  );
}
