import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Calendar, Play, Pause, SkipBack, SkipForward } from 'lucide-react'
import Layout from '../components/Layout'
import WaypointMap from '../components/WaypointMap'
import * as telemetryApi from '../api/telemetry'
import * as boatsApi from '../api/boats'
import type { Boat, TelemetryRecord } from '../types'
import { formatSpeed, formatTime } from '../utils/format'

export default function History() {
  const { boatId } = useParams<{ boatId: string }>()
  const navigate = useNavigate()
  const [boat, setBoat] = useState<Boat | null>(null)
  const [records, setRecords] = useState<TelemetryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [hours, setHours] = useState(24)
  const [playIndex, setPlayIndex] = useState(0)
  const [playing, setPlaying] = useState(false)

  // 加载船信息
  useEffect(() => {
    if (!boatId) return
    boatsApi.getBoat(parseInt(boatId)).then(setBoat).catch(console.error)
  }, [boatId])

  // 加载历史数据
  const loadHistory = async () => {
    if (!boatId) return
    setLoading(true)
    try {
      const end = new Date()
      const start = new Date(end.getTime() - hours * 3600 * 1000)
      const data = await telemetryApi.getTelemetryHistory(parseInt(boatId), {
        start: start.toISOString(),
        end: end.toISOString(),
        limit: 5000,
      })
      setRecords(data)
      setPlayIndex(data.length > 0 ? data.length - 1 : 0)
    } catch (err) {
      console.error('加载历史失败', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [boatId, hours])

  // 播放控制
  useEffect(() => {
    if (!playing || records.length === 0) return
    const timer = setInterval(() => {
      setPlayIndex((prev) => {
        if (prev >= records.length - 1) {
          setPlaying(false)
          return prev
        }
        return prev + 1
      })
    }, 200)
    return () => clearInterval(timer)
  }, [playing, records.length])

  const currentRecord = records[playIndex]
  const trajectory = useMemo(() => records.slice(0, playIndex + 1), [records, playIndex])

  return (
    <Layout>
      <div className="flex flex-col h-full">
        {/* 顶部栏 */}
        <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate(`/boats/${boatId}`)} className="p-2 hover:bg-gray-100 rounded-lg">
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-lg font-bold text-gray-800">{boat?.name || '船'} - 历史轨迹</h1>
              <p className="text-xs text-gray-400">共 {records.length} 条记录</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            <select
              value={hours}
              onChange={(e) => setHours(parseInt(e.target.value))}
              className="px-3 py-1.5 border rounded-lg text-sm"
            >
              <option value={1}>最近1小时</option>
              <option value={6}>最近6小时</option>
              <option value={24}>最近24小时</option>
              <option value={72}>最近3天</option>
              <option value={168}>最近7天</option>
            </select>
            <button onClick={loadHistory} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              刷新
            </button>
          </div>
        </div>

        {/* 主内容 */}
        <div className="flex-1 flex overflow-hidden">
          {/* 地图 */}
          <div className="flex-1 p-4">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-gray-400">加载中...</div>
              </div>
            ) : records.length === 0 ? (
              <div className="flex items-center justify-center h-full bg-white rounded-lg border">
                <div className="text-center text-gray-400">
                  <Calendar className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>暂无历史数据</p>
                </div>
              </div>
            ) : (
              <WaypointMap history={trajectory} height="100%" />
            )}
          </div>

          {/* 右侧信息面板 */}
          <div className="w-72 bg-white border-l p-4 overflow-y-auto">
            {currentRecord && (
              <div className="space-y-4">
                <div className="bg-blue-50 rounded-lg p-3">
                  <div className="text-xs text-blue-500 mb-1">当前时间点</div>
                  <div className="font-semibold text-blue-800">{formatTime(currentRecord.timestamp)}</div>
                  <div className="text-xs text-blue-400 mt-1">
                    进度: {playIndex + 1} / {records.length}
                  </div>
                </div>

                <div className="space-y-3">
                  <InfoRow label="纬度" value={currentRecord.lat?.toFixed(6) || '--'} />
                  <InfoRow label="经度" value={currentRecord.lon?.toFixed(6) || '--'} />
                  <InfoRow label="航向" value={currentRecord.heading ? `${Math.round(currentRecord.heading)}°` : '--'} />
                  <InfoRow label="速度" value={formatSpeed(currentRecord.groundspeed)} />
                  <InfoRow label="电量" value={currentRecord.battery_remaining !== null ? `${currentRecord.battery_remaining}%` : '--'} />
                  <InfoRow label="模式" value={currentRecord.flight_mode || '--'} />
                  <InfoRow label="航点" value={currentRecord.current_waypoint !== null ? `#${currentRecord.current_waypoint}` : '--'} />
                  <InfoRow label="饲料" value={currentRecord.feed_level !== null ? `${Math.round(currentRecord.feed_level)}%` : '--'} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 底部播放控制 */}
        {records.length > 0 && (
          <div className="bg-white border-t px-6 py-3">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setPlayIndex(0)}
                className="p-2 hover:bg-gray-100 rounded"
              >
                <SkipBack className="w-5 h-5 text-gray-600" />
              </button>
              <button
                onClick={() => setPlaying(!playing)}
                className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
              </button>
              <button
                onClick={() => setPlayIndex(records.length - 1)}
                className="p-2 hover:bg-gray-100 rounded"
              >
                <SkipForward className="w-5 h-5 text-gray-600" />
              </button>

              <input
                type="range"
                min={0}
                max={records.length - 1}
                value={playIndex}
                onChange={(e) => setPlayIndex(parseInt(e.target.value))}
                className="flex-1"
              />
              <span className="text-sm text-gray-500 w-32 text-right">
                {formatTime(currentRecord?.timestamp || '')}
              </span>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-gray-400">{label}</span>
      <span className="text-sm font-medium text-gray-800">{value}</span>
    </div>
  )
}
