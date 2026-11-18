import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  Loader2,
  Mail,
  Lock,
  User as UserIcon,
  Phone,
  Building2,
  MapPin,
  CheckCircle2,
  Trophy,
  ArrowRight,
  Eye,
  EyeOff,
} from 'lucide-react'
import { authApi, extractErrorMessage } from './lib/api'
import type { User } from './lib/types'
import { useAuthStore } from './store/authStore'
import { DEFAULT_GENERAL_BG, resolveMediaUrl, useAppearanceStore } from './store/appearanceStore'
import Navbar from './components/Navbar'

/**
 * Capa MVC: Vista — VistaRegistro.tsx
 * Registro de nuevas cuentas (Deportistas y Administradores de Complejos).
 */

type Tab = 'deportista' | 'admin'

export default function VistaRegistro() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const storeBg = useAppearanceStore((s) => s.fondoGeneralUrl)
  const bgImage = resolveMediaUrl(storeBg, DEFAULT_GENERAL_BG)

  const [tab, setTab] = useState<Tab>('deportista')
  const [showPassword, setShowPassword] = useState(false)
  const [form, setForm] = useState({
    nombre: '',
    email: '',
    password: '',
    confirmPassword: '',
    telefono: '',
    establecimiento_nombre: '',
    establecimiento_direccion: '',
  })
  const [errorMsg, setErrorMsg] = useState('')
  const [successUser, setSuccessUser] = useState<{ nombre: string; email: string } | null>(null)

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }))

  const handleRegisterSuccess = async (createdUser: User) => {
    try {
      const emailTrim = form.email.trim().toLowerCase()
      const loginData = await authApi.login(emailTrim, form.password)
      const u = loginData.usuario
      const userRol = u?.rol ?? createdUser.rol ?? (tab === 'admin' ? 'ADMIN_ESTABLECIMIENTO' : 'USUARIO')

      login(loginData.access_token, {
        id: u?.id ?? createdUser.id,
        nombre: u?.nombre ?? createdUser.nombre ?? form.nombre.trim(),
        rol: userRol,
        establecimiento_id: u?.establecimiento_id ?? createdUser.establecimiento_id ?? null,
        email: u?.email ?? createdUser.email ?? emailTrim,
        activo: true,
      })

      if (userRol === 'ADMIN_ESTABLECIMIENTO') {
        navigate('/admin/taquilla')
      } else {
        navigate('/catalogo')
      }
    } catch {
      setSuccessUser({
        nombre: createdUser?.nombre || form.nombre.trim(),
        email: createdUser?.email || form.email.trim().toLowerCase(),
      })
    }
  }

  const { mutate: registerUser, isPending: pendingUser } = useMutation({
    mutationFn: () => authApi.register({
      nombre: form.nombre.trim(),
      email: form.email.trim().toLowerCase(),
      password: form.password,
      telefono: form.telefono.trim(),
    }),
    onSuccess: (data) => handleRegisterSuccess(data),
    onError: (err: unknown) => setErrorMsg(extractErrorMessage(err, 'Error en el registro.')),
  })

  const { mutate: registerAdmin, isPending: pendingAdmin } = useMutation({
    mutationFn: () => authApi.registerAdmin({
      nombre: form.nombre.trim(),
      email: form.email.trim().toLowerCase(),
      password: form.password,
      telefono: form.telefono.trim(),
      establecimiento_nombre: form.establecimiento_nombre.trim(),
      establecimiento_direccion: form.establecimiento_direccion.trim(),
    }),
    onSuccess: (data) => handleRegisterSuccess(data),
    onError: (err: unknown) => setErrorMsg(extractErrorMessage(err, 'Error en el registro.')),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg('')
    if (form.password !== form.confirmPassword) {
      setErrorMsg('Las contraseñas no coinciden.')
      return
    }
    if (tab === 'deportista') registerUser()
    else registerAdmin()
  }

  const isPending = pendingUser || pendingAdmin

  if (successUser) {
    return (
      <div className="min-h-screen flex flex-col relative overflow-hidden bg-slate-900">
        <div
          className="fixed inset-0 z-0 h-full w-full bg-cover bg-center bg-no-repeat pointer-events-none filter blur-md brightness-50 scale-105"
          style={{
            backgroundImage: `url("${bgImage}")`,
            backgroundColor: '#064e3b',
          }}
        />
        <div className="fixed inset-0 z-0 bg-emerald-950/40 pointer-events-none" />
        <div className="relative z-20">
          <Navbar />
        </div>
        <div className="relative z-10 flex-1 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-3xl p-8 sm:p-10 text-center shadow-2xl border border-white/30">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-3xl mx-auto mb-4 shadow-sm border border-emerald-200">
              ✅
            </div>
            <h2 className="text-2xl font-extrabold text-gray-900 mb-2">¡Bienvenido, {successUser.nombre}!</h2>
            <p className="text-gray-600 text-sm mb-6 leading-relaxed">
              Tu cuenta con correo <strong>{successUser.email}</strong> ha sido registrada exitosamente. Ya puedes iniciar sesión y comenzar a reservar.
            </p>
            <button
              onClick={() => navigate('/login')}
              className="w-full py-3.5 rounded-xl font-bold text-white bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 shadow-lg shadow-emerald-600/25 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Ir a Iniciar Sesión</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden bg-slate-900">
      {/* 1. Fondo temático absoluto para toda la pantalla con filtro desenfocado y artístico */}
      <div
        className="fixed inset-0 z-0 h-full w-full bg-cover bg-center bg-no-repeat pointer-events-none filter blur-md brightness-50 scale-105"
        style={{
          backgroundImage: `url("${bgImage}")`,
          backgroundColor: '#064e3b',
        }}
      />
      {/* Capa de tinte semitransparente verde/oscuro para unificar el fondo */}
      <div className="fixed inset-0 z-0 bg-emerald-950/40 pointer-events-none" />

      {/* 2. Barra de navegación superior */}
      <div className="relative z-20">
        <Navbar />
      </div>

      {/* 3. Contenido principal: Estructura Split-Screen moderna */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-10 my-4">
        <div className="w-full max-w-5xl rounded-3xl overflow-hidden shadow-2xl border border-white/20 bg-white grid grid-cols-1 lg:grid-cols-2 min-h-[660px]">
          
          {/* ================= COLUMNA IZQUIERDA: Banner & Mensaje Motivador ================= */}
          <div
            className="relative flex flex-col justify-between p-8 sm:p-12 text-white bg-cover bg-center bg-no-repeat overflow-hidden min-h-[300px] lg:min-h-full w-full app-banner-bg"
            style={{
              backgroundImage: `url("${bgImage}")`,
              backgroundColor: '#064e3b',
            }}
          >
            {/* Overlay oscuro y verde semitransparente */}
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-950/95 via-emerald-900/85 to-black/90 backdrop-blur-[2px] pointer-events-none" />

            {/* Decoraciones de luz suave */}
            <div className="absolute -top-24 -left-24 w-72 h-72 rounded-full bg-emerald-500/20 blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -right-24 w-72 h-72 rounded-full bg-teal-400/20 blur-3xl pointer-events-none" />

            {/* Cabecera / Marca superior */}
            <div className="relative z-10">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-xs font-semibold text-emerald-200 shadow-sm">
                <span className="text-sm">⚽</span>
                <span>Comunidad Deportiva de Popayán</span>
              </div>
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight mt-4 text-white drop-shadow-md">
                Canchas Popayán
              </h1>
            </div>

            {/* Mensaje principal motivador */}
            <div className="relative z-10 my-6 lg:my-auto">
              <h2 className="text-xl sm:text-2xl lg:text-3xl font-extrabold text-white leading-tight drop-shadow">
                ¡Únete a Canchas Popayán!
              </h2>
              <p className="mt-3 text-sm sm:text-base text-emerald-100/90 leading-relaxed font-normal drop-shadow-sm max-w-md">
                Regístrate como deportista o administrador de complejos y comienza a vivir el deporte al máximo con reservas instantáneas y control total.
              </p>

              {/* Beneficios clave */}
              <div className="hidden sm:flex flex-col gap-3 mt-6 text-xs sm:text-sm text-emerald-100/90">
                <div className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  <span><strong>Para Deportistas:</strong> Consulta horarios libres, reserva canchas sintéticas en segundos y comparte partidos.</span>
                </div>
                <div className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  <span><strong>Para Administradores:</strong> Taquilla presencial, control de caja, pagos en tiempo real y panel de gestión.</span>
                </div>
                <div className="flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  <span>Acceso seguro y confirmaciones automáticas de reserva.</span>
                </div>
              </div>
            </div>

            {/* Footer de la columna izquierda */}
            <div className="relative z-10 pt-4 border-t border-white/15 flex items-center justify-between text-xs text-emerald-200/80">
              <span>Elige tu rol en el formulario</span>
              <span className="flex items-center gap-1 text-white font-medium">
                <Trophy size={14} className="text-amber-400" /> Popayán, Cauca
              </span>
            </div>
          </div>

          {/* ================= COLUMNA DERECHA: Formulario Crear Cuenta ================= */}
          <div className="flex flex-col justify-center p-6 sm:p-10 lg:p-12 bg-white overflow-y-auto">
            <div className="w-full max-w-md mx-auto">
              {/* Título de la sección */}
              <div className="mb-5">
                <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl font-bold mb-3 shadow-sm border border-emerald-100">
                  👤
                </div>
                <h3 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
                  Crear Cuenta
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  Selecciona tu perfil y completa tus datos
                </p>
              </div>

              {/* Selector de pestañas: Deportista vs Administrador */}
              <div className="flex p-1 bg-gray-100/90 rounded-2xl border border-gray-200/80 mb-5">
                <button
                  type="button"
                  onClick={() => { setTab('deportista'); setErrorMsg(''); }}
                  className={`flex-1 py-2.5 px-3 rounded-xl text-xs sm:text-sm font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                    tab === 'deportista'
                      ? 'bg-white text-emerald-700 shadow-sm border border-gray-200/60'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <span>👤 Deportista</span>
                </button>
                <button
                  type="button"
                  onClick={() => { setTab('admin'); setErrorMsg(''); }}
                  className={`flex-1 py-2.5 px-3 rounded-xl text-xs sm:text-sm font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                    tab === 'admin'
                      ? 'bg-white text-emerald-700 shadow-sm border border-gray-200/60'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <span>🏟️ Administrador</span>
                </button>
              </div>

              {/* Formulario */}
              <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
                {/* Nombre */}
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                    Nombre completo
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                      <UserIcon size={17} />
                    </div>
                    <input
                      type="text"
                      value={form.nombre}
                      onChange={set('nombre')}
                      className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                      placeholder="Ej: Juan Pérez"
                      autoComplete="off"
                      required
                    />
                  </div>
                </div>

                {/* Correo y Teléfono en dos columnas */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                      Correo electrónico
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                        <Mail size={17} />
                      </div>
                      <input
                        type="email"
                        value={form.email}
                        onChange={set('email')}
                        className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                        placeholder="tu@correo.com"
                        autoComplete="off"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                      Teléfono
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                        <Phone size={17} />
                      </div>
                      <input
                        type="tel"
                        value={form.telefono}
                        onChange={set('telefono')}
                        className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                        placeholder="Ej: 3001234567"
                        autoComplete="off"
                      />
                    </div>
                  </div>
                </div>

                {/* Contraseña y Confirmar en dos columnas */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                      Contraseña
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                        <Lock size={17} />
                      </div>
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={form.password}
                        onChange={set('password')}
                        className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-9 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                        placeholder="••••••••"
                        autoComplete="new-password"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                        tabIndex={-1}
                      >
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                      Confirmar
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                        <Lock size={17} />
                      </div>
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={form.confirmPassword}
                        onChange={set('confirmPassword')}
                        className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                        placeholder="Repite la clave"
                        autoComplete="new-password"
                        required
                      />
                    </div>
                  </div>
                </div>

                {/* Campos exclusivos para Administrador */}
                {tab === 'admin' && (
                  <div className="pt-3 border-t border-gray-100 space-y-3 animate-fadeIn">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-800 bg-emerald-50 px-2.5 py-1.5 rounded-lg border border-emerald-100">
                      <Building2 size={14} className="text-emerald-600" />
                      <span>Datos del Complejo Deportivo</span>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                        Nombre del complejo
                      </label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                          <Building2 size={17} />
                        </div>
                        <input
                          type="text"
                          value={form.establecimiento_nombre}
                          onChange={set('establecimiento_nombre')}
                          className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                          placeholder="Ej: Complejo Sintético Bernabéu"
                          autoComplete="off"
                          required={tab === 'admin'}
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                        Dirección y barrio
                      </label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                          <MapPin size={17} />
                        </div>
                        <input
                          type="text"
                          value={form.establecimiento_direccion}
                          onChange={set('establecimiento_direccion')}
                          className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                          placeholder="Ej: Carrera 15 # 12-45, Barrio San José"
                          autoComplete="off"
                          required={tab === 'admin'}
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Mensaje de error */}
                {errorMsg && (
                  <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5 flex items-start gap-2">
                    <span className="shrink-0 text-base">⚠️</span>
                    <span>{errorMsg}</span>
                  </div>
                )}

                {/* Botón de envío */}
                <button
                  type="submit"
                  disabled={isPending}
                  className="w-full py-3.5 px-4 rounded-xl font-bold text-white bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 active:scale-[0.99] shadow-lg shadow-emerald-600/25 transition-all duration-200 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer mt-2"
                >
                  {isPending ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      <span>Registrando cuenta...</span>
                    </>
                  ) : (
                    <>
                      <span>Crear Cuenta {tab === 'admin' ? 'como Administrador' : 'como Deportista'}</span>
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </form>

              {/* Enlace al login */}
              <div className="mt-6 pt-5 border-t border-gray-100 text-center text-sm text-gray-600">
                <span>¿Ya tienes una cuenta registrada? </span>
                <Link
                  to="/login"
                  className="font-bold text-emerald-600 hover:text-emerald-700 hover:underline transition-colors ml-1"
                >
                  Inicia sesión
                </Link>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  )
}
