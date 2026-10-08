import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import BoatList from './pages/BoatList'
import BoatConsole from './pages/BoatConsole'
import History from './pages/History'
import UserManagement from './pages/UserManagement'
import RegionManagement from './pages/RegionManagement'

export default function App() {
  return (
    <Routes>
      {/* 公开路由 */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* 受保护路由 */}
      <Route
        path="/boats"
        element={
          <ProtectedRoute>
            <BoatList />
          </ProtectedRoute>
        }
      />
      <Route
        path="/boats/:boatId"
        element={
          <ProtectedRoute>
            <BoatConsole />
          </ProtectedRoute>
        }
      />
      <Route
        path="/boats/:boatId/history"
        element={
          <ProtectedRoute>
            <History />
          </ProtectedRoute>
        }
      />

      {/* 总管理员专属路由 */}
      <Route
        path="/admin/users"
        element={
          <AdminRoute>
            <UserManagement />
          </AdminRoute>
        }
      />
      <Route
        path="/admin/regions"
        element={
          <AdminRoute>
            <RegionManagement />
          </AdminRoute>
        }
      />

      {/* 默认重定向 */}
      <Route path="/" element={<Navigate to="/boats" replace />} />
      <Route path="*" element={<Navigate to="/boats" replace />} />
    </Routes>
  )
}
