import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, XCircle, RefreshCw, Loader2, Calendar, Search, X, Banknote, CheckCircle } from 'lucide-react'
import { reservasApi, canchasApi, pagosApi, formatCOP, ESTADO_RESERVA_LABELS, extractErrorMessage, isSlotInPast } from '../lib/api'
import { useAuthStore } from '../store/authStore'
import type { EstadoReserva, ReservaDto } from '../lib/types'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'

function estadoBadge(estado: EstadoReserva) {
  const cls: Record<string, string> = {
    PENDIENTE_PAGO: 'bg-yellow-100 text-yellow-800',
    CONFIRMADA: 'bg-green-100 text-green-800',
    CANCELADA: 'bg-red-100 text-red-700',
    CANCELADA_ADMIN: 'bg-red-200 text-red-900',
    CONFIRMADA_PRESENCIAL: 'bg-blue-100 text-blue-800',
  }
  return cls[estado] ?? 'bg-gray-100 text-gray-700'
}

const HOURS = Array.from({ length: 14 }, (_, i) => `${String(i + 8).padStart(2, '0')}:00`)

function today() { return new Date().toISOString().split('T')[0] }

function normalizarTexto(valor: string): string {
  return valor
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function getClienteNombreReal(r: ReservaDto): string {
  const candidato = (r.cliente_nombre || r.usuario_nombre || r.nombre_cliente || '').trim()
  if (candidato && !candidato.toLowerCase().startsWith('usuario ')) {
    return candidato
  }
  return candidato || `Usuario ${r.usuario_id?.substring(0, 8) ?? 'N/A'}`
}

export default function VistaAdminTaquilla() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [fecha, setFecha] = useState(today())
  const [mostrarTodasFechas, setMostrarTodasFechas] = useState(false)
  const [busquedaCliente, setBusquedaCliente] = useState('')

  // Modals state
  const [presencialModal, setPresencialModal] = useState(false)
  const [cancelModal, setCancelModal] = useState<ReservaDto | null>(null)
  const [reprogramarModal, setReprogramarModal] = useState<ReservaDto | null>(null)
  const [pagoPendienteModal, setPagoPendienteModal] = useState<ReservaDto | null>(null)
  const [metodoPagoPendiente, setMetodoPagoPendiente] = useState<'EFECTIVO' | 'BRE_B' | 'WOMPI'>('EFECTIVO')
  const [motivo, setMotivo] = useState('')
  const [nuevaFecha, setNuevaFecha] = useState('')
  const [nuevaHora, setNuevaHora] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Presencial form
  const [presForm, setPresForm] = useState({
    cancha_id: '',
    nombre_cliente: '',
    telefono_cliente: '',
    hora_inicio: '',
    monto: '',
    paga_ahora: true,
    metodo_pago: 'EFECTIVO' as 'EFECTIVO' | 'BRE_B' | 'WOMPI',
  })

  const { data: reservas = [], isLoading } = useQuery({
    queryKey: ['admin-reservas', mostrarTodasFechas ? 'ALL' : fecha],
    queryFn: () => reservasApi.todasAdmin(mostrarTodasFechas ? undefined : fecha),
    refetchInterval: 10000,
  })

  const filteredReservas = useMemo(() => {
    const q = normalizarTexto(busquedaCliente.trim())
    if (!q) return reservas
    return reservas.filter((r) => normalizarTexto(getClienteNombreReal(r)).includes(q))
  }, [reservas, busquedaCliente])

  const { data: canchas = [] } = useQuery({
    queryKey: ['admin-canchas'],
    queryFn: canchasApi.getMisCanchas,
  })

  const { data: complejos = [] } = useQuery({
    queryKey: ['complejos'],
    queryFn: canchasApi.getComplejos,
  })

  const { mutate: crearPresencial, isPending: creandoPresencial } = useMutation({
    mutationFn: async () => {
      if (isSlotInPast(fecha, presForm.hora_inicio)) {
        throw new Error('No se pueden realizar reservas en horarios pasados.')
      }
      const cancha = canchas.find(c => c.id === presForm.cancha_id)
      const horaFin = `${String(Number(presForm.hora_inicio.split(':')[0]) + 1).padStart(2, '0')}:00:00`
      const numericMonto = parseFloat(presForm.monto) || (cancha ? Number(cancha.tarifa_por_hora) : 0)

      const res = await reservasApi.crearPresencial({
        cancha_id: presForm.cancha_id,
        complejo_id: cancha?.complejo_id ?? user?.establecimiento_id ?? 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        nombre_cliente: presForm.nombre_cliente || 'Cliente Taquilla',
        cliente_nombre: presForm.nombre_cliente || 'Cliente Taquilla',
        telefono_cliente: presForm.telefono_cliente || '3001234567',
        fecha,
        hora_inicio: presForm.hora_inicio.length === 5 ? presForm.hora_inicio + ':00' : presForm.hora_inicio,
        hora_fin: horaFin,
        monto: numericMonto,
        admin_id: user?.id || '33333333-3333-3333-3333-333333333333',
        estado: presForm.paga_ahora ? 'CONFIRMADA' : 'PENDIENTE_PAGO',
        pagado: presForm.paga_ahora,
        metodo_pago: presForm.paga_ahora ? presForm.metodo_pago : undefined,
      })

      // Sincronizar pago aprobado en ms_pagos si pagó ahora
      if (presForm.paga_ahora) {
        try {
          await pagosApi.registrarPresencial({
            reserva_id: res.id,
            complejo_id: res.complejo_id || user?.establecimiento_id || 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            monto: numericMonto,
            metodo: presForm.metodo_pago,
            fecha,
            observaciones: `Pago presencial en taquilla (${presForm.metodo_pago}) - Cliente: ${presForm.nombre_cliente || 'Taquilla'}`,
          })
        } catch (e) {
          console.warn('ms_pagos registrarPresencial warning:', e)
        }
      }

      return res
    },
    onSuccess: () => {
      setPresencialModal(false)
      setPresForm({
        cancha_id: '',
        nombre_cliente: '',
        telefono_cliente: '',
        hora_inicio: '',
        monto: '',
        paga_ahora: true,
        metodo_pago: 'EFECTIVO',
      })
      queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['admin-pagos'] })
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al crear la reserva presencial')),
  })

  const { mutate: confirmarPagoPendiente, isPending: confirmandoPago } = useMutation({
    mutationFn: async () => {
      if (!pagoPendienteModal) return
      const numericMonto = Number(pagoPendienteModal.monto) || 0
      try {
        await pagosApi.registrarPresencial({
          reserva_id: pagoPendienteModal.id,
          complejo_id: pagoPendienteModal.complejo_id || user?.establecimiento_id || 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
          monto: numericMonto,
          metodo: metodoPagoPendiente,
          fecha: pagoPendienteModal.fecha,
          observaciones: `Pago presencial registrado en taquilla (${metodoPagoPendiente}) - Cliente: ${getClienteNombreReal(pagoPendienteModal)}`,
        })
      } catch (e) {
        console.warn('pagosApi.registrarPresencial warning:', e)
      }

      await reservasApi.confirmarAdmin(pagoPendienteModal.id)
    },
    onSuccess: () => {
      const codigo = pagoPendienteModal?.codigo_uid || 'Reserva'
      const cliente = pagoPendienteModal ? getClienteNombreReal(pagoPendienteModal) : 'Cliente'
      setSuccessMsg(`✅ ¡Pago presencial (${metodoPagoPendiente}) registrado con éxito para ${codigo} (${cliente})! La reserva ha sido CONFIRMADA.`)
      setPagoPendienteModal(null)
      queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['admin-pagos'] })
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
      setTimeout(() => setSuccessMsg(''), 6000)
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al registrar el pago presencial')),
  })

  const { mutate: cancelarAdmin, isPending: cancelando } = useMutation({
    mutationFn: () => reservasApi.cancelarAdmin(cancelModal!.id, motivo || 'Cancelada por administrador'),
    onSuccess: () => {
      setCancelModal(null)
      setMotivo('')
      queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al cancelar la reserva')),
  })

  const { mutate: reprogramarAdmin, isPending: reprogramando } = useMutation({
    mutationFn: () => {
      if (isSlotInPast(nuevaFecha, nuevaHora)) {
        throw new Error('No se pueden realizar reservas en horarios pasados.')
      }
      return reservasApi.reprogramarAdmin(reprogramarModal!.id, {
        nueva_fecha: nuevaFecha,
        nueva_hora_inicio: nuevaHora + ':00',
        nueva_hora_fin: `${String(Number(nuevaHora.split(':')[0]) + 1).padStart(2, '0')}:00:00`,
      })
    },
    onSuccess: () => {
      setReprogramarModal(null)
      queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al reprogramar la reserva')),
  })

  const handleCanchaChange = (canchaId: string) => {
    const cancha = canchas.find(c => c.id === canchaId)
    setPresForm(f => ({
      ...f,
      cancha_id: canchaId,
      monto: cancha ? String(cancha.tarifa_por_hora) : '',
    }))
  }

  return (
    <div className="w-full flex flex-col min-h-0 overflow-y-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-bold text-gray-900">📋 Taquilla y Agenda (HU-16, HU-17, HU-18)</h2>
        <button onClick={() => setPresencialModal(true)} className="btn-primary flex items-center gap-2 text-sm">
          <Plus size={16} /> Nueva Reserva Presencial
        </button>
      </div>

      {/* Alerta de Éxito al Registrar Pago */}
      {successMsg && (
        <div className="mb-4 bg-emerald-50 border border-emerald-300 text-emerald-900 px-4 py-3 rounded-xl flex items-center justify-between shadow-sm animate-fade-in">
          <div className="flex items-center gap-2.5">
            <CheckCircle className="text-emerald-600 shrink-0" size={20} />
            <span className="text-sm font-semibold">{successMsg}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMsg('')}
            className="text-emerald-700 hover:text-emerald-950 text-sm font-bold ml-3 px-2 py-1 rounded hover:bg-emerald-100"
            title="Cerrar notificación"
          >
            ✕
          </button>
        </div>
      )}

      {/* Date & client name filter bar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Calendar size={16} className="text-gray-400" />
          <label className="text-sm font-medium text-gray-700">Fecha:</label>
          <input
            type="date"
            value={fecha}
            disabled={mostrarTodasFechas}
            onChange={e => setFecha(e.target.value)}
            className="input-field w-40 disabled:opacity-50"
          />
        </div>

        <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer select-none px-2.5 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50">
          <input
            type="checkbox"
            checked={mostrarTodasFechas}
            onChange={e => setMostrarTodasFechas(e.target.checked)}
            className="rounded border-gray-300 text-green-600 focus:ring-green-500"
          />
          Todas las fechas
        </label>

        <div className="relative flex-1 min-w-[240px] max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          <input
            type="text"
            value={busquedaCliente}
            onChange={e => setBusquedaCliente(e.target.value)}
            placeholder="Buscar cliente por nombre..."
            className="input-field w-full pl-9 pr-8"
          />
          {busquedaCliente && (
            <button
              type="button"
              onClick={() => setBusquedaCliente('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              title="Limpiar búsqueda"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <span className="text-sm text-gray-500 ml-auto">
          {filteredReservas.length} {filteredReservas.length === 1 ? 'reserva encontrada' : 'reservas encontradas'}
        </span>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : filteredReservas.length === 0 ? (
        <div className="card text-center py-10">
          <p className="text-gray-400">
            {busquedaCliente.trim()
              ? `No hay reservas que coincidan con "${busquedaCliente.trim()}".`
              : 'No hay reservas para esta fecha.'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto max-h-[calc(100vh-270px)] min-h-[320px] overflow-y-auto">
          <table className="w-full min-w-[780px]">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
              <tr>
                {['Código', 'Cliente', 'Fecha', 'Horario', 'Monto', 'Estado', 'Acciones'].map(h => (
                  <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-4 py-3 bg-gray-50">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredReservas.map(r => (
                <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-green-700">{r.codigo_uid}</td>
                  <td className="px-4 py-3 text-sm">
                    <p className="font-medium text-gray-900">{getClienteNombreReal(r)}</p>
                    {r.telefono_cliente && <p className="text-xs text-gray-400">{r.telefono_cliente}</p>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap font-medium">
                    {r.fecha}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                    {r.hora_inicio.substring(0, 5)} – {r.hora_fin.substring(0, 5)}
                  </td>
                  <td className="px-4 py-3 text-sm font-semibold text-green-700">{formatCOP(Number(r.monto))}</td>
                  <td className="px-4 py-3">
                    <span className={`badge text-xs ${estadoBadge(r.estado)}`}>{ESTADO_RESERVA_LABELS[r.estado]}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {['PENDIENTE', 'PENDIENTE_PAGO'].includes(r.estado) && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            setPagoPendienteModal(r)
                            setMetodoPagoPendiente('EFECTIVO')
                          }}
                          className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white rounded-lg transition-all flex items-center gap-1 text-xs font-semibold shadow-sm mr-1 cursor-pointer"
                          title="Registrar Pago / Confirmar"
                        >
                          <Banknote size={14} />
                          <span>Pagar</span>
                        </button>
                      )}
                      {!['CANCELADA', 'CANCELADA_ADMIN'].includes(r.estado) && (
                        <>
                          <button onClick={() => { setReprogramarModal(r); setNuevaFecha(r.fecha); setNuevaHora('') }}
                            className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors" title="Reprogramar">
                            <RefreshCw size={14} />
                          </button>
                          <button onClick={() => { setCancelModal(r); setMotivo('') }}
                            className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Cancelar (Admin)">
                            <XCircle size={14} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Nueva Reserva Presencial Modal */}
      <Modal isOpen={presencialModal} onClose={() => setPresencialModal(false)} title="➕ Reserva Presencial en Taquilla" size="lg">
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cancha</label>
            <select value={presForm.cancha_id} onChange={e => handleCanchaChange(e.target.value)} className="input-field">
              <option value="">Selecciona una cancha</option>
              {canchas.map(c => {
                const comp = complejos.find(cp => cp.id === c.complejo_id)
                return (
                  <option key={c.id} value={c.id}>
                    {c.nombre} ({comp?.nombre || 'Complejo'}) — {c.tipo} — {formatCOP(Number(c.tarifa_por_hora))}/h {c.activo ? '' : '⚠️ [Inactiva]'}
                  </option>
                )
              })}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Hora inicio</label>
              <select value={presForm.hora_inicio} onChange={e => setPresForm(f => ({ ...f, hora_inicio: e.target.value }))} className="input-field">
                <option value="">Seleccionar</option>
                {HOURS.map(h => {
                  const isPast = isSlotInPast(fecha, h)
                  return (
                    <option key={h} value={h} disabled={isPast} className={isPast ? 'text-gray-400 bg-gray-100' : ''}>
                      {h} {isPast ? '(Pasada)' : ''}
                    </option>
                  )
                })}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Monto (COP)</label>
              <input
                type="text"
                inputMode="numeric"
                value={presForm.monto}
                onChange={e => {
                  const val = e.target.value.replace(/[^0-9]/g, '')
                  setPresForm(f => ({ ...f, monto: val }))
                }}
                placeholder="Ej: 70000"
                className="input-field"
              />
              <p className="text-xs text-gray-400 mt-0.5">Puedes escribir y borrar el valor libremente</p>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre del cliente</label>
            <input type="text" value={presForm.nombre_cliente} onChange={e => setPresForm(f => ({ ...f, nombre_cliente: e.target.value }))} className="input-field" placeholder="Juan García" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Teléfono del cliente</label>
            <input type="tel" value={presForm.telefono_cliente} onChange={e => setPresForm(f => ({ ...f, telefono_cliente: e.target.value }))} className="input-field" placeholder="3001234567" />
          </div>

          {/* Selector de Estado de Pago (HU Presencial) */}
          <div className="bg-emerald-50/50 border border-emerald-200/80 rounded-xl p-3.5 space-y-2.5">
            <label className="block text-sm font-semibold text-gray-900">
              ¿El cliente realiza el pago ahora?
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <label className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${
                presForm.paga_ahora
                  ? 'border-emerald-500 bg-emerald-100/70 text-emerald-950 font-medium ring-1 ring-emerald-500'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
              }`}>
                <input
                  type="radio"
                  name="paga_ahora"
                  checked={presForm.paga_ahora}
                  onChange={() => setPresForm(f => ({ ...f, paga_ahora: true }))}
                  className="text-emerald-600 focus:ring-emerald-500"
                />
                <span className="text-xs sm:text-sm">✅ Sí, pagó ahora (Confirmar reserva)</span>
              </label>
              <label className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${
                !presForm.paga_ahora
                  ? 'border-amber-500 bg-amber-100/70 text-amber-950 font-medium ring-1 ring-amber-500'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
              }`}>
                <input
                  type="radio"
                  name="paga_ahora"
                  checked={!presForm.paga_ahora}
                  onChange={() => setPresForm(f => ({ ...f, paga_ahora: false }))}
                  className="text-amber-600 focus:ring-amber-500"
                />
                <span className="text-xs sm:text-sm">⏳ No, dejar Pendiente de Pago</span>
              </label>
            </div>

            {presForm.paga_ahora && (
              <div className="pt-1.5 border-t border-emerald-200/60 mt-2">
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Método de pago presencial:
                </label>
                <select
                  value={presForm.metodo_pago}
                  onChange={e => setPresForm(f => ({ ...f, metodo_pago: e.target.value as any }))}
                  className="input-field text-sm"
                >
                  <option value="EFECTIVO">💵 Efectivo (Caja / Taquilla)</option>
                  <option value="BRE_B">🔑 Bre-B</option>
                  <option value="WOMPI">🟢 Wompi</option>
                </select>
              </div>
            )}
          </div>

          <div className="flex gap-3 pt-3 border-t border-gray-100 mt-2">
            <button onClick={() => setPresencialModal(false)} className="btn-secondary flex-1">Cancelar</button>
            <button
              onClick={() => crearPresencial()}
              disabled={creandoPresencial || !presForm.cancha_id || !presForm.hora_inicio || !presForm.nombre_cliente}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {creandoPresencial ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              {presForm.paga_ahora ? 'Confirmar y Crear Reserva' : 'Crear como Pendiente'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Cancel Admin Modal */}
      <Modal isOpen={!!cancelModal} onClose={() => setCancelModal(null)} title="❌ Cancelar Reserva (Admin)">
        {cancelModal && (
          <div className="space-y-4">
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="font-semibold text-red-800">{cancelModal.codigo_uid}</p>
              <p className="text-sm text-red-600">{cancelModal.fecha} · {cancelModal.hora_inicio.substring(0, 5)}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Motivo de cancelación</label>
              <textarea value={motivo} onChange={e => setMotivo(e.target.value)}
                className="input-field" rows={2} placeholder="Ej: Mantenimiento de cancha, cliente no se presentó..." />
            </div>
            <div className="flex gap-3">
              <button onClick={() => setCancelModal(null)} className="btn-secondary flex-1">Volver</button>
              <button onClick={() => cancelarAdmin()} disabled={cancelando} className="btn-danger flex-1 flex items-center justify-center gap-2">
                {cancelando ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />}
                Cancelar Reserva
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Reprogramar Admin Modal */}
      <Modal isOpen={!!reprogramarModal} onClose={() => setReprogramarModal(null)} title="🔄 Reprogramar Reserva">
        {reprogramarModal && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">Código: <strong>{reprogramarModal.codigo_uid}</strong></p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nueva fecha</label>
              <input type="date" value={nuevaFecha} min={today()} onChange={e => setNuevaFecha(e.target.value)} className="input-field" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nueva hora de inicio</label>
              <select value={nuevaHora} onChange={e => setNuevaHora(e.target.value)} className="input-field">
                <option value="">Seleccionar hora</option>
                {HOURS.map(h => {
                  const isPast = isSlotInPast(nuevaFecha, h)
                  return (
                    <option key={h} value={h} disabled={isPast} className={isPast ? 'text-gray-400 bg-gray-100' : ''}>
                      {h} {isPast ? '(Pasada)' : ''}
                    </option>
                  )
                })}
              </select>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setReprogramarModal(null)} className="btn-secondary flex-1">Cancelar</button>
              <button
                onClick={() => reprogramarAdmin()}
                disabled={reprogramando || !nuevaFecha || !nuevaHora}
                className="btn-primary flex-1 flex items-center justify-center gap-2"
              >
                {reprogramando ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Reprogramar
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Registrar Pago Presencial Modal (HU-20) */}
      <Modal
        isOpen={!!pagoPendienteModal}
        onClose={() => setPagoPendienteModal(null)}
        title="💵 Registrar Pago Presencial / Confirmar Reserva"
        size="lg"
      >
        {pagoPendienteModal && (
          <div className="space-y-4">
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-mono font-bold text-emerald-900">{pagoPendienteModal.codigo_uid}</p>
                <span className="badge bg-yellow-100 text-yellow-800 text-xs font-semibold">Pendiente de Pago</span>
              </div>
              <p className="text-sm text-gray-800">
                Cliente: <strong>{getClienteNombreReal(pagoPendienteModal)}</strong>
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 pt-1 border-t border-emerald-100">
                <div>
                  <span className="font-medium text-gray-500 block">Fecha:</span>
                  <span>{pagoPendienteModal.fecha}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-500 block">Horario:</span>
                  <span>
                    {pagoPendienteModal.hora_inicio ? pagoPendienteModal.hora_inicio.substring(0, 5) : '00:00'} -{' '}
                    {pagoPendienteModal.hora_fin ? pagoPendienteModal.hora_fin.substring(0, 5) : '00:00'}
                  </span>
                </div>
              </div>
              <div className="pt-2 border-t border-emerald-200/80 flex items-center justify-between">
                <span className="text-xs text-emerald-900 font-medium">Total a Cobrar:</span>
                <span className="text-lg font-black text-emerald-800">
                  {formatCOP(Number(pagoPendienteModal.monto || 0))}
                </span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-800 mb-1">
                Método de Pago Recibido:
              </label>
              <select
                value={metodoPagoPendiente}
                onChange={e => setMetodoPagoPendiente(e.target.value as any)}
                className="input-field text-sm"
              >
                <option value="EFECTIVO">💵 Efectivo (Caja / Taquilla)</option>
                <option value="BRE_B">🔑 Bre-B</option>
                <option value="WOMPI">🟢 Wompi</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Al confirmar, se registrará el pago presencial y la reserva pasará a CONFIRMADA automáticamente.
              </p>
            </div>

            {/* Botones inferiores dentro del flujo con scroll */}
            <div className="flex gap-3 pt-3 border-t border-gray-200 mt-2">
              <button
                type="button"
                onClick={() => setPagoPendienteModal(null)}
                className="btn-secondary flex-1"
                disabled={confirmandoPago}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => confirmarPagoPendiente()}
                disabled={confirmandoPago}
                className="btn-primary flex-1 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 font-bold"
              >
                {confirmandoPago ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                Confirmar y Registrar Pago
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
