import { Battery, BatteryCharging } from 'lucide-react'
import { getBatteryColor, getBatteryBgColor } from '../utils/format'

interface BatteryIndicatorProps {
  percent: number | null
  voltage?: number | null
  current?: number | null
  size?: 'sm' | 'md' | 'lg'
}

export default function BatteryIndicator({ percent, voltage, current, size = 'md' }: BatteryIndicatorProps) {
  const colorClass = getBatteryColor(percent)
  const bgClass = getBatteryBgColor(percent)
  const width = percent ?? 0

  const sizeClasses = {
    sm: 'w-16 h-4',
    md: 'w-24 h-5',
    lg: 'w-32 h-6',
  }

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <div className={`${sizeClasses[size]} bg-gray-200 rounded-sm border border-gray-300 overflow-hidden`}>
          <div
            className={`h-full ${bgClass} transition-all duration-500`}
            style={{ width: `${width}%` }}
          />
        </div>
        {/* 电池头 */}
        <div className="absolute right-[-3px] top-1/2 -translate-y-1/2 w-1 h-2 bg-gray-300 rounded-r-sm" />
      </div>
      <div className="flex flex-col">
        <span className={`font-bold ${colorClass} ${size === 'sm' ? 'text-xs' : 'text-sm'}`}>
          {percent !== null ? `${Math.round(percent)}%` : '--'}
        </span>
        {voltage !== undefined && voltage !== null && (
          <span className="text-xs text-gray-500">{voltage.toFixed(1)}V</span>
        )}
      </div>
    </div>
  )
}
