/**
 * Capa MVC: Vista — VistaReserva.tsx
 * Consulta, gestión y reprogramación/cancelación de reservas del deportista autenticado.
 */

import { Calendar, Clock, XCircle, RefreshCw, Loader2, Edit3, CheckCircle2, AlertCircle } from 'lucide-react'
import { formatCOP, ESTADO_RESERVA_LABELS, isSlotInPast } from './lib/api'
import {
  isReservaActiva,
  normalizeEstado,
  RESERVA_HOURS as HOURS,
  useMisReservasController,
} from './hooks/useMisReservasController'
import type { EstadoReserva, ReservaDto } from './lib/types'
import Navbar from './components/Navbar'
import Modal from './components/Modal'
import LoadingSpinner from './components/LoadingSpinner'
import PageBackground from './components/PageBackground'

function estadoBadgeClass(estado: string) {
  switch (normalizeEstado(estado)) {
    case 'PENDIENTE':
    case 'PENDIENTE_PAGO':
      return 'bg-yellow-100 text-yellow-800'
    case 'CONFIRMADA':
      return 'bg-green-100 text-green-800'
    case 'CANCELADA':
      return 'bg-red-100 text-red-700'
    case 'CANCELADA_ADMIN':
      return 'bg-red-200 text-red-900'
    case 'CONFIRMADA_PRESENCIAL':
      return 'bg-blue-100 text-blue-800'
    default:
      return 'bg-gray-100 text-gray-700'
  }
}

function canReprogramarReserva(r: ReservaDto) {
  return isReservaActiva(r)
}

function canCancelReserva(r: ReservaDto) {
  return isReservaActiva(r)
}

