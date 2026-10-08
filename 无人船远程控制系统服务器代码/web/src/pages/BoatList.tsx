import { useEffect, useState, useCallback } from 'react'
import { Plus, Ship, RefreshCw, Search, MapPin } from 'lucide-react'
import Layout from '../components/Layout'
import BoatCard from '../components/BoatCard'
import { useBoatWebSocket } from '../hooks/useBoatWebSocket'
import * as boatsApi from '../api/boats'
import * as regionsApi from '../api/regions'
import type { Boat, BoatStatus, Region } from '../types'

export default function BoatList() {
  const [boats, setBoats] = useState<Boat[]>([])
  const [regions, setRegions] = useState<Region[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [regionFilter, setRegionFilter] = useState<number | ''>('')
  const { getBoatStatus } = useBoatWebSocket()

  const loadBoats = useCallback(async () => {
    setLoading(true)
    try {
      const params: { search?: string; region_id?: number } = {}
      if (search.trim()) params.search = search.trim()
      if (regionFilter !== '') params.region_id = regionFilter
      const data = await boatsApi.listBoats(params)
      setBoats(data)
    } catch (err) {
      console.error('加载船列表失败', err)
    } finally {
      setLoading(false)
    }
  }, [search, regionFilter])

  const loadRegions = async () => {
    try {
      const data = await regionsApi.listRegions()
      setRegions(data)
    } catch (err) {
      console.error('加载区域列表失败', err)
    }
  }

  const handleDeleteBoat = async (boat: Boat) => {
    try {
      await boatsApi.deleteBoat(boat.id)
      setBoats((prev) => prev.filter((b) => b.id !== boat.id))
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  // 搜索防抖: 输入停止500ms后触发搜索
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput)
    }, 500)
    return () => clearTimeout(timer)
  }, [searchInput])

  useEffect(() => {
    loadBoats()
  }, [loadBoats])

  useEffect(() => {
    loadRegions()
  }, [])

  return (
    <Layout>
      <div className="p-3 sm:p-4 lg:p-6">
        {/* 头部 */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4 sm:mb-6">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-800">我的无人船</h1>
            <p className="text-gray-500 text-sm mt-1">共 {boats.length} 艘船</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={loadBoats}
              className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700 text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              <span className="hidden sm:inline">刷新</span>
            </button>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">添加船</span>
            </button>
          </div>
        </div>

        {/* 搜索和筛选栏 */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="搜索船名或4G ICCID..."
              className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div className="relative sm:w-48">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <select
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value === '' ? '' : parseInt(e.target.value))}
              className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none appearance-none cursor-pointer"
            >
              <option value="">全部区域</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* 船列表 */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-gray-400">加载中...</div>
          </div>
        ) : boats.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 bg-white rounded-xl border border-dashed border-gray-300">
            <Ship className="w-16 h-16 text-gray-300 mb-4" />
            <p className="text-gray-500 mb-4">还没有添加无人船</p>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" />
              添加第一艘船
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {boats.map((boat) => {
              const status = getBoatStatus(boat.boat_key)
              return <BoatCard key={boat.id} boat={boat} status={status} onDelete={handleDeleteBoat} />
            })}
          </div>
        )}
      </div>

      {/* 添加船弹窗 */}
      {showAddModal && (
        <AddBoatModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false)
            loadBoats()
          }}
        />
      )}
    </Layout>
  )
}

function AddBoatModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState('')
  const [mavlinkSysId, setMavlinkSysId] = useState(1)
  const [iccid, setIccid] = useState('')
  const [regionId, setRegionId] = useState<number | ''>('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [regions, setRegions] = useState<Region[]>([])

  useEffect(() => {
    regionsApi.listRegions().then(setRegions).catch(console.error)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!iccid.trim()) {
      setError('请填写4G ICCID号')
      return
    }
    setSaving(true)
    try {
      await boatsApi.createBoat({
        name,
        mavlink_sys_id: mavlinkSysId,
        iccid: iccid.trim(),
        region_id: regionId !== '' ? regionId : undefined,
        description: description || undefined,
      })
      onSuccess()
    } catch (err: any) {
      setError(err.response?.data?.detail || '添加失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-md p-6">
        <h2 className="text-xl font-bold mb-4">添加无人船</h2>
        {error && <div className="mb-4 p-2 bg-red-50 text-red-600 rounded text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">船名称 *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">MAVLink系统ID</label>
            <input
              type="number"
              min={1}
              max={255}
              value={mavlinkSysId}
              onChange={(e) => setMavlinkSysId(parseInt(e.target.value))}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <p className="text-xs text-gray-400 mt-1">多船可重复，默认1即可，仅单条连接内有效</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">4G ICCID *</label>
            <input
              type="text"
              value={iccid}
              onChange={(e) => setIccid(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="SIM卡背面20位ICCID号"
              required
              minLength={15}
            />
            <p className="text-xs text-gray-400 mt-1">物联网卡全球唯一标识，用于船身份自动识别，必须填写</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">所属区域</label>
            <select
              value={regionId}
              onChange={(e) => setRegionId(e.target.value === '' ? '' : parseInt(e.target.value))}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none cursor-pointer"
            >
              <option value="">未分类</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">选择船所在的养殖区域，便于分类管理</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">描述 (可选)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              rows={2}
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? '保存中...' : '添加'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
