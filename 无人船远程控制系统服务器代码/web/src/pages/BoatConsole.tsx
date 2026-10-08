import { useEffect, useState, useCallback } from 'react'
import { useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Navigation, Gauge, MapPin, Battery, Wifi, Thermometer,
  Radio, Play, Square, RotateCcw, Home, Video, Settings, Trash2,
  Upload, Send, AlertTriangle, CheckCircle, XCircle,
} from 'lucide-react'
import Layout from '../components/Layout'
import WaypointMap from '../components/WaypointMap'
import type { WaypointMapRef } from '../components/WaypointMap'
import VideoPlayer from '../components/VideoPlayer'
import BatteryIndicator from '../components/BatteryIndicator'
import { useBoatWebSocket } from '../hooks/useBoatWebSocket'
import * as boatsApi from '../api/boats'
import * as controlApi from '../api/control'
import * as missionsApi from '../api/missions'
import * as telemetryApi from '../api/telemetry'
import type { Boat, BoatStatus, Mission, Waypoint, TelemetryRecord } from '../types'
import { formatSpeed, formatHeading, formatSignal, getModeColor } from '../utils/format'

export default function BoatConsole() {
  const { boatId } = useParams<{ boatId: string }>()
  const navigate = useNavigate()
  const [boat, setBoat] = useState<Boat | null>(null)
  const [missions, setMissions] = useState<Mission[]>([])
  const [history, setHistory] = useState<TelemetryRecord[]>([])
  const [selectedMissionId, setSelectedMissionId] = useState<number | null>(null)
  const [showVideo, setShowVideo] = useState(false)
  const [editingPath, setEditingPath] = useState(false)
  const [draftWaypoints, setDraftWaypoints] = useState<Waypoint[]>([])
  const [toast, setToast] = useState<{ type: 'success' | 'error' | 'warning'; msg: string } | null>(null)
  const { getBoatStatus } = useBoatWebSocket()
  const mapRef = useRef<WaypointMapRef>(null)

  const status: BoatStatus | undefined = boat ? getBoatStatus(boat.boat_key) : undefined

  const showToast = useCallback((type: 'success' | 'error' | 'warning', msg: string) => {
    setToast({ type, msg })
    setTimeout(() => setToast(null), 3000)
  }, [])

  // 加载船信息和任务列表
  useEffect(() => {
    if (!boatId) return
    const id = parseInt(boatId)
    boatsApi.getBoat(id).then(setBoat).catch(console.error)
    missionsApi.listMissions(id).then((data) => {
      setMissions(data)
      // 默认选中最新任务 (显示设定航线)
      if (data.length > 0) {
        setSelectedMissionId(data[0].id)
      }
    }).catch(console.error)
    // 加载历史轨迹 (最近24小时, 最多2000条)
    telemetryApi.getTelemetryHistory(id, { limit: 2000 })
      .then(setHistory)
      .catch(console.error)
  }, [boatId])

  const handleCommand = async (fn: () => Promise<any>, successMsg: string) => {
    if (!boatId) return
    try {
      await fn()
      showToast('success', successMsg)
    } catch (err: any) {
      showToast('error', err.response?.data?.detail || '操作失败')
    }
  }

  const startEditingPath = () => {
    setDraftWaypoints([])
    setEditingPath(true)
  }

  const saveAndUploadPath = async () => {
    if (!boatId || draftWaypoints.length === 0) return
    try {
      // 1. 创建任务
      const mission = await missionsApi.createMission(parseInt(boatId), {
        name: `路径_${new Date().toLocaleString('zh-CN')}`,
        waypoints: draftWaypoints,
      })
      // 2. 上传到船
      await missionsApi.uploadMission(parseInt(boatId), mission.id)
      showToast('success', `路径已上传 (${draftWaypoints.length}个航点)`)
      setEditingPath(false)
      setDraftWaypoints([])
      // 选中新创建的任务, 地图显示设定航线
      setSelectedMissionId(mission.id)
      // 刷新任务列表
      missionsApi.listMissions(parseInt(boatId)).then(setMissions)
    } catch (err: any) {
      showToast('error', err.response?.data?.detail || '上传失败')
    }
  }

  const executeMission = async (missionId: number) => {
    if (!boatId) return
    try {
      await missionsApi.executeMission(parseInt(boatId), missionId)
      showToast('success', '任务已开始执行')
    } catch (err: any) {
      showToast('error', err.response?.data?.detail || '执行失败')
    }
  }

  if (!boat) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-full">
          <div className="text-gray-400">加载中...</div>
        </div>
      </Layout>
    )
  }

  const online = status?.online ?? false

  // 当前选中显示的任务 (设定航线)
  const selectedMission = missions.find((m) => m.id === selectedMissionId) || null

  return (
    <Layout>
      <div className="flex flex-col h-full">
        {/* 顶部栏 - 响应式 */}
        <div className="bg-white border-b px-3 sm:px-6 py-2 sm:py-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <button
              onClick={() => navigate('/boats')}
              className="p-2 hover:bg-gray-100 rounded-lg flex-shrink-0"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div className="min-w-0">
              <h1 className="text-base sm:text-lg font-bold text-gray-800 truncate">{boat.name}</h1>
              <div className="flex items-center gap-2 text-xs">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${online ? 'bg-green-500' : 'bg-gray-300'}`} />
                <span className={online ? 'text-green-600' : 'text-gray-400'}>
                  {online ? '在线' : '离线'}
                </span>
                {status?.flight_mode && (
                  <span className={`px-2 py-0.5 rounded ${getModeColor(status.flight_mode)}`}>
                    {status.flight_mode}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
            <button
              onClick={() => setShowVideo(!showVideo)}
              className={`flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-2 rounded-lg text-sm ${showVideo ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              <Video className="w-4 h-4" />
              <span className="hidden sm:inline">视频</span>
            </button>
            <button
              onClick={() => navigate(`/boats/${boatId}/history`)}
              className="flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 text-sm"
            >
              <Navigation className="w-4 h-4" />
              <span className="hidden sm:inline">历史</span>
            </button>
          </div>
        </div>

        {/* 主内容区 - 响应式布局 */}
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
          {/* 仪表盘 (手机端在下, 桌面端在左) */}
          <div className="w-full lg:w-80 bg-white border-b lg:border-b-0 lg:border-r overflow-y-auto p-3 lg:p-4 space-y-3 lg:space-y-4 order-2 lg:order-1 max-h-[50vh] lg:max-h-none">
            {/* 电池 */}
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <Battery className="w-4 h-4" />
                电池
              </div>
              <BatteryIndicator
                percent={status?.battery_remaining ?? null}
                voltage={status?.battery_voltage}
                current={status?.battery_current}
                size="lg"
              />
              {status?.battery_current !== null && status?.battery_current !== undefined && (
                <div className="text-xs text-gray-400 mt-1">
                  电流: {status.battery_current.toFixed(1)}A
                </div>
              )}
            </div>

            {/* 航行状态 */}
            <div className="bg-gray-50 rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <Gauge className="w-4 h-4" />
                航行状态
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <div className="text-gray-400 text-xs">速度</div>
                  <div className="font-semibold text-gray-800">{formatSpeed(status?.groundspeed ?? null)}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs">航向</div>
                  <div className="font-semibold text-gray-800">{formatHeading(status?.heading ?? null)}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs">当前航点</div>
                  <div className="font-semibold text-gray-800">
                    {status?.current_waypoint !== null && status?.current_waypoint !== undefined
                      ? `#${status.current_waypoint}` : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs">解锁</div>
                  <div className={`font-semibold ${status?.armed ? 'text-green-600' : 'text-gray-400'}`}>
                    {status?.armed ? '是' : '否'}
                  </div>
                </div>
              </div>
            </div>

            {/* 位置 - 点击定位到船 */}
            <div
              className="bg-gray-50 rounded-lg p-3 cursor-pointer hover:bg-gray-100 hover:ring-2 hover:ring-blue-400 transition-all"
              onClick={() => mapRef.current?.focusToBoat()}
              title="点击在地图中定位到船的位置"
            >
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <MapPin className="w-4 h-4 text-blue-500" />
                <span>位置</span>
                <span className="ml-auto text-xs text-blue-500">点击定位</span>
              </div>
              <div className="text-sm font-mono text-gray-700">
                {status?.lat ? `${status.lat.toFixed(6)}, ${status.lon?.toFixed(6)}` : '--'}
              </div>
              {status?.gps_fix_type && (
                <div className="text-xs text-gray-400 mt-1">
                  GPS: {status.gps_fix_type} ({status.gps_satellites_visible ?? '--'}星)
                </div>
              )}
            </div>

            {/* 饲料 */}
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-gray-500">饲料余量</span>
                <span className="font-semibold text-gray-800">
                  {status?.feed_level !== null && status?.feed_level !== undefined
                    ? `${Math.round(status.feed_level)}%` : '--'}
                </span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${(status?.feed_level ?? 0) > 20 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${status?.feed_level ?? 0}%` }}
                />
              </div>
            </div>

            {/* 通信 */}
            <div className="bg-gray-50 rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <Wifi className="w-4 h-4" />
                通信
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">4G信号</span>
                <span className="font-semibold text-gray-800">{formatSignal(status?.cellular_csq ?? null)}</span>
              </div>
              {status?.box_temperature && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400 flex items-center gap-1">
                    <Thermometer className="w-3 h-3" /> 箱温
                  </span>
                  <span className="font-semibold text-gray-800">{status.box_temperature.toFixed(1)}℃</span>
                </div>
              )}
            </div>

            {/* 状态消息 */}
            {status?.last_status_text && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <div className="text-xs text-yellow-700">{status.last_status_text}</div>
                </div>
              </div>
            )}
          </div>

          {/* 地图区 (手机端在上, 桌面端在右) */}
          <div className="flex-1 flex flex-col p-2 lg:p-4 gap-2 lg:gap-4 order-1 lg:order-2 min-h-[300px] lg:min-h-0">
            {/* 地图 */}
            <div className="flex-1 relative">
              <WaypointMap
                ref={mapRef}
                boatStatus={status || null}
                waypoints={editingPath ? draftWaypoints : (selectedMission?.waypoints || [])}
                history={history}
                editable={editingPath}
                onWaypointsChange={setDraftWaypoints}
                height="100%"
              />

              {/* 路径编辑工具栏 */}
              {editingPath && (
                <div className="absolute top-3 right-3 bg-white rounded-lg shadow-lg p-2 flex gap-2 flex-wrap">
                  <span className="text-sm text-gray-500 px-2 py-1">
                    {draftWaypoints.length} 个航点
                  </span>
                  <button
                    onClick={() => setDraftWaypoints([])}
                    className="p-2 text-gray-500 hover:bg-gray-100 rounded"
                    title="清空"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={saveAndUploadPath}
                    disabled={draftWaypoints.length === 0}
                    className="flex items-center gap-1 px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                  >
                    <Upload className="w-4 h-4" />
                    保存并上传
                  </button>
                  <button
                    onClick={() => { setEditingPath(false); setDraftWaypoints([]) }}
                    className="p-2 text-gray-500 hover:bg-gray-100 rounded"
                  >
                    取消
                  </button>
                </div>
              )}
            </div>

            {/* 视频 */}
            {showVideo && (
              <div className="h-40 lg:h-48">
                <VideoPlayer boatKey={boat.boat_key} className="h-full" />
              </div>
            )}

            {/* 底部控制栏 */}
            <div className="bg-white rounded-lg border p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">遥控操作</span>
                {!online && <span className="text-xs text-red-500">船离线, 无法操作</span>}
              </div>
              <div className="flex gap-2 flex-wrap">
                <button
                  disabled={!online}
                  onClick={() => handleCommand(
                    () => controlApi.startAuto(boat.id),
                    '已切换AUTO模式'
                  )}
                  className="flex items-center gap-1 px-3 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-40"
                >
                  <Play className="w-4 h-4" />
                  开始航行
                </button>
                <button
                  disabled={!online}
                  onClick={() => handleCommand(
                    () => controlApi.returnToLaunch(boat.id),
                    '返航指令已发送'
                  )}
                  className="flex items-center gap-1 px-3 py-2 bg-orange-500 text-white rounded-lg text-sm hover:bg-orange-600 disabled:opacity-40"
                >
                  <Home className="w-4 h-4" />
                  返航
                </button>
                <button
                  disabled={!online}
                  onClick={() => handleCommand(
                    () => controlApi.emergencyStop(boat.id),
                    '紧急停车'
                  )}
                  className="flex items-center gap-1 px-3 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 disabled:opacity-40"
                >
                  <Square className="w-4 h-4" />
                  紧急停车
                </button>
                <div className="w-px bg-gray-200 mx-1 hidden sm:block" />
                <button
                  disabled={!online}
                  onClick={() => handleCommand(
                    () => controlApi.feedOn(boat.id),
                    '投料已开启'
                  )}
                  className="flex items-center gap-1 px-3 py-2 bg-amber-500 text-white rounded-lg text-sm hover:bg-amber-600 disabled:opacity-40"
                >
                  开投料
                </button>
                <button
                  disabled={!online}
                  onClick={() => handleCommand(
                    () => controlApi.feedOff(boat.id),
                    '投料已关闭'
                  )}
                  className="flex items-center gap-1 px-3 py-2 bg-gray-500 text-white rounded-lg text-sm hover:bg-gray-600 disabled:opacity-40"
                >
                  关投料
                </button>
                <div className="w-px bg-gray-200 mx-1 hidden sm:block" />
                <button
                  onClick={startEditingPath}
                  className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
                >
                  <Settings className="w-4 h-4" />
                  编辑路径
                </button>
              </div>

              {/* 任务列表 */}
              {missions.length > 0 && (
                <div className="mt-3 pt-3 border-t">
                  <div className="text-xs text-gray-500 mb-2">已保存任务 (点击显示航线, 点▶执行)</div>
                  <div className="flex gap-2 flex-wrap">
                    {missions.slice(0, 5).map((m) => (
                      <div
                        key={m.id}
                        className={`flex items-center gap-1 px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
                          selectedMissionId === m.id ? 'bg-blue-100 text-blue-700 border border-blue-300' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                        }`}
                        onClick={() => setSelectedMissionId(m.id)}
                        title={m.name}
                      >
                        <span>{m.name.length > 10 ? m.name.slice(0, 10) + '...' : m.name}</span>
                        <span className="text-gray-400">({m.waypoints.length}点)</span>
                        <button
                          disabled={!online}
                          onClick={(e) => { e.stopPropagation(); executeMission(m.id) }}
                          className="ml-1 text-green-600 hover:text-green-700 disabled:opacity-40"
                          title="执行此任务"
                        >
                          ▶
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Toast提示 */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 animate-pulse">
          <div className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white ${
            toast.type === 'success' ? 'bg-green-600' :
            toast.type === 'error' ? 'bg-red-600' : 'bg-yellow-500'
          }`}>
            {toast.type === 'success' ? <CheckCircle className="w-5 h-5" /> :
             toast.type === 'error' ? <XCircle className="w-5 h-5" /> :
             <AlertTriangle className="w-5 h-5" />}
            <span className="text-sm">{toast.msg}</span>
          </div>
        </div>
      )}
    </Layout>
  )
}