export default function VistaReserva() {
  const {
    resolvedGeneralBg,
    reservas,
    isLoading,
    canchaNameById,
    cancelModal,
    setCancelModal,
    cancelError,
    setCancelError,
    cancelando,
    cancelar,
    reprogramarModal,
    setReprogramarModal,
    nuevaFecha,
    setNuevaFecha,
    nuevaHora,
    setNuevaHora,
    reprogramarError,
    setReprogramarError,
    reprogramando,
    reprogramar,
    cargandoDisponibilidad,
    slotByHour,
    feedback,
    setFeedback,
    openReprogramarModal,
    todayColombia,
  } = useMisReservasController()

  return (
    <PageBackground imageUrl={resolvedGeneralBg}>
      <Navbar />
      <div className="w-full max-w-4xl mx-auto px-4 py-8 flex-1">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl border border-gray-200/80 shadow-lg px-6 py-4 mb-6 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              📋 Mis Reservas
              {reservas.length > 0 && (
                <span className="badge bg-green-100 text-green-700 text-sm">{reservas.length}</span>
              )}
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Consulta, edita/reagenda o cancela tus reservas activas
            </p>
          </div>
        </div>

        {feedback && (
          <div className="mb-5 bg-emerald-50/95 backdrop-blur-sm border border-emerald-200 text-emerald-800 rounded-xl px-4 py-3 text-sm font-medium flex items-center justify-between shadow-sm">
            <span className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
              {feedback}
            </span>
            <button onClick={() => setFeedback('')} className="text-xs text-emerald-700 hover:underline">Cerrar</button>
          </div>
        )}

        {isLoading ? (
          <LoadingSpinner />
        ) : reservas.length === 0 ? (
          <div className="card bg-white/95 backdrop-blur-sm shadow-lg text-center py-16">
            <div className="text-5xl mb-4">📭</div>
            <p className="text-lg font-medium text-gray-700">No tienes reservas aún</p>
            <p className="text-gray-400 mt-1">Ve al catálogo y reserva tu primera cancha</p>
          </div>
        ) : (
          <div className="space-y-4">
            {reservas.map(reserva => (
              <div key={reserva.id} className="card bg-white/95 backdrop-blur-sm shadow-lg">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      <span className="font-mono font-bold text-green-700 text-sm">{reserva.codigo_uid}</span>
                      <span className={`badge ${estadoBadgeClass(reserva.estado)}`}>
                        {ESTADO_RESERVA_LABELS[normalizeEstado(reserva.estado) as EstadoReserva] ?? reserva.estado}
                      </span>
                      {canchaNameById[reserva.cancha_id] && (
                        <span className="text-xs font-medium text-gray-600 bg-gray-100 px-2.5 py-0.5 rounded-full">
                          {canchaNameById[reserva.cancha_id]}
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                      <span className="flex items-center gap-1">
                        <Calendar size={14} /> {reserva.fecha}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock size={14} /> {reserva.hora_inicio.substring(0, 5)} – {reserva.hora_fin.substring(0, 5)}
                      </span>
                      <span className="font-semibold text-gray-800">{formatCOP(Number(reserva.monto))}</span>
                    </div>
                    {reserva.motivo_cancelacion && (
                      <p className="text-xs text-red-500 mt-1">Motivo: {reserva.motivo_cancelacion}</p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0 flex-wrap">
                    {canReprogramarReserva(reserva) && (
                      <button
                        onClick={() => openReprogramarModal(reserva)}
                        className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                      >
                        <Edit3 size={13} /> Editar / Reagendar
                      </button>
                    )}
                    {canCancelReserva(reserva) && (
                      <button
                        onClick={() => {
                          setCancelError('')
                          setCancelModal(reserva)
                        }}
                        className="btn-danger py-1.5 px-3 text-xs flex items-center gap-1"
                      >
                        <XCircle size={13} /> Cancelar
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Cancel Modal */}
      <Modal isOpen={!!cancelModal} onClose={() => { setCancelModal(null); setCancelError('') }} title="❌ Cancelar Reserva">
        {cancelModal && (
          <div className="space-y-4">
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="font-semibold text-red-800">{cancelModal.codigo_uid}</p>
              <p className="text-sm text-red-700">{cancelModal.fecha} · {cancelModal.hora_inicio.substring(0, 5)} – {cancelModal.hora_fin.substring(0, 5)}</p>
              <p className="text-xs text-red-500 mt-1">Esta acción no se puede deshacer.</p>
            </div>
            {cancelError && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-3 py-2 text-xs flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />
                <span>{cancelError}</span>
              </div>
            )}
            <div className="flex gap-3">
              <button onClick={() => { setCancelModal(null); setCancelError('') }} className="btn-secondary flex-1">Volver</button>
              <button
                onClick={() => cancelar(cancelModal.id)}
                disabled={cancelando}
                className="btn-danger flex-1 flex items-center justify-center gap-2"
              >
                {cancelando ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />}
                Confirmar Cancelación
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Editar / Reagendar Modal */}
      <Modal isOpen={!!reprogramarModal} onClose={() => setReprogramarModal(null)} title="✏️ Editar / Reagendar Reserva">
        {reprogramarModal && (
          <div className="space-y-4">
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm text-gray-700 space-y-0.5">
              <p className="font-semibold text-gray-900">
                {reprogramarModal.codigo_uid} {canchaNameById[reprogramarModal.cancha_id] ? `· ${canchaNameById[reprogramarModal.cancha_id]}` : ''}
              </p>
              <p className="text-xs text-gray-500">
                Horario actual: <strong>{reprogramarModal.fecha} · {reprogramarModal.hora_inicio.substring(0, 5)} – {reprogramarModal.hora_fin.substring(0, 5)}</strong>
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nueva fecha</label>
              <input
                type="date"
                value={nuevaFecha}
                min={todayColombia}
                onChange={e => {
                  setNuevaFecha(e.target.value)
                  setNuevaHora('')
                  setReprogramarError('')
                }}
                className="input-field"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-sm font-medium text-gray-700">
                  Nueva hora disponible (1 hora)
                </label>
                {cargandoDisponibilidad && (
                  <span className="text-xs text-emerald-700 flex items-center gap-1">
                    <Loader2 size={12} className="animate-spin" /> Consultando disponibilidad...
                  </span>
                )}
              </div>

              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-56 overflow-y-auto p-1">
                {HOURS.filter(h => !isSlotInPast(nuevaFecha, h)).map(h => {
                  const slot = slotByHour[h]
                  const isCurrentSlot =
                    nuevaFecha === reprogramarModal.fecha &&
                    h === reprogramarModal.hora_inicio.substring(0, 5)
                  const estado = slot?.estado ?? 'LIBRE'
                  const isBlocked =
                    isCurrentSlot ||
                    estado === 'OCUPADO' ||
                    estado === 'BLOQUEADO_TEMPORAL' ||
                    estado === 'MANTENIMIENTO'
                  const isSelected = nuevaHora === h

                  let statusText = 'Disponible'
                  if (isCurrentSlot) statusText = 'Actual'
                  else if (estado === 'MANTENIMIENTO') statusText = 'Mantto.'
                  else if (estado === 'OCUPADO' || estado === 'BLOQUEADO_TEMPORAL') statusText = 'Ocupado'

                  return (
                    <button
                      key={h}
                      type="button"
                      disabled={isBlocked || cargandoDisponibilidad}
                      onClick={() => {
                        setNuevaHora(h)
                        setReprogramarError('')
                      }}
                      className={`px-2 py-2 rounded-xl border text-center transition-all ${
                        isSelected
                          ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm ring-2 ring-emerald-300'
                          : isBlocked
                          ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                          : 'bg-white text-gray-800 border-gray-200 hover:border-emerald-400 hover:bg-emerald-50'
                      }`}
                    >
                      <div className="text-xs font-bold">{h}</div>
                      <div className={`text-[10px] ${isSelected ? 'text-emerald-100' : 'text-gray-500'}`}>
                        {statusText}
                      </div>
                    </button>
                  )
                })}
              </div>
              {nuevaHora && (
                <p className="text-xs text-emerald-700 font-medium mt-2">
                  Nuevo horario seleccionado: {nuevaFecha} de {nuevaHora} a {String(Number(nuevaHora.split(':')[0]) + 1).padStart(2, '0')}:00
                </p>
              )}
            </div>

            {reprogramarError && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-3 py-2 text-xs flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />
                <span>{reprogramarError}</span>
              </div>
            )}

            <div className="flex gap-3 pt-1">
              <button onClick={() => setReprogramarModal(null)} className="btn-secondary flex-1">Cancelar</button>
              <button
                onClick={() => reprogramar({ id: reprogramarModal.id, nuevaFecha, nuevaHora })}
                disabled={reprogramando || !nuevaFecha || !nuevaHora || cargandoDisponibilidad}
                className="btn-primary flex-1 flex items-center justify-center gap-2"
              >
                {reprogramando ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Confirmar Reagendamiento
              </button>
            </div>
          </div>
        )}
      </Modal>
    </PageBackground>
  )
}
