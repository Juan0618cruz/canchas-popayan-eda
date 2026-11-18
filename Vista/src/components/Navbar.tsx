import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { Menu, X, User, LogOut, Shield, Activity } from 'lucide-react'

function SoccerBallIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-5 h-5 text-white"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="9.5" />
      <polygon points="12 7.5 16 10.4 14.5 15 9.5 15 8 10.4" fill="currentColor" fillOpacity="0.25" />
      <line x1="12" y1="2.5" x2="12" y2="7.5" />
      <line x1="21" y1="9" x2="16" y2="10.4" />
      <line x1="17.6" y1="19.6" x2="14.5" y2="15" />
      <line x1="6.4" y1="19.6" x2="9.5" y2="15" />
      <line x1="3" y1="9" x2="8" y2="10.4" />
    </svg>
  )
}

export default function Navbar() {
  const { isAuthenticated, user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const isAdmin = isAuthenticated && (user?.rol === 'ADMIN_ESTABLECIMIENTO' || user?.rol?.toLowerCase() === 'admin')
  const isNormalUser = isAuthenticated && !isAdmin

  const handleLogout = () => {
    logout()
    navigate('/')
    setMenuOpen(false)
  }

  const navLinkClass = (path: string) => {
    const active = location.pathname === path || (path !== '/' && location.pathname.startsWith(path))
    return `px-3.5 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-1.5 ${
      active
        ? 'bg-emerald-50 text-emerald-700 font-semibold'
        : 'text-gray-700 hover:text-emerald-700 hover:bg-emerald-50/60'
    }`
  }

  return (
    <nav className="bg-white border-b border-gray-100 sticky top-0 z-40 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-[68px]">
          {/* Logo & Título */}
          <Link to="/" className="group flex items-center gap-3 shrink-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-700 flex items-center justify-center shadow-sm shadow-emerald-600/25 group-hover:scale-105 transition-transform">
              <SoccerBallIcon />
            </div>
            <div className="flex flex-col leading-none">
              <span className="text-lg font-extrabold tracking-tight text-gray-900">
                Canchas <span className="text-emerald-600">Popayán</span>
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-gray-500 mt-1 hidden sm:block">
                Complejos Sintéticos
              </span>
            </div>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-2">
            <Link to="/catalogo" className={navLinkClass('/catalogo')}>
              Catálogo
            </Link>
            {isAdmin && (
              <Link
                to="/reportes"
                className={
                  location.pathname.startsWith('/reportes') || location.pathname.startsWith('/monitor')
                    ? 'px-3.5 py-2 rounded-xl text-sm transition-all flex items-center gap-1.5 bg-emerald-50 text-emerald-700 font-semibold'
                    : 'px-3.5 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-1.5 text-gray-700 hover:text-emerald-700 hover:bg-emerald-50/60'
                }
              >
                <Activity size={15} />
                Reportes
              </Link>
            )}
            {isNormalUser && (
              <Link to="/mis-reservas" className={navLinkClass('/mis-reservas')}>
                Mis Reservas
              </Link>
            )}
            {isAdmin && (
              <Link to="/admin/taquilla" className={navLinkClass('/admin')}>
                <Shield size={15} />
                Portal Admin
              </Link>
            )}
          </div>

          {/* Desktop auth */}
          <div className="hidden md:flex items-center gap-3">
            {isAuthenticated && user ? (
              <>
                <div className="flex items-center gap-2 pr-2 border-r border-gray-200">
                  <span className="text-sm font-medium text-gray-700">{user.nombre}</span>
                  {user.rol === 'ADMIN_ESTABLECIMIENTO' && (
                    <span className="badge bg-emerald-100 text-emerald-800 font-semibold">Admin</span>
                  )}
                </div>
                <Link
                  to="/perfil"
                  className="px-3 py-1.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-sm font-medium flex items-center gap-1.5 transition-colors"
                >
                  <User size={14} /> Perfil
                </Link>
                <button
                  onClick={handleLogout}
                  className="px-3 py-1.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
                >
                  <LogOut size={14} /> Salir
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-4 py-2 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-sm font-semibold transition-colors"
                >
                  Iniciar Sesión
                </Link>
                <Link
                  to="/registro"
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-colors shadow-sm shadow-emerald-600/20"
                >
                  Registrarse
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-2 rounded-xl text-gray-500 hover:bg-gray-100 transition-colors"
            aria-label="Abrir menú"
          >
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden border-t border-gray-100 bg-white px-4 py-3 space-y-1.5 shadow-lg">
          <Link to="/catalogo" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-gray-700 hover:bg-emerald-50 hover:text-emerald-700 font-medium">
            Catálogo
          </Link>
          {isAdmin && (
            <Link to="/reportes" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-gray-700 hover:bg-emerald-50 hover:text-emerald-700 font-medium">
              Reportes
            </Link>
          )}
          {isNormalUser && (
            <Link to="/mis-reservas" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-gray-700 hover:bg-emerald-50 hover:text-emerald-700 font-medium">
              Mis Reservas
            </Link>
          )}
          {isAdmin && (
            <Link to="/admin/taquilla" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-gray-700 hover:bg-emerald-50 hover:text-emerald-700 font-medium">
              Portal Admin
            </Link>
          )}
          <div className="pt-2 border-t border-gray-100">
            {isAuthenticated ? (
              <>
                <Link to="/perfil" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-50 font-medium">
                  Mi Perfil
                </Link>
                <button onClick={handleLogout} className="block w-full text-left px-3 py-2 rounded-lg text-red-600 hover:bg-red-50 font-medium">
                  Cerrar Sesión
                </button>
              </>
            ) : (
              <div className="flex gap-2 pt-1">
                <Link to="/login" onClick={() => setMenuOpen(false)} className="flex-1 text-center py-2 rounded-xl border border-gray-200 text-gray-700 font-semibold text-sm">
                  Iniciar Sesión
                </Link>
                <Link to="/registro" onClick={() => setMenuOpen(false)} className="flex-1 text-center py-2 rounded-xl bg-emerald-600 text-white font-semibold text-sm">
                  Registrarse
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </nav>
  )
}
