/**
 * Capa MVC: Vista — VistaCancha.tsx
 * Catálogo público interactivo de complejos deportivos y canchas sintéticas.
 * Permite filtrar por fecha, hora y modalidad, visualizando la disponibilidad en tiempo real.
 */

import { useState, useMemo, useEffect } from 'react'
import { Search, MapPin, ChevronRight, Loader2, Calendar, Clock, Trophy, ShieldCheck } from 'lucide-react'
import { formatCOP, TIPO_LABELS, buscarDisponibilidad, renderizarDisponibilidad, isSlotInPast } from './lib/api'
import { resolveMediaUrl } from './store/appearanceStore'
import { useAuthStore } from './store/authStore'
import {
  getCanchaSlots,
  getTodayIso as today,
  useCatalogoController,
} from './hooks/useCatalogoController'
import type { BloqueHorarioDto, CanchaDto, ComplejoDto, TipoCancha } from './lib/types'
import Modal from './components/Modal'
import PagoModal from './components/PagoModal'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import LoadingSpinner from './components/LoadingSpinner'
import MiniCanchaSlot from './components/MiniCanchaSlot'
import AdminReservaDrawer from './components/AdminReservaDrawer'
import PageBackground from './components/PageBackground'

export { buscarDisponibilidad, renderizarDisponibilidad }

declare global {
  interface Window {
    buscarDisponibilidad?: typeof buscarDisponibilidad
    renderizarDisponibilidad?: typeof renderizarDisponibilidad
  }
}

if (typeof window !== 'undefined') {
  window.buscarDisponibilidad = buscarDisponibilidad
  window.renderizarDisponibilidad = renderizarDisponibilidad
}

function formatHora(hora: string) {
  return hora.substring(0, 5)
}

const HOURS = Array.from({ length: 14 }, (_, i) => `${String(i + 8).padStart(2, '0')}:00`)

