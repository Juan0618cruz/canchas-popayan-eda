import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  X,
  User,
  Phone,
  Mail,
  Calendar,
  Clock,
  DollarSign,
  CreditCard,
  RefreshCw,
  XCircle,
  CheckCircle,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  Banknote,
} from 'lucide-react'
import {
  reservasApi,
  pagosApi,
  formatCOP,
  ESTADO_RESERVA_LABELS,
  extractErrorMessage,
  isSlotInPast,
} from '../lib/api'
import type { BloqueHorarioDto, CanchaDto, ComplejoDto, ReservaDto } from '../lib/types'
import LoadingSpinner from './LoadingSpinner'

interface AdminReservaDrawerProps {
  isOpen: boolean
  onClose: () => void
  cancha: CanchaDto | null
  complejo: ComplejoDto | null
  bloque: BloqueHorarioDto | null
  onSuccessAction?: () => void
}

const HOURS = Array.from({ length: 14 }, (_, i) => `${String(i + 8).padStart(2, '0')}:00`)

function estadoBadge(estado: string) {
  const cls: Record<string, string> = {
    PENDIENTE_PAGO: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    CONFIRMADA: 'bg-green-100 text-green-800 border-green-300',
    CANCELADA: 'bg-red-100 text-red-700 border-red-300',
    CANCELADA_ADMIN: 'bg-red-200 text-red-900 border-red-400',
    CONFIRMADA_PRESENCIAL: 'bg-blue-100 text-blue-800 border-blue-300',
  }
  return cls[estado] ?? 'bg-gray-100 text-gray-700 border-gray-200'
}

function getClienteNombre(r: ReservaDto): string {
  const c = (r.cliente_nombre || r.usuario_nombre || r.nombre_cliente || '').trim()
  if (c && !c.toLowerCase().startsWith('usuario ')) return c
  return c || `Usuario ${r.usuario_id?.substring(0, 8) ?? 'N/A'}`
}

