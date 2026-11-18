import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  CheckCircle,
  CreditCard,
  ExternalLink,
  Landmark,
  Loader2,
  Lock,
  Smartphone,
  XCircle,
} from 'lucide-react'
import Modal from './Modal'
import { extractErrorMessage, formatCOP, pagosApi } from '../lib/api'
import type { MetodoPago, ReservaDto, WompiPrepararResponse } from '../lib/types'
import { useAuthStore } from '../store/authStore'

interface PagoModalProps {
  isOpen: boolean
  onClose: () => void
  reserva: ReservaDto
}

type WompiMetodo = 'WOMPI_NEQUI' | 'WOMPI_PSE' | 'WOMPI_BANCOLOMBIA' | 'WOMPI_CARD'
type ResultadoPago = 'APPROVED' | 'DECLINED' | null

const PSE_BANCOS = [
  'Bancolombia',
  'Nequi',
  'Davivienda',
  'Banco de Bogotá',
  'BBVA Colombia',
  'Banco Agrario',
  'Nu Colombia',
  'Scotiabank Colpatria',
]

const WOMPI_PAYMENT_METHODS: Array<{
  id: WompiMetodo
  label: string
  subtitle: string
  icon: typeof Smartphone
}> = [
  { id: 'WOMPI_NEQUI', label: 'Nequi', subtitle: 'Celular', icon: Smartphone },
  { id: 'WOMPI_PSE', label: 'PSE', subtitle: 'Bancos CO', icon: Building2 },
  { id: 'WOMPI_BANCOLOMBIA', label: 'Bancolombia', subtitle: 'Botón', icon: Landmark },
  { id: 'WOMPI_CARD', label: 'Tarjeta', subtitle: 'Débito/Crédito', icon: CreditCard },
]

function buildLocalReference(codigoUid?: string): string {
  const randomSuffix = Math.random().toString(16).slice(2, 8).toUpperCase()
  const cleanCode = (codigoUid || 'POP').replace(/[^A-Z0-9]/gi, '').slice(-4).toUpperCase()
  return `WOMPI-POP-${cleanCode}-${randomSuffix}`
}

function mapWidgetMethodType(methodType?: string): MetodoPago {
  const normalized = (methodType || '').toUpperCase()
  if (normalized.includes('NEQUI')) return 'WOMPI_NEQUI'
  if (normalized.includes('PSE')) return 'WOMPI_PSE'
  if (normalized.includes('BANCOLOMBIA')) return 'WOMPI_BANCOLOMBIA'
  return 'WOMPI_CARD'
}

function loadWompiWidgetScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.WidgetCheckout) {
      resolve(true)
      return
    }
    const existing = document.querySelector<HTMLScriptElement>('script[src="https://checkout.wompi.co/widget.js"]')
    if (existing) {
      existing.addEventListener('load', () => resolve(Boolean(window.WidgetCheckout)), { once: true })
      existing.addEventListener('error', () => resolve(false), { once: true })
      return
    }
    const script = document.createElement('script')
    script.src = 'https://checkout.wompi.co/widget.js'
    script.async = true
    script.onload = () => resolve(Boolean(window.WidgetCheckout))
    script.onerror = () => resolve(false)
    document.body.appendChild(script)
  })
}