export default function VistaCancha() {
  const { user } = useAuthStore()
  const isAdmin = user?.rol === 'ADMIN_ESTABLECIMIENTO'

  const [adminDrawerSlot, setAdminDrawerSlot] = useState<{
    cancha: CanchaDto
    complejo: ComplejoDto
    bloque: BloqueHorarioDto
  } | null>(null)

  const {
    complejos,
    filteredComplejos,
    isLoading,
    error,
    fecha,
    setFecha,
    horaFiltro,
    setHoraFiltro,
    tipoFiltro,
    setTipoFiltro,
    reservaModal,
    setReservaModal,
    pagoModal,
    setPagoModal,
    slotMap,
    loadingSlots,
    creandoReserva,
    resolvedGeneralBg,
    cargarDisponibilidadCanchas,
    handleBlockClick,
    handleConfirmReserva,
  } = useCatalogoController()

  // Horarios vigentes: se filtran y remueven por completo las horas pasadas del día seleccionado
  const visibleHours = useMemo(() => {
    return HOURS.filter(h => !isSlotInPast(fecha, `${h}:00`))
  }, [fecha])

  // Si la hora filtrada ya pasó o no está en los horarios visibles, limpiar el filtro de hora
  useEffect(() => {
    if (horaFiltro && !visibleHours.includes(horaFiltro)) {
      setHoraFiltro('')
    }
  }, [visibleHours, horaFiltro, setHoraFiltro])

  return (
    <PageBackground imageUrl={resolvedGeneralBg}>
      <Navbar />

      {/* Catalog Header & Floating Filter Card */}
      <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-7 pb-2">
        {/* Floating Header + Filter Card */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 px-5 py-5 sm:px-6 sm:py-6">
          <div className="mb-5 pb-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
                Catálogo de Canchas Sintéticas
              </h1>
              <p className="text-gray-600 text-sm mt-1">
                Consulta horarios disponibles en Popayán y reserva tu cancha al instante
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-gray-700 bg-gray-50 border border-gray-200 px-3.5 py-2 rounded-xl w-fit shrink-0">
              <span className="inline-flex items-center gap-1.5 font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 border border-emerald-400 inline-block" />
                Disponible
              </span>
              <span className="inline-flex items-center gap-1.5 font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 border border-amber-400 inline-block" />
                Reservado
              </span>
              <span className="inline-flex items-center gap-1.5 font-medium">
                <span className="w-2.5 h-2.5 rounded-sm bg-red-200 border border-red-400 inline-block" />
                Mantenimiento
              </span>
              {isAdmin && (
                <span className="inline-flex items-center gap-1.5 font-bold text-emerald-800 bg-emerald-100/90 border border-emerald-300 px-2 py-0.5 rounded-lg text-[11px]">
                  <ShieldCheck size={13} className="text-emerald-700" />
                  Modo Admin: Clic en slot ocupado para gestionar
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-4 items-end">
            {/* Fecha */}
            <div className="lg:col-span-3">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
                <Calendar size={14} className="text-emerald-600" />
                Fecha
              </label>
              <div className="relative">
                <input
                  type="date"
                  value={fecha}
                  min={today()}
                  onChange={e => setFecha(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3.5 py-2.5 text-sm font-medium text-gray-800 hover:border-emerald-300 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all"
                />
              </div>
            </div>

            {/* Hora de inicio */}
            <div className="lg:col-span-3">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
                <Clock size={14} className="text-emerald-600" />
                Hora de inicio
              </label>
              <select
                value={horaFiltro}
                onChange={e => setHoraFiltro(e.target.value)}
                className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3.5 py-2.5 text-sm font-medium text-gray-800 hover:border-emerald-300 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all cursor-pointer"
              >
                <option value="">Cualquier hora</option>
                {visibleHours.map(h => <option key={h} value={h}>{h}</option>)}
              </select>
            </div>

            {/* Tipo de cancha */}
            <div className="lg:col-span-3">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
                <Trophy size={14} className="text-emerald-600" />
                Tipo de cancha
              </label>
              <select
                value={tipoFiltro}
                onChange={e => setTipoFiltro(e.target.value as TipoCancha | '')}
                className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3.5 py-2.5 text-sm font-medium text-gray-800 hover:border-emerald-300 focus:bg-white focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all cursor-pointer"
              >
                <option value="">Todos los tipos</option>
                <option value="FUTBOL_5">Fútbol 5</option>
                <option value="FUTBOL_7">Fútbol 7</option>
                <option value="FUTBOL_8">Fútbol 8</option>
              </select>
            </div>

            {/* Botón Buscar */}
            <div className="lg:col-span-3">
              <button
                onClick={() => {
                  const allCanchas = (Array.isArray(complejos) ? complejos : [])
                    .flatMap(c => Array.isArray(c?.canchas) ? c.canchas : [])
                  cargarDisponibilidadCanchas(allCanchas, fecha)
                }}
                disabled={loadingSlots}
                className="w-full bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-semibold px-5 py-2.5 rounded-xl shadow-md shadow-emerald-600/25 hover:shadow-lg hover:shadow-emerald-500/30 hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0"
              >
                {loadingSlots ? <Loader2 size={17} className="animate-spin" /> : <Search size={17} />}
                <span>Buscar disponibilidad</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-14 flex-1">
        {isLoading ? (
          <LoadingSpinner text="Cargando complejos..." />
        ) : error ? (
          <div className="bg-white rounded-2xl text-center py-16 text-red-500 shadow">
            <p className="text-xl mb-2">❌ No se pudo conectar al servidor</p>
            <p className="text-sm text-gray-500">Asegúrate de que el backend esté corriendo en el puerto 8000</p>
          </div>
        ) : filteredComplejos.length === 0 ? (
          <div className="bg-white rounded-2xl text-center py-16 text-gray-500 shadow">
            <p className="text-4xl mb-3">🏟️</p>
            <p className="text-lg font-medium">No hay canchas disponibles con estos filtros</p>
          </div>
        ) : (
          <div className="space-y-8">
            {filteredComplejos.map(complejo => {
              const complexBannerUrl = resolveMediaUrl(complejo.imagen_url, resolvedGeneralBg)
              return (
                <div key={complejo.id} className="shadow-xl rounded-2xl border border-white/30 overflow-hidden transition-all duration-300 hover:shadow-2xl">
                  {/* Complex header with custom banner image & subtle contrast overlay */}
                  <div
                    className="relative px-6 py-6 text-white overflow-hidden bg-cover bg-center bg-no-repeat w-full border-b border-white/20 shadow-xl app-banner-bg"
                    style={{
                      backgroundImage: complexBannerUrl ? `url("${complexBannerUrl}")` : undefined,
                      backgroundColor: '#064e3b',
                    }}
                  >
                    {/* Capa sutil de opacidad / gradiente oscuro encima para legibilidad sin tapar la foto */}
                    <div className="absolute inset-0 bg-gradient-to-r from-black/60 via-black/40 to-black/30 pointer-events-none" />

                    <div className="relative z-10 flex items-center justify-between gap-4">
                      <div>
                        <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight drop-shadow-md text-white">
                          {complejo.nombre}
                        </h2>
                        <div className="flex items-center gap-1.5 text-white/90 text-sm mt-1 drop-shadow font-medium">
                          <MapPin size={15} className="shrink-0 text-emerald-400" />
                          <span>{complejo.direccion} · {complejo.barrio}, Popayán</span>
                        </div>
                      </div>
                      <span className="badge bg-black/50 backdrop-blur-md border border-white/30 text-white text-xs px-3.5 py-1.5 shadow-sm font-semibold">
                        ⚽ {complejo.canchas.length} {complejo.canchas.length === 1 ? 'cancha' : 'canchas'}
                      </span>
                    </div>
                  </div>

                {/* Time header & schedule grid */}
                <div className="overflow-x-auto bg-white/80 backdrop-blur-md">
                  <div className="min-w-max">
                    {visibleHours.length === 0 ? (
                      <div className="p-8 text-center bg-white/70 backdrop-blur-sm rounded-b-2xl">
                        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 mb-3 border border-emerald-200 shadow-sm">
                          <Clock size={24} />
                        </div>
                        <p className="text-gray-800 font-bold text-sm">
                          No hay turnos disponibles para la fecha seleccionada ({fecha}).
                        </p>
                        <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
                          Los horarios de este día ya han finalizado. Selecciona una fecha posterior en el calendario para reservar.
                        </p>
                      </div>
                    ) : (
                      <>
                        {/* Hour labels row */}
                        <div className="flex border-b border-gray-200/60 bg-white/60 backdrop-blur-sm">
                          <div className="w-60 shrink-0 px-4 py-2.5 text-xs font-bold text-gray-600 uppercase tracking-wider flex items-center">
                            CANCHA SINTÉTICA
                          </div>
                          {visibleHours.map(h => (
                            <div key={h} className="w-24 shrink-0 text-center text-xs font-semibold text-gray-500 py-2.5 border-l border-gray-100/60">
                              {h}
                            </div>
                          ))}
                        </div>

                        {/* Court rows */}
                        {complejo.canchas.map(cancha => {
                          const slots = getCanchaSlots(cancha, slotMap[cancha.id], fecha)
                          const canchaImg = cancha.imagen_url ? resolveMediaUrl(cancha.imagen_url) : ''
                          return (
                            <div key={cancha.id} className="flex border-b border-gray-100/70 last:border-b-0 hover:bg-emerald-50/40 transition-colors">
                              {/* Court info */}
                              <div className="w-60 shrink-0 px-4 py-3.5 border-r border-gray-100/80 bg-white/40 backdrop-blur-sm flex items-center gap-3">
                                {canchaImg ? (
                                  <img
                                    src={canchaImg}
                                    alt={cancha.nombre}
                                    className="w-12 h-12 rounded-xl object-cover border border-emerald-200 shrink-0 shadow-sm"
                                  />
                                ) : (
                                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-600 to-green-700 text-white flex items-center justify-center text-lg shrink-0 shadow-sm">
                                    ⚽
                                  </div>
                                )}
                                <div className="min-w-0">
                                  <p className="font-bold text-sm text-gray-900 leading-tight line-clamp-2">{cancha.nombre}</p>
                                  <div className="flex flex-wrap items-center gap-1.5 mt-1">
                                    <span className={`badge text-[10px] ${
                                      cancha.tipo === 'FUTBOL_5' ? 'bg-blue-100 text-blue-700' :
                                      cancha.tipo === 'FUTBOL_7' ? 'bg-purple-100 text-purple-700' :
                                      'bg-orange-100 text-orange-700'
                                    }`}>
                                      {TIPO_LABELS[cancha.tipo]}
                                    </span>
                                    <span className="text-xs font-semibold text-emerald-700">
                                      {formatCOP(Number(cancha.tarifa_por_hora))}/h
                                    </span>
                                  </div>
                                </div>
                              </div>

                              {/* Mini Cancha Sintética Time Slots */}
                              {visibleHours.map(hora => {
                                const slot = slots.find(s => formatHora(s.hora_inicio) === hora) || {
                                  id: `virtual-${cancha.id}-${hora}`,
                                  cancha_id: cancha.id,
                                  fecha,
                                  hora_inicio: `${hora}:00`,
                                  hora_fin: `${String(Number(hora.split(':')[0]) + 1).padStart(2, '0')}:00:00`,
                                  estado: 'LIBRE' as const,
                                }
                                const isFiltered = horaFiltro && horaFiltro !== hora

                                return (
                                  <div key={hora} className={`w-24 shrink-0 p-1.5 border-l border-gray-100/60 flex items-center justify-center ${isFiltered ? 'opacity-25' : ''}`}>
                                    <MiniCanchaSlot
                                      horaInicio={slot.hora_inicio}
                                      fecha={fecha}
                                      tarifa={Number(cancha.tarifa_por_hora)}
                                      estado={slot.estado}
                                      isPast={false}
                                      isAdmin={isAdmin}
                                      onClick={() => slot.estado === 'LIBRE' && handleBlockClick(cancha, complejo, slot)}
                                      onAdminInspect={() => setAdminDrawerSlot({ cancha, complejo, bloque: slot })}
                                    />
                                  </div>
                                )
                              })}
                            </div>
                          )
                        })}
                      </>
                    )}
                  </div>
                </div>
              </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Admin reservation inspection & management drawer (Slide-over) */}
      {isAdmin && (
        <AdminReservaDrawer
          isOpen={!!adminDrawerSlot}
          onClose={() => setAdminDrawerSlot(null)}
          cancha={adminDrawerSlot?.cancha ?? null}
          complejo={adminDrawerSlot?.complejo ?? null}
          bloque={adminDrawerSlot?.bloque ?? null}
          onSuccessAction={() => {
            const allCanchas = (Array.isArray(complejos) ? complejos : []).flatMap(c => (Array.isArray(c?.canchas) ? c.canchas : []))
            cargarDisponibilidadCanchas(allCanchas, fecha)
          }}
        />
      )}

      {/* Reservation confirmation modal */}
      {reservaModal && (
        <Modal isOpen={!!reservaModal} onClose={() => setReservaModal(null)} title="🏟️ Confirmar Reserva">
          <div className="space-y-4">
            <div className="bg-green-50 rounded-xl p-4 border border-green-200">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><p className="text-gray-500 text-xs">Complejo</p><p className="font-semibold">{reservaModal.complejo.nombre}</p></div>
                <div><p className="text-gray-500 text-xs">Cancha</p><p className="font-semibold">{reservaModal.cancha.nombre}</p></div>
                <div><p className="text-gray-500 text-xs">Fecha</p><p className="font-semibold">{reservaModal.bloque.fecha}</p></div>
                <div><p className="text-gray-500 text-xs">Horario</p><p className="font-semibold">{formatHora(reservaModal.bloque.hora_inicio)} – {formatHora(reservaModal.bloque.hora_fin)}</p></div>
                <div className="col-span-2 pt-2 border-t border-green-200">
                  <p className="text-gray-500 text-xs">Total a pagar</p>
                  <p className="text-2xl font-bold text-green-700">{formatCOP(Number(reservaModal.cancha.tarifa_por_hora))}</p>
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setReservaModal(null)} className="btn-secondary flex-1">Cancelar</button>
              <button onClick={handleConfirmReserva} disabled={creandoReserva} className="btn-primary flex-1 flex items-center justify-center gap-2">
                {creandoReserva ? <><Loader2 size={16} className="animate-spin" /> Reservando...</> : <><ChevronRight size={16} /> Confirmar y Pagar</>}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Payment modal */}
      {pagoModal && (
        <PagoModal
          isOpen={!!pagoModal}
          onClose={() => setPagoModal(null)}
          reserva={pagoModal}
        />
      )}

      <Footer />
    </PageBackground>
  )
}
