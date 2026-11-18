/**
 * Capa MVC: Vista — VistaPerfil.tsx (también accesible como VistaUsuario.tsx)
 * Gestión de la cuenta de usuario, edición de datos personales y cambio de contraseña.
 */

import { Save, Loader2, User } from 'lucide-react'
import { usePerfilController } from './hooks/usePerfilController'
import Navbar from './components/Navbar'
import LoadingSpinner from './components/LoadingSpinner'
import PageBackground from './components/PageBackground'

export default function VistaPerfil() {
  const {
    user,
    perfil,
    isLoading,
    resolvedGeneralBg,
    nombre,
    setNombre,
    telefono,
    setTelefono,
    currentPassword,
    setCurrentPassword,
    newPassword,
    setNewPassword,
    confirmPassword,
    setConfirmPassword,
    msg,
    setMsg,
    pwdMsg,
    updating,
    changingPwd,
    updatePerfil,
    handlePwdSubmit,
  } = usePerfilController()

  if (isLoading) {
    return (
      <PageBackground imageUrl={resolvedGeneralBg}>
        <Navbar />
        <LoadingSpinner />
      </PageBackground>
    )
  }

  return (
    <PageBackground imageUrl={resolvedGeneralBg}>
      <Navbar />
      <div className="w-full max-w-2xl mx-auto px-4 py-8 flex-1">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl border border-gray-200/80 shadow-lg px-6 py-4 mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <User size={24} className="text-green-600" /> Mi Perfil
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">Consulta y actualiza tu información personal y credenciales</p>
        </div>

        {/* Información personal */}
        <div className="card bg-white/95 backdrop-blur-sm shadow-lg mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Información Personal</h2>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nombre completo</label>
              <input type="text" value={nombre} onChange={e => setNombre(e.target.value)} className="input-field" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Correo electrónico</label>
              <input type="email" value={perfil?.email || user?.email || ''} disabled className="input-field bg-gray-50 text-gray-500 cursor-not-allowed" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Teléfono</label>
              <input type="tel" value={telefono} onChange={e => setTelefono(e.target.value)} className="input-field" placeholder="Ej: 3001234567" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Rol en la plataforma</label>
              <input type="text" value={user?.rol === 'ADMIN_ESTABLECIMIENTO' ? 'Administrador de Complejo' : 'Deportista'} disabled className="input-field bg-gray-50 text-gray-500 cursor-not-allowed font-medium" />
            </div>
            {msg && <p className={`text-sm ${msg.startsWith('✅') ? 'text-green-700' : 'text-red-600'}`}>{msg}</p>}
            <button onClick={updatePerfil} disabled={updating} className="btn-primary flex items-center gap-2 mt-2">
              {updating ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Guardar Cambios
            </button>
          </div>
        </div>

        {/* Cambio de contraseña */}
        <div className="card bg-white/95 backdrop-blur-sm shadow-lg">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Cambiar Contraseña</h2>
          <form onSubmit={handlePwdSubmit} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña actual</label>
              <input type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} className="input-field" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nueva contraseña</label>
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} className="input-field" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar nueva contraseña</label>
              <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} className="input-field" required />
            </div>
            {pwdMsg && <p className={`text-sm ${pwdMsg.startsWith('✅') ? 'text-green-700' : 'text-red-600'}`}>{pwdMsg}</p>}
            <button type="submit" disabled={changingPwd} className="btn-primary flex items-center gap-2">
              {changingPwd ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Cambiar Contraseña
            </button>
          </form>
        </div>
      </div>
    </PageBackground>
  )
}

export { VistaPerfil as VistaUsuario }
