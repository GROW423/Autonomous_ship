import { Link } from 'react-router-dom'
import { Ship, MapPin, Navigation, Wifi, WifiOff, Trash2 } from 'lucide-react'
import type { Boat, BoatStatus } from '../types'
import BatteryIndicator from './BatteryIndicator'
import { formatSpeed, getModeColor } from '../utils/format'

interface BoatCardProps {
  boat: Boat
  status?: BoatStatus
  onDelete?: (boat: Boat) => void
}

export default function BoatCard({ boat, status, onDelete }: BoatCardProps) {
  const online = status?.online ?? false
  const mode = status?.flight_mode ?? null

  const handleDelete = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (onDelete && window.confirm(`确定要删除船「${boat.name}」吗？此操作不可恢复。`)) {
      onDelete(boat)
    }
  }

  return (
    <Link
      to={`/boats/${boat.id}`}
      className="block bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-gray-100 overflow-hidden group"
    >
      {/* 顶部状态条 */}
      <div className={`h-1 ${online ? 'bg-green-500' : 'bg-gray-300'}`} />

      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${online ? 'bg-blue-100' : 'bg-gray-100'}`}>
              <Ship className={`w-5 h-5 ${online ? 'text-blue-600' : 'text-gray-400'}`} />
            </div>
            <div>
              <h3 className="font-semibold text-gray-800">{boat.name}</h3>
              <p className="text-xs text-gray-400">ID: {boat.mavlink_sys_id}</p>
              {boat.region_name && (
                <span className="inline-block mt-1 px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs rounded">
                  {boat.region_name}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              {online ? (
                <Wifi className="w-4 h-4 text-green-500" />
              ) : (
                <WifiOff className="w-4 h-4 text-gray-400" />
              )}
              <span className={`text-xs ${online ? 'text-green-600' : 'text-gray-400'}`}>
                {online ? '在线' : '离线'}
              </span>
            </div>
            {onDelete && (
              <button
                onClick={handleDelete}
                className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                title="删除船"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* 状态信息 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <BatteryIndicator percent={status?.battery_remaining ?? null} voltage={status?.battery_voltage} size="sm" />
            {mode && (
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${getModeColor(mode)}`}>
                {mode}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-1 text-gray-500">
              <Navigation className="w-3 h-3" />
              <span>{formatSpeed(status?.groundspeed ?? null)}</span>
            </div>
            <div className="flex items-center gap-1 text-gray-500">
              <MapPin className="w-3 h-3" />
              <span className="truncate">
                {status?.lat ? `${status.lat.toFixed(4)}, ${status.lon?.toFixed(4)}` : '--'}
              </span>
            </div>
          </div>

          {/* 饲料余量 */}
          {status?.feed_level !== null && status?.feed_level !== undefined && (
            <div>
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>饲料余量</span>
                <span>{Math.round(status.feed_level)}%</span>
              </div>
              <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full ${status.feed_level > 20 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${status.feed_level}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </Link>
  )
}