export default function AdminReservaDrawer({
  isOpen,
  onClose,
  cancha,
  complejo,
  bloque,
  onSuccessAction,
}: AdminReservaDrawerProps) {
  const queryClient = useQueryClient()

  // Section states
  const [showPagar, setShowPagar] = useState(false)
  const [metodoPago, setMetodoPago] = useState<'EFECTIVO' | 'BRE_B' | 'WOMPI'>('EFECTIVO')

  const [showReprogramar, setShowReprogramar] = useState(false)
  const [nuevaFecha, setNuevaFecha] = useState('')
  const [nuevaHora, setNuevaHora] = useState('')

  const [showCancelar, setShowCancelar] = useState(false)
  const [motivoCancelacion, setMotivoCancelacion] = useState('')

  // Consultar detalles completos de la reserva
  const {
    data: reserva,
    isLoading: loadingReserva,
    error: errorReserva,
    refetch: refetchReserva,
  } = useQuery<ReservaDto | null>({
    queryKey: ['admin-reserva-slot', cancha?.id, bloque?.fecha, bloque?.hora_inicio, bloque?.reserva_id],
    queryFn: async () => {
      if (!cancha || !bloque) return null
      if (bloque.reserva_id) {
        try {
          return await reservasApi.getByIdAdmin(bloque.reserva_id)
        } catch {
          // Búsqueda alternativa por franja horaria
        }
      }
      return await reservasApi.getPorSlot(cancha.id, bloque.fecha, bloque.hora_inicio)
    },
    enabled: isOpen && !!cancha && !!bloque,
  })

  // Consultar información financiera del pago asociado
  const {
    data: pago,
    isLoading: loadingPago,
    refetch: refetchPago,
  } = useQuery({
    queryKey: ['admin-pago-reserva', reserva?.id],
    queryFn: () => (reserva ? pagosApi.getPorReserva(reserva.id) : null),
    enabled: isOpen && !!reserva?.id,
  })

  // Mutation: Registrar Pago Ahora
  const { mutate: registrarPagoAhora, isPending: pagando } = useMutation({
    mutationFn: async () => {
      if (!reserva || !cancha) return
      const numericMonto = Number(reserva.monto) || Number(cancha.tarifa_por_hora) || 0
      try {
        await pagosApi.registrarPresencial({
          reserva_id: reserva.id,
          complejo_id: reserva.complejo_id || complejo?.id || 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
          monto: numericMonto,
          metodo: metodoPago,
          fecha: reserva.fecha,
          observaciones: `Pago presencial registrado desde panel lateral (${metodoPago}) - Cliente: ${getClienteNombre(reserva)}`,
        })
      } catch (e) {
        console.warn('pagosApi.registrarPresencial warning:', e)
      }

      await reservasApi.confirmarAdmin(reserva.id)
    },
    onSuccess: () => {
      setShowPagar(false)
      refetchReserva()
      refetchPago()
      queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['admin-pagos'] })
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
      onSuccessAction?.()
    },
    onError: (err: unknown) => {
      alert('❌ ' + extractErrorMessage(err, 'Error al registrar el pago presencial.'))
    },
  })

  // Mutation: Reprogramar Reserva
  const { mutate: reprogramar, isPending: reprogramando } = useMutation({
    mutationFn: async () => {
      if (!reserva) return
      const horaFin = `${String(Number(nuevaHora.split(':')[0]) + 1).padStart(2, '0')}:00:00`
      await reservasApi.reprogramarAdmin(reserva.id, {
        nueva_fecha: nuevaFecha,
        nueva_hora_inicio: nuevaHora.length === 5 ? nuevaHora + ':00' : nuevaHora,
        nueva_hora_fin: horaFin,
      })
    },
    onSuccess: () => {
      setShowReprogramar(false)
      refetchReserva()
      queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
      onSuccessAction?.()
    },
    onError: (err: unknown) => {
      alert('❌ ' + extractErrorMessage(err, 'Error al reprogramar la reserva.'))
    },
  })

  // Mutation: Cancelar Reserva
  const { mutate: cancelar, isPending: cancelando } = useMutation({
    mutationFn: async () => {
      if (!reserva) return
      await reservasApi.cancelarAdmin(
        reserva.id,
        motivoCancelacion.trim() || 'Cancelada por administrador desde catálogo'
      )
    },
    onSuccess: () => {
      setShowCancelar(false)
      queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
      onSuccessAction?.()
      onClose()
    },
    onError: (err: unknown) => {
      alert('❌ ' + extractErrorMessage(err, 'Error al cancelar la reserva.'))
    },
  })

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col">
          {/* Header */}
          <div className="p-5 bg-gradient-to-r from-emerald-800 to-green-700 text-white flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-white/10 rounded-xl backdrop-blur-sm">
                <ShieldCheck size={20} className="text-emerald-200" />
              </div>
              <div>
                <h3 className="text-base font-bold leading-tight">Gestión de Reserva (Admin)</h3>
                <p className="text-xs text-emerald-100 mt-0.5">
                  {cancha?.nombre} · {complejo?.nombre}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              title="Cerrar panel"
            >
              <X size={20} />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {loadingReserva ? (
              <div className="py-16 text-center">
                <LoadingSpinner />
                <p className="text-xs text-gray-500 mt-2">Consultando datos de la reserva...</p>
              </div>
            ) : errorReserva || !reserva ? (
              <div className="card text-center py-10 bg-amber-50 border-amber-200">
                <AlertTriangle className="mx-auto text-amber-500 mb-2" size={32} />
                <p className="font-semibold text-gray-800 text-sm">No se encontró información de la reserva</p>
                <p className="text-xs text-gray-500 mt-1">
                  Es posible que la reserva haya sido liberada o cancelada recientemente.
                </p>
                <button
                  onClick={() => refetchReserva()}
                  className="btn-secondary text-xs mt-4 inline-flex items-center gap-1.5"
                >
                  <RefreshCw size={14} /> Reintentar
                </button>
              </div>
            ) : (
              <>
                {/* 1. Identificación y Estado */}
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
                        CÓDIGO DE RESERVA
                      </span>
                      <span className="font-mono text-base font-extrabold text-emerald-800">
                        {reserva.codigo_uid}
                      </span>
                    </div>
                    <span
                      className={`badge border text-xs px-2.5 py-1 font-semibold ${estadoBadge(
                        reserva.estado
                      )}`}
                    >
                      {ESTADO_RESERVA_LABELS[reserva.estado as keyof typeof ESTADO_RESERVA_LABELS] ||
                        reserva.estado}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200 text-xs">
                    <div className="flex items-center gap-1.5 text-gray-600">
                      <Calendar size={14} className="text-gray-400 shrink-0" />
                      <span>{reserva.fecha}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-gray-600">
                      <Clock size={14} className="text-gray-400 shrink-0" />
                      <span>
                        {reserva.hora_inicio.substring(0, 5)} – {reserva.hora_fin.substring(0, 5)}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-gray-200 flex items-center justify-between">
                    <span className="text-xs text-gray-500">Tarifa aplicada:</span>
                    <span className="text-sm font-bold text-emerald-700">
                      {formatCOP(Number(reserva.monto))}
                    </span>
                  </div>
                </div>

                {/* 2. Información del Cliente */}
                <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2 shadow-sm">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
                    <User size={13} className="text-gray-400" /> Datos del Cliente
                  </h4>
                  <p className="text-sm font-semibold text-gray-900">{getClienteNombre(reserva)}</p>
                  <div className="space-y-1 text-xs text-gray-600 pt-1">
                    <div className="flex items-center gap-2">
                      <Phone size={13} className="text-gray-400" />
                      <span>{reserva.telefono_cliente || 'Sin teléfono registrado'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Mail size={13} className="text-gray-400" />
                      <span>{reserva.cliente_email || 'Sin correo registrado'}</span>
                    </div>
                  </div>
                </div>

                {/* 3. Información del Pago */}
                <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2 shadow-sm">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
                    <CreditCard size={13} className="text-gray-400" /> Estado del Pago
                  </h4>

                  {loadingPago ? (
                    <div className="py-2 text-center text-xs text-gray-400">Consultando pago...</div>
                  ) : pago ? (
                    <div className="space-y-2 pt-1 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Referencia:</span>
                        <span className="font-mono font-semibold text-gray-800">
                          {pago.referencia_externa || pago.id.substring(0, 8)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Método:</span>
                        <span className="font-semibold text-gray-900">{pago.metodo}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Monto:</span>
                        <span className="font-bold text-emerald-700">{formatCOP(Number(pago.monto))}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Fecha de pago:</span>
                        <span className="text-gray-600">
                          {pago.created_at ? new Date(pago.created_at).toLocaleString('es-CO') : 'N/A'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-gray-500">Estado:</span>
                        <span className="badge bg-green-100 text-green-800 font-bold text-[11px]">
                          ✓ APROBADO
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900">
                      <div className="flex items-center gap-1.5 font-bold">
                        <AlertTriangle size={14} className="text-amber-600" />
                        <span>Pendiente por cobrar</span>
                      </div>
                      <p className="mt-1 text-gray-600">
                        La reserva está bloqueando el horario pero aún no registra pago.
                      </p>
                      <p className="mt-1.5 font-bold text-emerald-800">
                        Valor a cobrar: {formatCOP(Number(reserva.monto))}
                      </p>
                    </div>
                  )}
                </div>

                {/* 4. Acciones Directas */}
                <div className="space-y-2.5 pt-2">
                  <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                    Acciones de Taquilla
                  </h4>

                  {/* Botón 1: Registrar Pago Ahora (si está PENDIENTE_PAGO) */}
                  {reserva.estado === 'PENDIENTE_PAGO' && (
                    <div className="bg-emerald-50/70 border border-emerald-300 rounded-xl p-3.5 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-emerald-950 flex items-center gap-1.5">
                          <Banknote size={15} className="text-emerald-700" /> Registrar Cobro Presencial
                        </span>
                        <button
                          type="button"
                          onClick={() => setShowPagar(!showPagar)}
                          className="text-xs text-emerald-700 font-semibold underline hover:text-emerald-900"
                        >
                          {showPagar ? 'Ocultar' : 'Abrir'}
                        </button>
                      </div>

                      {showPagar && (
                        <div className="space-y-2.5 pt-2 border-t border-emerald-200/80">
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Método de pago recibido:
                            </label>
                            <select
                              value={metodoPago}
                              onChange={(e) => setMetodoPago(e.target.value as any)}
                              className="input-field text-xs"
                            >
                              <option value="EFECTIVO">💵 Efectivo (Caja Taquilla)</option>
                              <option value="BRE_B">🔑 Bre-B</option>
                              <option value="WOMPI">🟢 Wompi</option>
                            </select>
                          </div>
                          <button
                            type="button"
                            onClick={() => registrarPagoAhora()}
                            disabled={pagando}
                            className="btn-primary w-full text-xs py-2 bg-emerald-600 hover:bg-emerald-700 flex items-center justify-center gap-1.5 font-bold shadow-sm"
                          >
                            {pagando ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                            Confirmar Pago y Activar Reserva
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Botón 2: Reprogramar Reserva */}
                  {!['CANCELADA', 'CANCELADA_ADMIN'].includes(reserva.estado) && (
                    <div className="bg-blue-50/60 border border-blue-200 rounded-xl p-3.5 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-blue-950 flex items-center gap-1.5">
                          <RefreshCw size={14} className="text-blue-700" /> Reprogramar Reserva
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setShowReprogramar(!showReprogramar)
                            if (!nuevaFecha) setNuevaFecha(reserva.fecha)
                          }}
                          className="text-xs text-blue-700 font-semibold underline hover:text-blue-900"
                        >
                          {showReprogramar ? 'Ocultar' : 'Configurar'}
                        </button>
                      </div>

                      {showReprogramar && (
                        <div className="space-y-2 pt-2 border-t border-blue-200/80 text-xs">
                          <div>
                            <label className="block font-medium text-gray-700 mb-1">Nueva Fecha:</label>
                            <input
                              type="date"
                              value={nuevaFecha}
                              min={new Date().toISOString().split('T')[0]}
                              onChange={(e) => setNuevaFecha(e.target.value)}
                              className="input-field text-xs"
                            />
                          </div>
                          <div>
                            <label className="block font-medium text-gray-700 mb-1">Nueva Hora Inicio:</label>
                            <select
                              value={nuevaHora}
                              onChange={(e) => setNuevaHora(e.target.value)}
                              className="input-field text-xs"
                            >
                              <option value="">Seleccionar hora</option>
                              {HOURS.filter((h) => !nuevaFecha || !isSlotInPast(nuevaFecha, h)).map((h) => (
                                <option key={h} value={h}>
                                  {h}
                                </option>
                              ))}
                            </select>
                          </div>
                          <button
                            type="button"
                            onClick={() => reprogramar()}
                            disabled={reprogramando || !nuevaFecha || !nuevaHora}
                            className="btn-primary w-full text-xs py-2 bg-blue-600 hover:bg-blue-700 flex items-center justify-center gap-1.5 font-bold"
                          >
                            {reprogramando ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                            Guardar Nueva Fecha y Hora
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Botón 3: Cancelar Reserva */}
                  {!['CANCELADA', 'CANCELADA_ADMIN'].includes(reserva.estado) && (
                    <div className="bg-red-50/60 border border-red-200 rounded-xl p-3.5 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-red-950 flex items-center gap-1.5">
                          <XCircle size={14} className="text-red-700" /> Cancelar Reserva (Admin)
                        </span>
                        <button
                          type="button"
                          onClick={() => setShowCancelar(!showCancelar)}
                          className="text-xs text-red-700 font-semibold underline hover:text-red-900"
                        >
                          {showCancelar ? 'Ocultar' : 'Cancelar'}
                        </button>
                      </div>

                      {showCancelar && (
                        <div className="space-y-2 pt-2 border-t border-red-200/80 text-xs">
                          <div>
                            <label className="block font-medium text-gray-700 mb-1">
                              Motivo de cancelación:
                            </label>
                            <input
                              type="text"
                              value={motivoCancelacion}
                              onChange={(e) => setMotivoCancelacion(e.target.value)}
                              placeholder="Ej: Cliente canceló llamada, mantenimiento..."
                              className="input-field text-xs"
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() => cancelar()}
                            disabled={cancelando}
                            className="btn-danger w-full text-xs py-2 flex items-center justify-center gap-1.5 font-bold"
                          >
                            {cancelando ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
                            Confirmar Cancelación y Liberar Horario
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
