/**
 * Capa MVC: Vista — VistaRecuperarPassword.tsx
 * Flujo de recuperación de contraseñas olvidadas por correo electrónico y token.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Loader2, Mail, KeyRound } from 'lucide-react'
import { authApi, extractErrorMessage } from './lib/api'
import type { ForgotPasswordResponse } from './lib/types'
import Navbar from './components/Navbar'

export default function VistaRecuperarPassword() {
  const [step, setStep] = useState<1 | 2>(1)
  const [email, setEmail] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [tokenHint, setTokenHint] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [done, setDone] = useState(false)

  const { mutate: sendEmail, isPending: sendingEmail } = useMutation({
    mutationFn: () => authApi.forgotPassword(email),
    onSuccess: (data: ForgotPasswordResponse) => {
      setTokenHint(data?.token ?? data?.detail ?? '')
      setStep(2)
    },
    onError: () => setStep(2), // Always move forward (security)
  })

  const { mutate: resetPass, isPending: resettingPass } = useMutation({
    mutationFn: () => authApi.resetPassword(token, newPassword),
    onSuccess: () => setDone(true),
    onError: (err: unknown) => setErrorMsg(extractErrorMessage(err, 'Token inválido o expirado.')),
  })

  if (done) return (
    <div className="min-h-screen bg-gray-50"><Navbar />
      <div className="flex items-center justify-center py-20 px-4">
        <div className="card max-w-md w-full text-center">
          <div className="text-6xl mb-4">🔓</div>
          <h2 className="text-2xl font-bold text-green-700 mb-2">¡Contraseña Restablecida!</h2>
          <p className="text-gray-600 mb-6">Tu contraseña fue actualizada. Ya puedes iniciar sesión.</p>
          <Link to="/login" className="btn-primary block text-center">Ir al Login</Link>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50"><Navbar />
      <div className="flex items-center justify-center py-12 px-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="text-5xl mb-3">🔑</div>
            <h1 className="text-2xl font-bold text-gray-900">Recuperar Contraseña</h1>
            <p className="text-gray-500 mt-1">
              {step === 1 ? 'Ingresa tu email para recibir tu código de recuperación de 6 dígitos' : 'Ingresa el código de 6 dígitos y tu nueva contraseña'}
            </p>
          </div>

          <div className="card">
            {step === 1 ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Correo electrónico</label>
                  <div className="relative">
                    <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                      className="input-field pl-9" placeholder="tu@correo.com" required />
                  </div>
                </div>
                <button onClick={() => { setErrorMsg(''); sendEmail() }} disabled={sendingEmail || !email} className="btn-primary w-full py-3">
                  {sendingEmail ? <span className="flex items-center justify-center gap-2"><Loader2 size={18} className="animate-spin" /> Enviando...</span> : 'Enviar Código de Recuperación'}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {tokenHint && (
                  <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                    <p className="text-xs font-bold text-blue-700 mb-1">🧪 Código de recuperación:</p>
                    <p className="font-mono text-2xl font-extrabold text-blue-900 tracking-widest bg-blue-100 rounded-lg py-2 inline-block px-4">{tokenHint}</p>
                    <p className="text-xs text-blue-500 mt-1">Válido por 15 minutos · Un solo uso</p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Código de 6 dígitos</label>
                  <div className="relative">
                    <KeyRound size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      type="text"
                      maxLength={6}
                      value={token}
                      onChange={e => setToken(e.target.value.trim())}
                      className="input-field pl-9 font-mono text-center tracking-widest text-lg font-bold"
                      placeholder="123456"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nueva contraseña</label>
                  <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} className="input-field" placeholder="••••••" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar contraseña</label>
                  <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} className="input-field" placeholder="••••••" />
                </div>

                {errorMsg && (
                  <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">❌ {errorMsg}</div>
                )}

                <button
                  onClick={() => {
                    setErrorMsg('')
                    if (newPassword !== confirmPassword) { setErrorMsg('Las contraseñas no coinciden.'); return }
                    resetPass()
                  }}
                  disabled={resettingPass || !token || !newPassword}
                  className="btn-primary w-full py-3"
                >
                  {resettingPass ? <span className="flex items-center justify-center gap-2"><Loader2 size={18} className="animate-spin" /> Restableciendo...</span> : 'Restablecer Contraseña'}
                </button>
              </div>
            )}

            <p className="text-center text-sm text-gray-500 mt-4">
              <Link to="/login" className="text-green-600 hover:underline">← Volver al Login</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
