import React from 'react';
import PropTypes from 'prop-types';

/**
 * Color configuration map for the MetricCard.
 * Maps abstract color names to specific Tailwind CSS classes for backgrounds, text, and borders.
 */
const THEME_COLORS = {
  blue: {
    iconBg: 'bg-blue-50',
    iconText: 'text-blue-600',
    trendUp: 'text-blue-600',
    trendDown: 'text-blue-600',
    border: 'border-blue-100',
    ring: 'focus:ring-blue-500',
  },
  green: {
    iconBg: 'bg-green-50',
    iconText: 'text-green-600',
    trendUp: 'text-green-600',
    trendDown: 'text-green-600',
    border: 'border-green-100',
    ring: 'focus:ring-green-500',
  },
  red: {
    iconBg: 'bg-red-50',
    iconText: 'text-red-600',
    trendUp: 'text-red-600',
    trendDown: 'text-red-600',
    border: 'border-red-100',
    ring: 'focus:ring-red-500',
  },
  purple: {
    iconBg: 'bg-purple-50',
    iconText: 'text-purple-600',
    trendUp: 'text-purple-600',
    trendDown: 'text-purple-600',
    border: 'border-purple-100',
    ring: 'focus:ring-purple-500',
  },
  orange: {
    iconBg: 'bg-orange-50',
    iconText: 'text-orange-600',
    trendUp: 'text-orange-600',
    trendDown: 'text-orange-600',
    border: 'border-orange-100',
    ring: 'focus:ring-orange-500',
  },
  gray: {
    iconBg: 'bg-gray-100',
    iconText: 'text-gray-600',
    trendUp: 'text-gray-600',
    trendDown: 'text-gray-600',
    border: 'border-gray-200',
    ring: 'focus:ring-gray-500',
  },
};

/**
 * MetricCard Component
 *
 * A reusable UI component for displaying statistics, metrics, and KPIs.
 * Supports loading states, trend indicators, custom icons, and click interactions.
 *
 * @param {Object} props - The component props
 * @param {string} props.title - The label or title of the metric
 * @param {string|number} props.value - The main value to display
 * @param {React.ReactNode} [props.icon] - Optional icon component to display in the top right
 * @param {Object} [props.trend] - Optional trend data object
 * @param {number|string} props.trend.value - The trend value (e.g., "12%", 50)
 * @param {'up'|'down'|'neutral'} props.trend.direction - Direction of the trend
 * @param {string} [props.trend.label] - Context label for the trend (e.g., "vs last month")
 * @param {'blue'|'green'|'red'|'purple'|'orange'|'gray'} [props.color='blue'] - Color theme for the card
 * @param {boolean} [props.loading=false] - Whether the card is in a loading state
 * @param {string} [props.className] - Additional CSS classes for the wrapper
 * @param {Function} [props.onClick] - Optional click handler
 */
const MetricCard = ({
  title,
  value,
  icon,
  trend,
  color = 'blue',
  loading = false,
  className = '',
  onClick,
}) => {
  // Resolve theme based on color prop, fallback to blue if invalid
  const theme = THEME_COLORS[color] || THEME_COLORS.blue;

  // Base classes for the card container
  const containerClasses = `
    relative flex flex-col p-6 bg-white rounded-xl shadow-sm border border-gray-100
    transition-all duration-200 ease-in-out
    ${onClick ? 'cursor-pointer hover:shadow-md hover:-translate-y-0.5 active:translate-y-0' : ''}
    ${onClick ? theme.ring : ''}
    ${onClick ? 'focus:outline-none focus:ring-2 focus:ring-offset-2' : ''}
    ${className}
  `.trim();

  // Render Loading Skeleton
  if (loading) {
    return (
      <div className={`${containerClasses} animate-pulse`} aria-busy="true">
        <div className="flex justify-between items-start mb-4">
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-10 w-10 bg-gray-200 rounded-lg"></div>
        </div>
        <div className="h-8 bg-gray-200 rounded w-3/4 mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-1/3"></div>
      </div>
    );
  }

  // Helper to render trend icon based on direction
  const renderTrendIcon = (direction) => {
    if (direction === 'up') {
      return (
        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      );
    } else if (direction === 'down') {
      return (
        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
        </svg>
      );
    }
    return (
      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14" />
      </svg>
    );
  };

  // Determine trend color dynamically if not strictly tied to theme
  const getTrendColorClass = (direction) => {
    if (direction === 'up') return 'text-green-600 bg-green-50';
    if (direction === 'down') return 'text-red-600 bg-red-50';
    return 'text-gray-600 bg-gray-50';
  };

  return (
    <div 
      className={containerClasses}
      onClick={onClick}
      role={onClick ? 'button' : 'article'}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(e);
        }
      } : undefined}
    >
      {/* Header: Title and Icon */}
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-sm font-medium text-gray-500 truncate pr-4" title={typeof title === 'string' ? title : undefined}>
          {title}
        </h3>
        
        {icon && (
          <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${theme.iconBg} ${theme.iconText} shrink-0`}>
            {React.cloneElement(icon, { className: `w-6 h-6 ${icon.props.className || ''}` })}
          </div>
        )}
      </div>

      {/* Body: Main Value */}
      <div className="flex items-baseline mt-1">
        <span className="text-2xl font-bold text-gray-900 tracking-tight">
          {value}
        </span>
      </div>

      {/* Footer: Trend Indicator */}
      {trend && (
        <div className="flex items-center mt-4 text-sm">
          <span 
            className={`
              inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
              ${getTrendColorClass(trend.direction)}
            `}
          >
            {renderTrendIcon(trend.direction)}
            {trend.value}
          </span>
          {trend.label && (
            <span className="ml-2 text-gray-400 text-xs truncate">
              {trend.label}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

MetricCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  icon: PropTypes.node,
  trend: PropTypes.shape({
    value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    direction: PropTypes.oneOf(['up', 'down', 'neutral']).isRequired,
    label: PropTypes.string,
  }),
  color: PropTypes.oneOf(['blue', 'green', 'red', 'purple', 'orange', 'gray']),
  loading: PropTypes.bool,
  className: PropTypes.string,
  onClick: PropTypes.func,
};

MetricCard.defaultProps = {
  color: 'blue',
  loading: false,
  className: '',
  trend: null,
  icon: null,
  onClick: null,
};

export default React.memo(MetricCard);
