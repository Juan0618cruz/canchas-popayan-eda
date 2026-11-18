/**
 * Capa MVC: Vista — VistaLogin.tsx
 * Vista de inicio de sesión con autenticación JWT y diseño moderno split-screen.
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Eye, EyeOff, Loader2, Mail, Lock, Sparkles, CheckCircle2, Trophy, ArrowRight } from 'lucide-react'
import { authApi, extractErrorMessage } from './lib/api'
import type { LoginResponse } from './lib/types'
import { useAuthStore } from './store/authStore'
import { DEFAULT_GENERAL_BG, resolveMediaUrl, useAppearanceStore } from './store/appearanceStore'
import Navbar from './components/Navbar'

export default function VistaLogin() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const storeBg = useAppearanceStore((s) => s.fondoGeneralUrl)
  const bgImage = resolveMediaUrl(storeBg, DEFAULT_GENERAL_BG)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  const { mutate, isPending } = useMutation({
    mutationFn: () => authApi.login(email, password),
    onSuccess: (data: LoginResponse) => {
      const u = data.usuario
      const userId = u?.id ?? data.usuario_id ?? ''
      const userRol = u?.rol ?? data.rol ?? 'USUARIO'
      const userNombre = u?.nombre ?? data.nombre ?? (email ? email.split('@')[0] : 'Usuario')
      const userEmail = u?.email ?? data.email ?? email
      const userEstId = u?.establecimiento_id ?? data.establecimiento_id ?? null

      login(data.access_token, {
        id: userId,
        nombre: userNombre,
        rol: userRol,
        establecimiento_id: userEstId,
        email: userEmail,
        activo: true,
      })
      if (userRol === 'ADMIN_ESTABLECIMIENTO') {
        navigate('/admin/taquilla')
      } else {
        navigate('/catalogo')
      }
    },
    onError: (err: unknown) => {
      setErrorMsg(extractErrorMessage(err, 'Credenciales inválidas. Verifica tu correo y contraseña.'))
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg('')
    mutate()
  }

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden bg-slate-900">
      {/* Fondo temático absoluto para toda la pantalla con filtro desenfocado y artístico */}
      <div
        className="fixed inset-0 z-0 h-full w-full bg-cover bg-center bg-no-repeat pointer-events-none filter blur-md brightness-50 scale-105"
        style={{
          backgroundImage: `url("${bgImage}")`,
          backgroundColor: '#064e3b',
        }}
      />
      {/* Capa de tinte semitransparente verde/oscuro para unificar el fondo */}
      <div className="fixed inset-0 z-0 bg-emerald-950/40 pointer-events-none" />

      {/* Barra de navegación superior */}
      <div className="relative z-20">
        <Navbar />
      </div>

      {/* Contenido principal: Tarjeta central flotando nítidamente por encima del fondo */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-10">
        <div className="w-full max-w-5xl rounded-3xl overflow-hidden shadow-2xl border border-white/20 bg-white grid grid-cols-1 lg:grid-cols-2 min-h-[620px] lg:min-h-[680px]">
          
          {/* ================= COLUMNA IZQUIERDA: Banner & Bienvenida ================= */}
          <div
            className="relative flex flex-col justify-between p-8 sm:p-12 text-white bg-cover bg-center bg-no-repeat overflow-hidden min-h-[280px] lg:min-h-full w-full app-banner-bg"
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
                <span>Plataforma Oficial Popayán</span>
              </div>
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight mt-4 text-white drop-shadow-md">
                Canchas Popayán
              </h1>
            </div>

            {/* Mensaje principal de bienvenida */}
            <div className="relative z-10 my-6 lg:my-auto">
              <h2 className="text-xl sm:text-2xl lg:text-3xl font-extrabold text-white leading-tight drop-shadow">
                ¡Bienvenido a Canchas Popayán!
              </h2>
              <p className="mt-3 text-sm sm:text-base text-emerald-100/90 leading-relaxed font-normal drop-shadow-sm max-w-md">
                Gestiona tus reservas, vive la pasión del deporte y administra tu complejo de manera inteligente y en tiempo real.
              </p>

              {/* Beneficios clave (visibles en desktop y tablets) */}
              <div className="hidden sm:flex flex-col gap-2.5 mt-6 text-xs sm:text-sm text-emerald-100/90">
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                  <span>Reserva inmediata 24/7 sin llamadas ni esperas</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                  <span>Disponibilidad en tiempo real de canchas sintéticas</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                  <span>Control de taquilla y cobros para administradores</span>
                </div>
              </div>
            </div>

            {/* Footer de la columna izquierda */}
            <div className="relative z-10 pt-4 border-t border-white/15 flex items-center justify-between text-xs text-emerald-200/80">
              <span>Fútbol 5 · Fútbol 7 · Fútbol 8</span>
              <span className="flex items-center gap-1 text-white font-medium">
                <Trophy size={14} className="text-amber-400" /> Popayán, Cauca
              </span>
            </div>
          </div>

          {/* ================= COLUMNA DERECHA: Formulario de Login ================= */}
          <div className="flex flex-col justify-center p-8 sm:p-12 lg:p-14 bg-white">
            <div className="w-full max-w-md mx-auto">
              {/* Título de la sección */}
              <div className="mb-8">
                <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl font-bold mb-4 shadow-sm border border-emerald-100">
                  ⚽
                </div>
                <h3 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
                  Iniciar Sesión
                </h3>
                <p className="text-sm text-gray-500 mt-1.5">
                  Ingresa tus credenciales para acceder a tu cuenta
                </p>
              </div>

              {/* Formulario */}
              <form onSubmit={handleSubmit} className="space-y-5" autoComplete="off">
                {/* Campo: Correo */}
                <div>
                  <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">
                    Correo electrónico
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                      <Mail size={18} />
                    </div>
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                      placeholder="tu-correo@ejemplo.com"
                      autoComplete="off"
                      required
                    />
                  </div>
                </div>

                {/* Campo: Contraseña */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Contraseña
                    </label>
                    <Link
                      to="/recuperar-password"
                      className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 hover:underline transition-colors"
                    >
                      ¿Olvidaste tu contraseña?
                    </Link>
                  </div>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                      <Lock size={18} />
                    </div>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      className="w-full rounded-xl border border-gray-200 bg-gray-50/50 pl-10 pr-11 py-3 text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                      placeholder="••••••••••••"
                      autoComplete="current-password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                {/* Mensaje de error */}
                {errorMsg && (
                  <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 flex items-start gap-2 animate-fadeIn">
                    <span className="shrink-0 text-base">⚠️</span>
                    <span>{errorMsg}</span>
                  </div>
                )}

                {/* Botón de acceso */}
                <button
                  type="submit"
                  disabled={isPending}
                  className="w-full py-3.5 px-4 rounded-xl font-bold text-white bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 active:scale-[0.99] shadow-lg shadow-emerald-600/25 transition-all duration-200 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                >
                  {isPending ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      <span>Iniciando sesión...</span>
                    </>
                  ) : (
                    <>
                      <span>Iniciar Sesión</span>
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </form>

              {/* Registro */}
              <div className="mt-8 pt-6 border-t border-gray-100 text-center text-sm text-gray-600">
                <span>¿Aún no tienes una cuenta? </span>
                <Link
                  to="/registro"
                  className="font-bold text-emerald-600 hover:text-emerald-700 hover:underline transition-colors ml-1"
                >
                  Regístrate gratis
                </Link>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  )
}
