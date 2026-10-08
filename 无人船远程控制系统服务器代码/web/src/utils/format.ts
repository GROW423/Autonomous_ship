// 格式化工具函数

export function formatBattery(percent: number | null): string {
  if (percent === null || percent === undefined) return '--'
  return `${Math.round(percent)}%`
}

export function formatSpeed(speed: number | null): string {
  if (speed === null || speed === undefined) return '--'
  return `${speed.toFixed(1)} m/s`
}

export function formatHeading(heading: number | null): string {
  if (heading === null || heading === undefined) return '--'
  return `${Math.round(heading)}°`
}

export function formatCoordinate(lat: number | null, lon: number | null): string {
  if (lat === null || lon === null) return '--'
  return `${lat.toFixed(6)}, ${lon.toFixed(6)}`
}

export function formatTime(isoString: string): string {
  const d = new Date(isoString)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatSignal(csq: number | null): string {
  if (csq === null || csq === undefined) return '--'
  if (csq === 99) return '无信号'
  if (csq >= 20) return '强'
  if (csq >= 10) return '中'
  return '弱'
}

export function getBatteryColor(percent: number | null): string {
  if (percent === null) return 'text-gray-400'
  if (percent > 50) return 'text-green-600'
  if (percent > 20) return 'text-yellow-600'
  return 'text-red-600'
}

export function getBatteryBgColor(percent: number | null): string {
  if (percent === null) return 'bg-gray-300'
  if (percent > 50) return 'bg-green-500'
  if (percent > 20) return 'bg-yellow-500'
  return 'bg-red-500'
}

export function getModeColor(mode: string | null): string {
  if (!mode) return 'bg-gray-100 text-gray-600'
  switch (mode) {
    case 'AUTO': return 'bg-blue-100 text-blue-700'
    case 'RTL': return 'bg-orange-100 text-orange-700'
    case 'MANUAL': return 'bg-purple-100 text-purple-700'
    case 'GUIDED': return 'bg-cyan-100 text-cyan-700'
    case 'HOLD': return 'bg-gray-100 text-gray-700'
    default: return 'bg-gray-100 text-gray-600'
  }
}
