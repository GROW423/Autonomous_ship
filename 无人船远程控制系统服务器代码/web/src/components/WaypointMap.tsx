import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react'
import type { Waypoint, BoatStatus, TelemetryRecord } from '../types'

// 高德地图全局类型声明
declare global {
  interface Window {
    AMap: any
  }
}

interface WaypointMapProps {
  boatStatus?: BoatStatus | null
  waypoints?: Waypoint[]
  history?: TelemetryRecord[]
  editable?: boolean
  onWaypointsChange?: (waypoints: Waypoint[]) => void
  height?: string
  autoFocus?: boolean
}

export interface WaypointMapRef {
  focusToPosition: (lat: number, lon: number, zoom?: number) => void
  focusToBoat: () => void
}

/**
 * 高德地图航点编辑器
 * - 显示船实时位置(小船图标)
 * - 显示历史轨迹
 * - 点击地图添加航点
 * - 拖动航点调整位置
 * - 右键删除航点
 * - 支持外部调用定位到指定位置
 */
const WaypointMap = forwardRef<WaypointMapRef, WaypointMapProps>(function WaypointMap({
  boatStatus,
  waypoints = [],
  history = [],
  editable = false,
  onWaypointsChange,
  height = '500px',
  autoFocus = true,
}, ref) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<any>(null)
  const markersRef = useRef<any[]>([])
  const polylineRef = useRef<any>(null)
  const boatMarkerRef = useRef<any>(null)
  const historyPolylineRef = useRef<any>(null)
  const waypointsRef = useRef<Waypoint[]>(waypoints)
  const onWaypointsChangeRef = useRef(onWaypointsChange)
  const boatStatusRef = useRef(boatStatus)
  const hasAutoFocusedRef = useRef(false)
  const [mapReady, setMapReady] = useState(false)

  // 保持最新引用
  useEffect(() => {
    waypointsRef.current = waypoints
  }, [waypoints])
  useEffect(() => {
    onWaypointsChangeRef.current = onWaypointsChange
  }, [onWaypointsChange])
  useEffect(() => {
    boatStatusRef.current = boatStatus
  }, [boatStatus])

  // 暴露给父组件的方法
  useImperativeHandle(ref, () => ({
    focusToPosition: (lat: number, lon: number, zoom?: number) => {
      if (!mapInstance.current) return
      mapInstance.current.setZoomAndCenter(zoom || 17, [lon, lat], false, 500)
    },
    focusToBoat: () => {
      const s = boatStatusRef.current
      if (!mapInstance.current || !s?.lat || !s?.lon) return
      mapInstance.current.setZoomAndCenter(17, [s.lon, s.lat], false, 500)
    },
  }))

  // 初始化地图
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return

    if (!window.AMap) {
      console.error('高德地图API未加载, 请检查index.html中的key配置')
      return
    }

    const map = new window.AMap.Map(mapRef.current, {
      zoom: 16,
      center: [113.2644, 23.1291], // 默认广州
      mapStyle: 'amap://styles/normal',
      viewMode: '2D',
    })

    // 添加控件
    map.addControl(new window.AMap.Scale())
    map.addControl(new window.AMap.ToolBar({ position: 'RB' }))

    mapInstance.current = map
    setMapReady(true)

    return () => {
      map.destroy()
      mapInstance.current = null
    }
  }, [])

  // 点击添加航点 (编辑模式)
  useEffect(() => {
    if (!mapInstance.current || !mapReady) return
    const map = mapInstance.current

    const clickHandler = (e: any) => {
      const newWp: Waypoint = {
        lat: e.lnglat.getLat(),
        lon: e.lnglat.getLng(),
        alt: 0,
        speed: 1.5,
        action: null,
      }
      const updated = [...waypointsRef.current, newWp]
      onWaypointsChangeRef.current?.(updated)
    }

    if (editable) {
      map.on('click', clickHandler)
    }

    return () => {
      map.off('click', clickHandler)
    }
  }, [editable, mapReady])

  // 渲染航点
  const renderWaypoints = useCallback(() => {
    if (!mapInstance.current || !mapReady) return
    const map = mapInstance.current

    // 清除旧标记
    markersRef.current.forEach((m) => map.remove(m))
    markersRef.current = []
    if (polylineRef.current) {
      map.remove(polylineRef.current)
      polylineRef.current = null
    }

    if (waypoints.length === 0) return

    // 创建航点标记
    const points: [number, number][] = []
    waypoints.forEach((wp, index) => {
      points.push([wp.lon, wp.lat])

      const marker = new window.AMap.Marker({
        position: [wp.lon, wp.lat],
        title: `航点 ${index + 1}`,
        draggable: editable,
        content: `<div style="
          background: ${index === 0 ? '#10b981' : index === waypoints.length - 1 ? '#ef4444' : '#3b82f6'};
          color: white;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: bold;
          border: 2px solid white;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        ">${index + 1}</div>`,
      })

      if (editable) {
        marker.on('dragend', (e: any) => {
          const updated = [...waypoints]
          updated[index] = {
            ...updated[index],
            lat: e.lnglat.getLat(),
            lon: e.lnglat.getLng(),
          }
          onWaypointsChange?.(updated)
        })
        marker.on('rightclick', () => {
          const updated = waypoints.filter((_, i) => i !== index)
          onWaypointsChange?.(updated)
        })
      }

      map.add(marker)
      markersRef.current.push(marker)
    })

    // 航点连线
    if (points.length > 1) {
      polylineRef.current = new window.AMap.Polyline({
        path: points,
        strokeColor: '#3b82f6',
        strokeWeight: 3,
        strokeOpacity: 0.8,
        strokeStyle: 'dashed',
      })
      map.add(polylineRef.current)
    }
  }, [waypoints, editable, mapReady, onWaypointsChange])

  useEffect(() => {
    renderWaypoints()
  }, [renderWaypoints])

  // 渲染船实时位置 (小船图标)
  useEffect(() => {
    if (!mapInstance.current || !boatStatus || !boatStatus.lat || !boatStatus.lon) return
    const map = mapInstance.current

    const position: [number, number] = [boatStatus.lon, boatStatus.lat]
    const heading = boatStatus.heading || 0

    // 小船SVG图标
    const boatSvg = `
      <svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" style="transform: rotate(${heading}deg); transform-origin: center center; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));">
        <!-- 船身 -->
        <path d="M20 4 L28 14 L28 28 L20 36 L12 28 L12 14 Z" fill="#2563eb" stroke="#1e40af" stroke-width="1.5"/>
        <!-- 船舱 -->
        <rect x="16" y="12" width="8" height="10" rx="1" fill="#60a5fa" stroke="#3b82f6" stroke-width="1"/>
        <!-- 船头方向指示 -->
        <path d="M20 2 L23 8 L17 8 Z" fill="#ef4444"/>
        <!-- 水波效果 -->
        <ellipse cx="20" cy="36" rx="10" ry="2" fill="none" stroke="#93c5fd" stroke-width="1" opacity="0.6"/>
      </svg>
    `

    if (!boatMarkerRef.current) {
      boatMarkerRef.current = new window.AMap.Marker({
        position,
        content: boatSvg,
        zIndex: 100,
        offset: new window.AMap.Pixel(-20, -20),
      })
      map.add(boatMarkerRef.current)
    } else {
      boatMarkerRef.current.setPosition(position)
      boatMarkerRef.current.setContent(boatSvg)
    }

    // 首次收到船位置时自动定位
    if (autoFocus && !hasAutoFocusedRef.current) {
      hasAutoFocusedRef.current = true
      setTimeout(() => {
        map.setZoomAndCenter(17, position, false, 800)
      }, 300)
    }
  }, [boatStatus?.lat, boatStatus?.lon, boatStatus?.heading, autoFocus])

  // 渲染历史轨迹
  useEffect(() => {
    if (!mapInstance.current || history.length < 2) return
    const map = mapInstance.current

    if (historyPolylineRef.current) {
      map.remove(historyPolylineRef.current)
    }

    const points = history
      .filter((r) => r.lat && r.lon)
      .map((r) => [r.lon!, r.lat!] as [number, number])

    if (points.length < 2) return

    historyPolylineRef.current = new window.AMap.Polyline({
      path: points,
      strokeColor: '#10b981',
      strokeWeight: 3,
      strokeOpacity: 0.6,
    })
    map.add(historyPolylineRef.current)
  }, [history])

  return (
    <div className="relative rounded-lg overflow-hidden border border-gray-200" style={{ height }}>
      <div ref={mapRef} className="w-full h-full" />
      {editable && (
        <div className="absolute top-3 left-3 bg-white/90 backdrop-blur px-3 py-2 rounded-lg shadow text-xs text-gray-600">
          <div>点击地图添加航点</div>
          <div>拖动航点调整位置</div>
          <div>右键航点删除</div>
        </div>
      )}
      {/* 图例 */}
      <div className="absolute bottom-3 left-3 bg-white/90 backdrop-blur px-3 py-2 rounded-lg shadow text-xs space-y-1">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 40 40"><path d="M20 4 L28 14 L28 28 L20 36 L12 28 L12 14 Z" fill="#2563eb"/></svg>
          </div>
          <span className="text-gray-600">船实时位置</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-0.5 bg-blue-500" style={{borderTop: '2px dashed #3b82f6'}}></div>
          <span className="text-gray-600">设定航线</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-0.5 bg-green-500"></div>
          <span className="text-gray-600">实际轨迹</span>
        </div>
      </div>
      {!mapReady && (
        <div className="absolute inset-0 bg-gray-100 flex items-center justify-center">
          <div className="text-gray-400 text-sm">地图加载中...</div>
        </div>
      )}
    </div>
  )
})

export default WaypointMap
