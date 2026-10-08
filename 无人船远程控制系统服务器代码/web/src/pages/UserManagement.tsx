import { useEffect, useState } from 'react'
import { Plus, Search, RefreshCw, Edit2, Trash2, Key, UserX, UserCheck, Shield, MapPin } from 'lucide-react'
import Layout from '../components/Layout'
import * as usersApi from '../api/users'
import * as regionsApi from '../api/regions'
import type { User, Region } from '../types'

const ROLE_LABELS: Record<string, { label: string; color: string }> = {
  admin: { label: '总管理员', color: 'bg-red-100 text-red-700' },
  regional_admin: { label: '地方管理员', color: 'bg-blue-100 text-blue-700' },
  user: { label: '普通用户', color: 'bg-gray-100 text-gray-700' },
}

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([])
  const [regions, setRegions] = useState<Region[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [resetPwdUser, setResetPwdUser] = useState<User | null>(null)

  const loadUsers = async () => {
    setLoading(true)
    try {
      const params: { search?: string; role?: string } = {}
      if (search.trim()) params.search = search.trim()
      if (roleFilter) params.role = roleFilter
      const data = await usersApi.listUsers(params)
      setUsers(data)
    } catch (err) {
      console.error('加载用户列表失败', err)
    } finally {
      setLoading(false)
    }
  }

  const loadRegions = async () => {
    try {
      const data = await regionsApi.listRegions()
      setRegions(data)
    } catch (err) {
      console.error('加载区域列表失败', err)
    }
  }

  useEffect(() => {
    loadRegions()
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), 500)
    return () => clearTimeout(timer)
  }, [searchInput])

  useEffect(() => {
    loadUsers()
  }, [search, roleFilter])

  const handleToggleActive = async (user: User) => {
    if (!window.confirm(`确定要${user.is_active ? '禁用' : '启用'}用户「${user.username}」吗？`)) return
    try {
      await usersApi.updateUser(user.id, { is_active: !user.is_active })
      loadUsers()
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败')
    }
  }

  const handleDelete = async (user: User) => {
    if (!window.confirm(`确定要删除用户「${user.username}」吗？此操作不可恢复。`)) return
    try {
      await usersApi.deleteUser(user.id)
      loadUsers()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">用户管理</h1>
            <p className="text-gray-500 text-sm mt-1">共 {users.length} 个用户</p>
          </div>
          <div className="flex gap-2">
            <button onClick={loadUsers} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700">
              <RefreshCw className="w-4 h-4" /> 刷新
            </button>
            <button onClick={() => setShowCreateModal(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <Plus className="w-4 h-4" /> 添加用户
            </button>
          </div>
        </div>

        {/* 搜索筛选 */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="搜索用户名/姓名/邮箱..." className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="sm:w-44 px-4 py-2 bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none cursor-pointer">
            <option value="">全部角色</option>
            <option value="admin">总管理员</option>
            <option value="regional_admin">地方管理员</option>
            <option value="user">普通用户</option>
          </select>
        </div>

        {/* 用户列表 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">用户名</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">姓名</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">角色</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">负责区域</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-600">状态</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr><td colSpan={6} className="text-center py-12 text-gray-400">加载中...</td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-12 text-gray-400">暂无用户</td></tr>
              ) : users.map((user) => {
                const roleInfo = ROLE_LABELS[user.role] || ROLE_LABELS.user
                return (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-800">{user.username}</div>
                      {user.email && <div className="text-xs text-gray-400">{user.email}</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{user.full_name || '--'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${roleInfo.color}`}>
                        <Shield className="w-3 h-3" /> {roleInfo.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {user.region_name ? (
                        <span className="inline-flex items-center gap-1 text-sm text-gray-600">
                          <MapPin className="w-3 h-3" /> {user.region_name}
                        </span>
                      ) : '--'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-sm ${user.is_active ? 'text-green-600' : 'text-gray-400'}`}>
                        {user.is_active ? <UserCheck className="w-4 h-4" /> : <UserX className="w-4 h-4" />}
                        {user.is_active ? '正常' : '已禁用'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setEditingUser(user)} className="p-1.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50" title="编辑">
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button onClick={() => setResetPwdUser(user)} className="p-1.5 rounded text-gray-400 hover:text-amber-600 hover:bg-amber-50" title="重置密码">
                          <Key className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleToggleActive(user)} className={`p-1.5 rounded ${user.is_active ? 'text-gray-400 hover:text-orange-600 hover:bg-orange-50' : 'text-gray-400 hover:text-green-600 hover:bg-green-50'}`} title={user.is_active ? '禁用' : '启用'}>
                          {user.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                        </button>
                        <button onClick={() => handleDelete(user)} className="p-1.5 rounded text-gray-400 hover:text-red-600 hover:bg-red-50" title="删除">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 创建用户弹窗 */}
      {showCreateModal && (
        <UserFormModal
          mode="create"
          regions={regions}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => { setShowCreateModal(false); loadUsers() }}
        />
      )}

      {/* 编辑用户弹窗 */}
      {editingUser && (
        <UserFormModal
          mode="edit"
          user={editingUser}
          regions={regions}
          onClose={() => setEditingUser(null)}
          onSuccess={() => { setEditingUser(null); loadUsers() }}
        />
      )}

      {/* 重置密码弹窗 */}
      {resetPwdUser && (
        <ResetPasswordModal
          user={resetPwdUser}
          onClose={() => setResetPwdUser(null)}
          onSuccess={() => { setResetPwdUser(null); alert('密码重置成功') }}
        />
      )}
    </Layout>
  )
}

// ============================================================
// 用户表单弹窗 (创建/编辑)
// ============================================================
function UserFormModal({ mode, user, regions, onClose, onSuccess }: {
  mode: 'create' | 'edit'
  user?: User
  regions: Region[]
  onClose: () => void
  onSuccess: () => void
}) {
  const [username, setUsername] = useState(user?.username || '')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [phone, setPhone] = useState(user?.phone || '')
  const [role, setRole] = useState(user?.role || 'user')
  const [regionId, setRegionId] = useState<number | ''>(user?.region_id ?? '')
  const [isActive, setIsActive] = useState(user?.is_active ?? true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (mode === 'create' && !password) {
      setError('请设置密码')
      return
    }
    if (role === 'regional_admin' && regionId === '') {
      setError('地方管理员必须选择负责区域')
      return
    }
    setSaving(true)
    try {
      if (mode === 'create') {
        await usersApi.createUser({
          username, password,
          full_name: fullName || undefined,
          email: email || undefined,
          phone: phone || undefined,
          role,
          region_id: regionId !== '' ? regionId : undefined,
        })
      } else if (user) {
        await usersApi.updateUser(user.id, {
          full_name: fullName || undefined,
          email: email || undefined,
          phone: phone || undefined,
          role,
          region_id: regionId !== '' ? regionId : undefined,
          is_active: isActive,
        })
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
      <div className="bg-white rounded-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold mb-4">{mode === 'create' ? '添加用户' : '编辑用户'}</h2>
        {error && <div className="mb-4 p-2 bg-red-50 text-red-600 rounded text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">用户名 *</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} disabled={mode === 'edit'} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-100" required />
            </div>
            {mode === 'create' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">密码 *</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required minLength={6} />
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">姓名</label>
              <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">电话</label>
              <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">角色 *</label>
              <select value={role} onChange={(e) => setRole(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none cursor-pointer">
                <option value="user">普通用户</option>
                <option value="regional_admin">地方管理员</option>
                <option value="admin">总管理员</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">负责区域</label>
              <select value={regionId} onChange={(e) => setRegionId(e.target.value === '' ? '' : parseInt(e.target.value))} disabled={role !== 'regional_admin'} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none cursor-pointer disabled:bg-gray-100 disabled:cursor-not-allowed">
                <option value="">--</option>
                {regions.map((r) => (<option key={r.id} value={r.id}>{r.name}</option>))}
              </select>
              {role === 'regional_admin' && <p className="text-xs text-gray-400 mt-1">地方管理员必须选择区域</p>}
            </div>
          </div>
          {mode === 'edit' && (
            <div className="flex items-center gap-2">
              <input type="checkbox" id="isActive" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="w-4 h-4" />
              <label htmlFor="isActive" className="text-sm text-gray-700">账号启用</label>
            </div>
          )}
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
            <button type="submit" disabled={saving} className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ============================================================
// 重置密码弹窗
// ============================================================
function ResetPasswordModal({ user, onClose, onSuccess }: {
  user: User
  onClose: () => void
  onSuccess: () => void
}) {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (newPassword.length < 6) {
      setError('密码至少6位')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    setSaving(true)
    try {
      await usersApi.resetPassword(user.id, newPassword)
      onSuccess()
    } catch (err: any) {
      setError(err.response?.data?.detail || '重置失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-md p-6">
        <h2 className="text-xl font-bold mb-4">重置密码</h2>
        <p className="text-sm text-gray-500 mb-4">为用户「{user.username}」设置新密码</p>
        {error && <div className="mb-4 p-2 bg-red-50 text-red-600 rounded text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">新密码 *</label>
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required minLength={6} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">确认密码 *</label>
            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
            <button type="submit" disabled={saving} className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">{saving ? '重置中...' : '重置密码'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
