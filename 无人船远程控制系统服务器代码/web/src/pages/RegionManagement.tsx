import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Edit2, Trash2, MapPin, Users } from 'lucide-react'
import Layout from '../components/Layout'
import * as regionsApi from '../api/regions'
import type { Region } from '../types'

export default function RegionManagement() {
  const [regions, setRegions] = useState<Region[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingRegion, setEditingRegion] = useState<Region | null>(null)

  const loadRegions = async () => {
    setLoading(true)
    try {
      const data = await regionsApi.listRegions()
      setRegions(data)
    } catch (err) {
      console.error('加载区域列表失败', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRegions()
  }, [])

  const handleDelete = async (region: Region) => {
    if (!window.confirm(`确定要删除区域「${region.name}」吗？关联的用户和船将变为未分类。`)) return
    try {
      await regionsApi.deleteRegion(region.id)
      loadRegions()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">区域管理</h1>
            <p className="text-gray-500 text-sm mt-1">共 {regions.length} 个区域</p>
          </div>
          <div className="flex gap-2">
            <button onClick={loadRegions} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700">
              <RefreshCw className="w-4 h-4" /> 刷新
            </button>
            <button onClick={() => setShowCreateModal(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <Plus className="w-4 h-4" /> 添加区域
            </button>
          </div>
        </div>

        {/* 区域卡片列表 */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-gray-400">加载中...</div>
          </div>
        ) : regions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 bg-white rounded-xl border border-dashed border-gray-300">
            <MapPin className="w-16 h-16 text-gray-300 mb-4" />
            <p className="text-gray-500 mb-4">还没有添加区域</p>
            <button onClick={() => setShowCreateModal(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <Plus className="w-4 h-4" /> 添加第一个区域
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {regions.map((region) => (
              <div key={region.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                      <MapPin className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-800">{region.name}</h3>
                      <p className="text-xs text-gray-400">ID: {region.id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setEditingRegion(region)} className="p-1.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50" title="编辑">
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleDelete(region)} className="p-1.5 rounded text-gray-400 hover:text-red-600 hover:bg-red-50" title="删除">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                {region.description && (
                  <p className="text-sm text-gray-500 mb-3">{region.description}</p>
                )}
                <div className="flex items-center gap-1 text-xs text-gray-400">
                  <Users className="w-3 h-3" />
                  <span>可分配地方管理员和船只</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 创建区域弹窗 */}
      {showCreateModal && (
        <RegionFormModal
          mode="create"
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => { setShowCreateModal(false); loadRegions() }}
        />
      )}

      {/* 编辑区域弹窗 */}
      {editingRegion && (
        <RegionFormModal
          mode="edit"
          region={editingRegion}
          onClose={() => setEditingRegion(null)}
          onSuccess={() => { setEditingRegion(null); loadRegions() }}
        />
      )}
    </Layout>
  )
}

// ============================================================
// 区域表单弹窗
// ============================================================
function RegionFormModal({ mode, region, onClose, onSuccess }: {
  mode: 'create' | 'edit'
  region?: Region
  onClose: () => void
  onSuccess: () => void
}) {
  const [name, setName] = useState(region?.name || '')
  const [description, setDescription] = useState(region?.description || '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!name.trim()) {
      setError('请输入区域名称')
      return
    }
    setSaving(true)
    try {
      if (mode === 'create') {
        await regionsApi.createRegion({ name: name.trim(), description: description || undefined })
      } else if (region) {
        await regionsApi.updateRegion(region.id, { name: name.trim(), description: description || undefined })
      }
      onSuccess()
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-md p-6">
        <h2 className="text-xl font-bold mb-4">{mode === 'create' ? '添加区域' : '编辑区域'}</h2>
        {error && <div className="mb-4 p-2 bg-red-50 text-red-600 rounded text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">区域名称 *</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="如: 广州南沙、珠海、台山" className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="区域描述信息" className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
            <button type="submit" disabled={saving} className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
