/**
 * Componente principal de enrutamiento de la aplicación (Frontend SPA).
 * Configura las rutas protegidas y públicas enlazadas directamente con la capa de Vistas (MVC).
 */

import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { useAppearanceStore } from './store/appearanceStore'
import { canchasApi } from './lib/api'

// Importación de Vistas normalizadas según el patrón MVC
import VistaLanding from './VistaLanding'
import VistaLogin from './VistaLogin'
import VistaRegistro from './VistaRegistro'
import VistaRecuperarPassword from './VistaRecuperarPassword'
import VistaCancha from './VistaCancha'
import VistaReserva from './VistaReserva'
import VistaPerfil from './VistaPerfil'
import VistaReportes from './VistaReportes'
import VistaAdminLayout from './admin/VistaAdminLayout'
import VistaAdminCanchas from './admin/VistaAdminCanchas'
import VistaAdminTaquilla from './admin/VistaAdminTaquilla'
import VistaAdminPagos from './admin/VistaAdminPagos'
import VistaAdminApariencia from './admin/VistaAdminApariencia'

function RutaProtegida({ children, requiereAdmin = false }: { children: React.ReactNode; requiereAdmin?: boolean }) {
  const { isAuthenticated, user } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  const esAdmin = user?.rol === 'ADMIN_ESTABLECIMIENTO' || user?.rol?.toLowerCase() === 'admin'
  if (requiereAdmin && !esAdmin) return <Navigate to="/catalogo" replace />
  return <>{children}</>
}

export default function App() {
  const setAppearance = useAppearanceStore((s) => s.setAppearance)

  useEffect(() => {
    canchasApi.getApariencia().then((cfg) => {
      if (cfg) {
        setAppearance({
          fondoGeneralUrl: cfg.fondo_general_url,
          fondoSlotUrl: cfg.fondo_slot_url,
        })
      }
    }).catch(() => {})
  }, [setAppearance])

  return (
    <Routes>
      <Route path="/" element={<VistaLanding />} />
      <Route path="/login" element={<VistaLogin />} />
      <Route path="/registro" element={<VistaRegistro />} />
      <Route path="/recuperar-password" element={<VistaRecuperarPassword />} />
      <Route path="/catalogo" element={<VistaCancha />} />
      <Route path="/monitor" element={
        <RutaProtegida requiereAdmin><VistaReportes /></RutaProtegida>
      } />
      <Route path="/reportes" element={
        <RutaProtegida requiereAdmin><VistaReportes /></RutaProtegida>
      } />
      <Route path="/mis-reservas" element={
        <RutaProtegida><VistaReserva /></RutaProtegida>
      } />
      <Route path="/perfil" element={
        <RutaProtegida><VistaPerfil /></RutaProtegida>
      } />
      <Route path="/admin" element={
        <RutaProtegida requiereAdmin><VistaAdminLayout /></RutaProtegida>
      }>
        <Route index element={<Navigate to="/admin/taquilla" replace />} />
        <Route path="canchas" element={<VistaAdminCanchas />} />
        <Route path="taquilla" element={<VistaAdminTaquilla />} />
        <Route path="pagos" element={<VistaAdminPagos />} />
        <Route path="apariencia" element={<VistaAdminApariencia />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
