import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { DollarSign, Loader2, CheckCircle } from 'lucide-react'
import { pagosApi, formatCOP, extractErrorMessage } from '../lib/api'
import type { EstadoPago } from '../lib/types'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'

function estadoPagoBadge(estado: EstadoPago) {
  const cls: Record<EstadoPago, string> = {
    PENDIENTE: 'bg-yellow-100 text-yellow-800',
    APROBADO: 'bg-green-100 text-green-800',
    RECHAZADO: 'bg-red-100 text-red-700',
  }
  return cls[estado]
}

const METODO_LABELS: Record<string, string> = {
  WOMPI: '🟢 Wompi',
  BRE_B: '🔑 Bre-B',
  EFECTIVO: '💵 Efectivo',
  WOMPI_NEQUI: '🟢 Wompi',
  WOMPI_PSE: '🟢 Wompi',
  WOMPI_BANCOLOMBIA: '🟢 Wompi',
  WOMPI_CARD: '🟢 Wompi',
  TARJETA: '🟢 Wompi',
  TRANSFERENCIA: '🔑 Bre-B',
}

function today() { return '2026-11-30' }
function startOfNovember() { return '2026-11-01' }

export default function VistaAdminPagos() {
  const queryClient = useQueryClient()

  const [fechaInicio, setFechaInicio] = useState(startOfNovember())
  const [fechaFin, setFechaFin] = useState(today())
  const [estadoFiltro, setEstadoFiltro] = useState<EstadoPago | ''>('')
  const [presencialModal, setPresencialModal] = useState<{ reserva_id: string; complejo_id: string; monto: number } | null>(null)
  const [metodo, setMetodo] = useState<'EFECTIVO' | 'BRE_B' | 'WOMPI'>('EFECTIVO')
  const [observaciones, setObservaciones] = useState('')

  const { data: pagos = [], isLoading, refetch } = useQuery({
    queryKey: ['admin-pagos', fechaInicio, fechaFin, estadoFiltro],
    queryFn: () => pagosApi.reportesAdmin({
      fecha_inicio: fechaInicio || undefined,
      fecha_fin: fechaFin || undefined,
      estado: estadoFiltro || undefined,
    }),
    refetchInterval: 5000,
  })

  const { mutate: registrarPresencial, isPending: registrando } = useMutation({
    mutationFn: () => pagosApi.registrarPresencial({
      reserva_id: presencialModal!.reserva_id,
      complejo_id: presencialModal!.complejo_id,
      monto: presencialModal!.monto,
      metodo,
      observaciones: observaciones || undefined,
    }),
    onSuccess: () => {
      setPresencialModal(null)
      setObservaciones('')
      queryClient.invalidateQueries({ queryKey: ['admin-pagos'] })
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al registrar pago.')),
  })

  const totalIngresos = pagos
    .filter(p => p.estado === 'APROBADO')
    .reduce((sum, p) => sum + Number(p.monto), 0)

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-900 mb-5 flex items-center gap-2">
        <DollarSign size={22} className="text-green-600" />
        Caja y Pagos (HU-19, HU-20)
      </h2>

      {/* Filters */}
      <div className="card mb-5">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Fecha inicio</label>
            <input type="date" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)} className="input-field w-36" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Fecha fin</label>
            <input type="date" value={fechaFin} onChange={e => setFechaFin(e.target.value)} className="input-field w-36" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Estado</label>
            <select value={estadoFiltro} onChange={e => setEstadoFiltro(e.target.value as EstadoPago | '')} className="input-field w-36">
              <option value="">Todos</option>
              <option value="APROBADO">Aprobado</option>
              <option value="RECHAZADO">Rechazado</option>
              <option value="PENDIENTE">Pendiente</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={() => refetch()} className="btn-primary py-2 text-sm">Buscar</button>
            <button
              onClick={() => {
                setFechaInicio('')
                setFechaFin('')
                setEstadoFiltro('')
                setTimeout(() => refetch(), 50)
              }}
              className="btn-secondary py-2 text-sm"
            >
              Ver Todos
            </button>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        <div className="card text-center">
          <p className="text-2xl font-bold text-green-700">{formatCOP(totalIngresos)}</p>
          <p className="text-xs text-gray-500 mt-1">Total Ingresos Aprobados</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-gray-900">{pagos.length}</p>
          <p className="text-xs text-gray-500 mt-1">Transacciones</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-green-600">{pagos.filter(p => p.estado === 'APROBADO').length}</p>
          <p className="text-xs text-gray-500 mt-1">Pagos Aprobados</p>
        </div>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : pagos.length === 0 ? (
        <div className="card text-center py-10">
          <p className="text-gray-400">No hay pagos para los filtros seleccionados.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          <table className="w-full min-w-[700px]">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Fecha', 'Reserva ID', 'Método', 'Monto', 'Estado', 'Referencia', 'Acción'].map(h => (
                  <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {pagos.map(pago => (
                <tr key={pago.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 text-xs text-gray-600">
                    {new Date(pago.created_at).toLocaleDateString('es-CO')}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">
                    {pago.reserva_id ? String(pago.reserva_id).substring(0, 12) + '...' : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm">{METODO_LABELS[pago.metodo] || pago.metodo || 'EFECTIVO'}</td>
                  <td className="px-4 py-3 text-sm font-semibold text-green-700">{formatCOP(Number(pago.monto))}</td>
                  <td className="px-4 py-3">
                    <span className={`badge text-xs ${estadoPagoBadge(pago.estado)}`}>{pago.estado}</span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-400">
                    {pago.referencia_externa ?? '—'}
                  </td>
                  <td className="px-4 py-3">
                    {pago.estado === 'PENDIENTE' && (
                      <button
                        onClick={() => setPresencialModal({
                          reserva_id: pago.reserva_id,
                          complejo_id: pago.complejo_id,
                          monto: Number(pago.monto),
                        })}
                        className="btn-primary py-1 text-xs flex items-center gap-1"
                      >
                        <CheckCircle size={12} /> Validar Pago
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pago Presencial Modal */}
      <Modal isOpen={!!presencialModal} onClose={() => setPresencialModal(null)} title="💵 Validar Pago Presencial (HU-20)">
        {presencialModal && (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-sm font-semibold text-green-800">Monto a cobrar: <strong>{formatCOP(presencialModal.monto)}</strong></p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Método de pago</label>
              <div className="grid grid-cols-3 gap-2">
                {(['EFECTIVO', 'BRE_B', 'WOMPI'] as const).map(m => (
                  <button
                    key={m}
                    onClick={() => setMetodo(m)}
                    className={`py-3 rounded-xl border-2 font-semibold text-xs sm:text-sm transition-colors ${
                      metodo === m ? 'border-green-500 bg-green-50 text-green-700' : 'border-gray-200 text-gray-600 hover:border-gray-300'
                    }`}
                  >
                    {m === 'EFECTIVO' ? '💵 Efectivo' : m === 'BRE_B' ? '🔑 Bre-B' : '🟢 Wompi'}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Observaciones (opcional)</label>
              <textarea value={observaciones} onChange={e => setObservaciones(e.target.value)}
                className="input-field" rows={2} placeholder="Número de comprobante, banco, etc." />
            </div>
            <div className="flex gap-3">
              <button onClick={() => setPresencialModal(null)} className="btn-secondary flex-1">Cancelar</button>
              <button onClick={() => registrarPresencial()} disabled={registrando} className="btn-primary flex-1 flex items-center justify-center gap-2">
                {registrando ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                Confirmar Pago
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
