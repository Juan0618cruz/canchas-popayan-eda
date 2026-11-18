/**
 * Capa MVC: Vista — VistaAdminLayout.tsx
 * Estructura y navegación lateral del portal administrativo de establecimientos.
 */

import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { LayoutDashboard, Calendar, DollarSign, Shield, Palette } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { DEFAULT_GENERAL_BG, resolveMediaUrl, useAppearanceStore } from '../store/appearanceStore'
import Navbar from '../components/Navbar'
import PageBackground from '../components/PageBackground'

const NAV_ITEMS = [
  { to: '/admin/canchas', label: 'Mis Canchas', icon: <LayoutDashboard size={18} /> },
  { to: '/admin/taquilla', label: 'Taquilla y Agenda', icon: <Calendar size={18} /> },
  { to: '/admin/pagos', label: 'Caja y Pagos', icon: <DollarSign size={18} /> },
  { to: '/admin/apariencia', label: 'Apariencia y Fondos', icon: <Palette size={18} /> },
]

export default function VistaAdminLayout() {
  const { user } = useAuthStore()
  const { fondoGeneralUrl } = useAppearanceStore()
  if (user?.rol !== 'ADMIN_ESTABLECIMIENTO') return <Navigate to="/catalogo" replace />

  const resolvedGeneralBg = resolveMediaUrl(fondoGeneralUrl, DEFAULT_GENERAL_BG)

  return (
    <PageBackground imageUrl={resolvedGeneralBg}>
      <Navbar />
      <div className="w-full max-w-7xl mx-auto px-4 py-6 flex-1">
        {/* Admin header */}
        <div
          className="rounded-2xl p-5 mb-6 text-white shadow-lg border border-emerald-800/40 bg-cover bg-center bg-no-repeat w-full app-banner-bg"
          style={{
            backgroundImage: `linear-gradient(95deg, rgba(6, 78, 59, 0.90), rgba(5, 46, 22, 0.78)), url("${resolvedGeneralBg}")`,
          }}
        >
          <div className="flex items-center gap-3">
            <Shield size={28} />
            <div>
              <h1 className="text-xl font-bold">Portal Administrativo</h1>
              <p className="text-green-100 text-sm">{user?.nombre} · Complejo Deportivo Balón de Oro</p>
            </div>
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-6 items-start">
          {/* Sidebar */}
          <aside className="w-full md:w-56 shrink-0">
            <nav className="bg-white/95 backdrop-blur-sm rounded-2xl border border-gray-200/90 shadow-lg overflow-hidden">
              {NAV_ITEMS.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-3.5 text-sm font-medium border-b border-gray-100 last:border-0 transition-colors ${
                      isActive
                        ? 'bg-green-50 text-green-700 border-l-4 border-l-green-600'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`
                  }
                >
                  {item.icon}
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </aside>

          {/* Content */}
          <main className="flex-1 w-full min-w-0 bg-white/90 backdrop-blur-sm rounded-2xl border border-gray-200/80 shadow-lg p-5 sm:p-6 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </PageBackground>
  )
}