export default function PagoModal({ isOpen, onClose, reserva }: PagoModalProps) {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()

  const [metodoTab, setMetodoTab] = useState<WompiMetodo>('WOMPI_NEQUI')
  const [referencia, setReferencia] = useState<string>(() => buildLocalReference(reserva.codigo_uid))
  const [wompiPrep, setWompiPrep] = useState<WompiPrepararResponse | null>(null)
  const [resultado, setResultado] = useState<ResultadoPago>(null)
  const [pagoData, setPagoData] = useState<{ referencia?: string; estado?: string; metodo?: string } | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [widgetLoading, setWidgetLoading] = useState(false)

  // Interactive Sandbox fields for Colombian Wompi methods
  const [nequiCelular, setNequiCelular] = useState('3001234567')
  const [pseBanco, setPseBanco] = useState('Bancolombia')
  const [psePersona, setPsePersona] = useState<'Natural' | 'Jurídica'>('Natural')
  const [pseDocumento, setPseDocumento] = useState('1061745890')
  const [bancolombiaUsuario, setBancolombiaUsuario] = useState('deportista.popayan')
  const [cardNumber, setCardNumber] = useState('4242 4242 4242 4242')
  const [cardHolder, setCardHolder] = useState(user?.nombre ?? 'Carlos Gómez')
  const [cardExpiry, setCardExpiry] = useState('12/28')
  const [cardCvv, setCardCvv] = useState('123')
  const [cardCuotas, setCardCuotas] = useState('1')

  useEffect(() => {
    if (!isOpen || !reserva?.id) return
    const fallbackRef = buildLocalReference(reserva.codigo_uid)
    setReferencia(fallbackRef)
    setResultado(null)
    setPagoData(null)
    setErrorMsg('')

    pagosApi
      .prepararWompi({
        reserva_id: reserva.id,
        monto: Number(reserva.monto),
        referencia_externa: fallbackRef,
      })
      .then((prep) => {
        setWompiPrep(prep)
        if (prep.referencia_externa) setReferencia(prep.referencia_externa)
      })
      .catch(() => {
        setWompiPrep(null)
      })
  }, [isOpen, reserva.id, reserva.codigo_uid, reserva.monto])

  const invalidateCaches = () => {
    queryClient.invalidateQueries({ queryKey: ['disponibilidad'] })
    queryClient.invalidateQueries({ queryKey: ['complejos'] })
    queryClient.invalidateQueries({ queryKey: ['mis-reservas'] })
    queryClient.invalidateQueries({ queryKey: ['admin-pagos'] })
    queryClient.invalidateQueries({ queryKey: ['admin-reservas'] })
    queryClient.invalidateQueries({ queryKey: ['eda-logs'] })
  }

  const { mutate: confirmarPagoWompi, isPending } = useMutation({
    mutationFn: ({
      statusOutcome,
      metodo,
      transactionId,
      observaciones,
    }: {
      statusOutcome: 'APPROVED' | 'DECLINED'
      metodo: MetodoPago
      transactionId?: string
      observaciones?: string
    }) =>
      pagosApi.wompiWebhook({
        reference: referencia,
        status: statusOutcome,
        metodo_pago: metodo,
        reserva_id: reserva.id,
        usuario_id: user?.id,
        complejo_id: reserva.complejo_id,
        monto: Number(reserva.monto),
        transaction_id: transactionId ?? `tx-${Date.now()}`,
        customer_email: user?.email,
        observaciones,
      }),
    onSuccess: (data, vars) => {
      setErrorMsg('')
      setResultado(vars.statusOutcome)
      setPagoData({
        referencia: data.referencia_externa ?? referencia,
        estado: data.estado,
        metodo: data.metodo,
      })
      invalidateCaches()
    },
    onError: (err: unknown) => {
      setErrorMsg(extractErrorMessage(err, 'No se pudo procesar el pago con Wompi.'))
    },
  })

  const buildSandboxObservations = (): string => {
    switch (metodoTab) {
      case 'WOMPI_NEQUI':
        return `Wompi Sandbox · Nequi Cel: ${nequiCelular.trim() || '3001234567'}`
      case 'WOMPI_PSE':
        return `Wompi Sandbox · PSE ${pseBanco} (${psePersona}) Doc: ${pseDocumento}`
      case 'WOMPI_BANCOLOMBIA':
        return `Wompi Sandbox · Botón Bancolombia (${bancolombiaUsuario})`
      case 'WOMPI_CARD':
        return `Wompi Sandbox · Tarjeta ****${cardNumber.replace(/\s+/g, '').slice(-4)} (${cardCuotas} cuota/s)`
    }
  }

  const handleSandboxSubmit = (statusOutcome: 'APPROVED' | 'DECLINED') => {
    setErrorMsg('')
    if (statusOutcome === 'APPROVED') {
      if (metodoTab === 'WOMPI_NEQUI' && nequiCelular.replace(/\D/g, '').length < 10) {
        setErrorMsg('Ingresa un número celular Nequi válido de 10 dígitos (ej: 3001234567).')
        return
      }
      if (metodoTab === 'WOMPI_PSE' && !pseDocumento.trim()) {
        setErrorMsg('Ingresa tu número de documento para continuar por PSE.')
        return
      }
      if (metodoTab === 'WOMPI_CARD' && cardNumber.replace(/\D/g, '').length < 12) {
        setErrorMsg('Ingresa un número de tarjeta válido para continuar.')
        return
      }
    }

    confirmarPagoWompi({
      statusOutcome,
      metodo: metodoTab,
      observaciones: buildSandboxObservations(),
    })
  }

  const effectivePublicKey = (import.meta.env.VITE_WOMPI_PUBLIC_KEY || wompiPrep?.public_key || '').trim()

  const handleOpenOfficialWidget = async () => {
    if (!effectivePublicKey) return
    setErrorMsg('')
    setWidgetLoading(true)
    const loaded = await loadWompiWidgetScript()
    setWidgetLoading(false)

    if (!loaded || !window.WidgetCheckout) {
      setErrorMsg('No fue posible cargar el script oficial de Wompi (widget.js). Usa el modo Sandbox integrado.')
      return
    }

    const checkout = new window.WidgetCheckout({
      currency: 'COP',
      amountInCents: wompiPrep?.amount_in_cents ?? Math.round(Number(reserva.monto) * 100),
      reference: referencia,
      publicKey: effectivePublicKey,
      ...(wompiPrep?.integrity_signature
        ? { signature: { integrity: wompiPrep.integrity_signature } }
        : {}),
      customerData: {
        email: user?.email,
        fullName: user?.nombre,
      },
    })

    checkout.open((result) => {
      const tx = result?.transaction
      if (!tx) return
      const approved = String(tx.status).toUpperCase() === 'APPROVED'
      confirmarPagoWompi({
        statusOutcome: approved ? 'APPROVED' : 'DECLINED',
        metodo: mapWidgetMethodType(tx.paymentMethodType),
        transactionId: tx.id,
        observaciones: `Wompi Widget Oficial · Estado ${tx.status}`,
      })
    })
  }

  const handleClose = () => {
    setResultado(null)
    setPagoData(null)
    setErrorMsg('')
    onClose()
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Checkout Wompi Colombia" size="lg">
      {/* Identidad Wompi Colombia */}
      <div className="bg-[#1A1F71] text-white rounded-xl p-4 mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="bg-[#00C389] text-[#1A1F71] font-black text-lg px-3 py-1 rounded-lg tracking-tight">
            wompi
          </div>
          <div>
            <p className="font-bold text-sm leading-tight">Wompi Colombia · Grupo Bancolombia</p>
            <p className="text-[11px] text-indigo-200 flex items-center gap-1 mt-0.5">
              <Lock size={11} /> Ref: <span className="font-mono text-white font-semibold">{referencia}</span>
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-indigo-200 uppercase">Total a pagar</p>
          <p className="text-2xl font-extrabold text-[#00C389]">{formatCOP(Number(reserva.monto))}</p>
        </div>
      </div>

      {/* Resumen de reserva */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 mb-4 flex items-center justify-between flex-wrap gap-2 text-sm">
        <div>
          <span className="font-bold text-emerald-900">{reserva.codigo_uid}</span>
          <span className="text-emerald-700 ml-2">
            {reserva.fecha} · {reserva.hora_inicio.substring(0, 5)} – {reserva.hora_fin.substring(0, 5)}
          </span>
        </div>
        <span className="badge bg-amber-100 text-amber-800 text-xs">
          {resultado === 'APPROVED' ? 'CONFIRMADA' : resultado === 'DECLINED' ? 'CANCELADA' : 'PENDIENTE PAGO'}
        </span>
      </div>

      {/* Resultado */}
      {resultado ? (
        <div
          className={`rounded-xl p-6 text-center ${
            resultado === 'APPROVED'
              ? 'bg-green-50 border border-green-300'
              : 'bg-red-50 border border-red-300'
          }`}
        >
          {resultado === 'APPROVED' ? (
            <>
              <CheckCircle size={52} className="mx-auto text-green-600 mb-3" />
              <h3 className="text-xl font-bold text-green-800">¡Pago Aprobado por Wompi!</h3>
              <p className="text-green-700 text-sm mt-1">
                Tu reserva quedó <strong>CONFIRMADA</strong> y enviamos la notificación a <strong>{user?.email}</strong>.
              </p>
              <div className="mt-3 flex flex-wrap items-center justify-center gap-2 text-xs">
                <span className="font-mono bg-green-100 text-green-800 px-3 py-1 rounded-md">
                  Ref: {pagoData?.referencia ?? referencia}
                </span>
                <span className="bg-green-100 text-green-800 px-3 py-1 rounded-md font-semibold">
                  Método: {pagoData?.metodo ?? metodoTab}
                </span>
              </div>
            </>
          ) : (
            <>
              <XCircle size={52} className="mx-auto text-red-600 mb-3" />
              <h3 className="text-xl font-bold text-red-800">Pago Declinado por Wompi</h3>
              <p className="text-red-700 text-sm mt-1">
                La transacción fue rechazada y el horario ha sido liberado nuevamente.
              </p>
            </>
          )}
          <button onClick={handleClose} className="btn-primary mt-5 w-full">
            Cerrar
          </button>
        </div>
      ) : (
        <>
          {/* Widget oficial Wompi si VITE_WOMPI_PUBLIC_KEY está configurada */}
          {effectivePublicKey && (
            <div className="mb-4 bg-indigo-50 border border-indigo-200 rounded-xl p-3 flex items-center justify-between gap-3">
              <div className="text-xs text-indigo-900">
                <p className="font-bold">Widget Oficial Wompi Activo</p>
                <p className="text-indigo-700">Llave pública detectada · Checkout oficial `widget.js`</p>
              </div>
              <button
                type="button"
                onClick={handleOpenOfficialWidget}
                disabled={widgetLoading || isPending}
                className="bg-[#1A1F71] hover:bg-[#13175a] text-white text-xs font-semibold px-3.5 py-2 rounded-lg flex items-center gap-1.5 shrink-0"
              >
                {widgetLoading ? <Loader2 size={14} className="animate-spin" /> : <ExternalLink size={14} />}
                Abrir Widget Wompi
              </button>
            </div>
          )}

          {/* Métodos locales Wompi */}
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Elige tu medio de pago en Wompi Colombia
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            {WOMPI_PAYMENT_METHODS.map(({ id, label, subtitle, icon: Icon }) => {
              const active = metodoTab === id
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => {
                    setMetodoTab(id)
                    setErrorMsg('')
                  }}
                  className={`p-3 rounded-xl border-2 text-left transition-all ${
                    active
                      ? 'border-[#00C389] bg-emerald-50/70 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-gray-300'
                  }`}
                >
                  <Icon size={18} className={active ? 'text-[#1A1F71]' : 'text-gray-500'} />
                  <p className="font-bold text-sm text-gray-900 mt-1.5">{label}</p>
                  <p className="text-[11px] text-gray-500">{subtitle}</p>
                </button>
              )
            })}
          </div>

          {/* Formulario interactivo por método (Sandbox Integrado) */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-4 space-y-3">
            {metodoTab === 'WOMPI_NEQUI' && (
              <>
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-sm text-gray-800">Pago rápido con Nequi</p>
                  <span className="text-[11px] bg-pink-100 text-pink-800 font-semibold px-2 py-0.5 rounded-full">
                    Notificación Push
                  </span>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Número celular Nequi (10 dígitos)
                  </label>
                  <input
                    type="tel"
                    maxLength={10}
                    value={nequiCelular}
                    onChange={(e) => setNequiCelular(e.target.value)}
                    className="input-field font-mono"
                    placeholder="3001234567"
                  />
                </div>
                <p className="text-xs text-gray-500">
                  Recibirás una notificación push en tu app Nequi para aprobar el cobro por {formatCOP(Number(reserva.monto))}.
                </p>
              </>
            )}

            {metodoTab === 'WOMPI_PSE' && (
              <>
                <p className="font-semibold text-sm text-gray-800">PSE — Transferencia Bancaria Colombia</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Banco</label>
                    <select
                      value={pseBanco}
                      onChange={(e) => setPseBanco(e.target.value)}
                      className="input-field"
                    >
                      {PSE_BANCOS.map((banco) => (
                        <option key={banco} value={banco}>
                          {banco}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Tipo de persona</label>
                    <select
                      value={psePersona}
                      onChange={(e) => setPsePersona(e.target.value as 'Natural' | 'Jurídica')}
                      className="input-field"
                    >
                      <option value="Natural">Persona Natural</option>
                      <option value="Jurídica">Persona Jurídica</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Número de documento (CC / NIT)</label>
                  <input
                    type="text"
                    value={pseDocumento}
                    onChange={(e) => setPseDocumento(e.target.value)}
                    className="input-field font-mono"
                    placeholder="1061745890"
                  />
                </div>
              </>
            )}

            {metodoTab === 'WOMPI_BANCOLOMBIA' && (
              <>
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-sm text-gray-800">Botón Bancolombia</p>
                  <span className="text-[11px] bg-yellow-100 text-yellow-900 font-semibold px-2 py-0.5 rounded-full">
                    Transferencia Directa
                  </span>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Usuario Sucursal Virtual Personas (Sandbox)
                  </label>
                  <input
                    type="text"
                    value={bancolombiaUsuario}
                    onChange={(e) => setBancolombiaUsuario(e.target.value)}
                    className="input-field"
                    placeholder="usuario.bancolombia"
                  />
                </div>
                <p className="text-xs text-gray-500">
                  Autoriza el pago directo desde tu cuenta de ahorros o corriente Bancolombia sin salir de la plataforma.
                </p>
              </>
            )}

            {metodoTab === 'WOMPI_CARD' && (
              <>
                <p className="font-semibold text-sm text-gray-800">Tarjeta Débito / Crédito (Visa · Mastercard)</p>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Número de tarjeta</label>
                  <input
                    type="text"
                    value={cardNumber}
                    onChange={(e) => setCardNumber(e.target.value)}
                    className="input-field font-mono"
                    placeholder="4242 4242 4242 4242"
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-1">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Vencimiento</label>
                    <input
                      type="text"
                      value={cardExpiry}
                      onChange={(e) => setCardExpiry(e.target.value)}
                      className="input-field font-mono"
                      placeholder="12/28"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">CVV</label>
                    <input
                      type="password"
                      maxLength={4}
                      value={cardCvv}
                      onChange={(e) => setCardCvv(e.target.value)}
                      className="input-field font-mono"
                      placeholder="123"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Cuotas</label>
                    <select
                      value={cardCuotas}
                      onChange={(e) => setCardCuotas(e.target.value)}
                      className="input-field"
                    >
                      {['1', '3', '6', '12'].map((c) => (
                        <option key={c} value={c}>
                          {c} {c === '1' ? 'cuota' : 'cuotas'}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Titular de la tarjeta</label>
                  <input
                    type="text"
                    value={cardHolder}
                    onChange={(e) => setCardHolder(e.target.value)}
                    className="input-field"
                    placeholder="Nombre como aparece en la tarjeta"
                  />
                </div>
              </>
            )}
          </div>

          {errorMsg && (
            <div className="mb-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg px-3 py-2">
              {errorMsg}
            </div>
          )}

          {/* Botones de acción Sandbox / Confirmación */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
            <div className="flex items-center justify-between text-xs text-slate-600 mb-2.5">
              <span className="font-semibold">🧪 Modo Sandbox Interactivo Wompi</span>
              <span>Callback directo a `/pagos/wompi/webhook`</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleSandboxSubmit('APPROVED')}
                disabled={isPending}
                className="bg-[#00C389] hover:bg-[#00aa77] text-[#1A1F71] font-bold py-3 px-4 rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {isPending ? <Loader2 size={18} className="animate-spin" /> : <CheckCircle size={18} />}
                Pagar con Wompi (APPROVED)
              </button>
              <button
                type="button"
                onClick={() => handleSandboxSubmit('DECLINED')}
                disabled={isPending}
                className="bg-red-600 hover:bg-red-700 text-white font-semibold py-3 px-4 rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {isPending ? <Loader2 size={18} className="animate-spin" /> : <XCircle size={18} />}
                Simular Declinado (DECLINED)
              </button>
            </div>
          </div>
        </>
      )}
    </Modal>
  )
}
