import { formatCOP, isSlotInPast } from '../lib/api'
import type { EstadoBloque } from '../lib/types'
import { DEFAULT_SLOT_BG, resolveMediaUrl, useAppearanceStore } from '../store/appearanceStore'

interface MiniCanchaSlotProps {
  horaInicio: string
  tarifa: number
  estado: EstadoBloque
  slotBgUrl?: string | null
  onClick?: () => void
  title?: string
  isAdmin?: boolean
  onAdminInspect?: () => void
  isPast?: boolean
  fecha?: string
}

export default function MiniCanchaSlot({
  horaInicio,
  tarifa,
  estado,
  slotBgUrl,
  onClick,
  title,
  isAdmin,
  onAdminInspect,
  isPast,
  fecha,
}: MiniCanchaSlotProps) {
  const storeSlotBg = useAppearanceStore((s) => s.fondoSlotUrl)
  const resolvedBg = resolveMediaUrl(slotBgUrl ?? storeSlotBg, DEFAULT_SLOT_BG)
  const horaLabel = horaInicio.substring(0, 5)
  const precioLabel = formatCOP(Number(tarifa)).replace('COP', '').trim()

  const isPastSlot = isPast ?? (fecha ? isSlotInPast(fecha, horaInicio) : false)

  const isLibre = estado === 'LIBRE'
  const isBloqueado = estado === 'BLOQUEADO_TEMPORAL'
  const isOcupado = estado === 'OCUPADO'
  const isMantenimiento = estado === 'MANTENIMIENTO'

  if (isMantenimiento) {
    return (
      <div
        className="mini-pitch-slot mini-pitch-mantenimiento"
        style={{ backgroundImage: `url("${resolvedBg}")` }}
        title={title || 'No disponible por mantenimiento'}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-rose-50/90 via-slate-100/85 to-red-50/90 backdrop-blur-[2px] pointer-events-none" />
        <span className="relative z-10 bg-slate-300/80 text-slate-700 px-2 py-0.5 rounded-md text-[9px] font-semibold leading-none shadow-sm">
          {horaLabel}
        </span>
        <span className="relative z-10 text-base font-bold text-rose-500 leading-none">—</span>
        <span className="relative z-10 bg-rose-100 text-rose-700 border border-rose-300/80 px-2 py-[1.5px] rounded-full text-[8.5px] font-bold leading-tight shadow-sm">
          Mantto.
        </span>
      </div>
    )
  }

  // 1. Horarios pasados: Ocultar por completo de la renderización en el DOM
  if (isPastSlot) {
    return null
  }

  // 2. Horarios ocupados o pendientes de pago
  if (isBloqueado || isOcupado) {
    if (isAdmin) {
      return (
        <button
          type="button"
          onClick={onAdminInspect}
          className="mini-pitch-slot mini-pitch-reservado ring-2 ring-emerald-400/90 hover:ring-emerald-300 hover:-translate-y-0.5 hover:scale-[1.03] hover:shadow-lg transition-all duration-200 cursor-pointer shadow-sm group"
          style={{ backgroundImage: `url("${resolvedBg}")` }}
          title={title || `[ADMIN] Clic para ver detalle y gestionar reserva de las ${horaLabel}`}
        >
          <div className="absolute inset-0 bg-gradient-to-b from-amber-600/80 via-amber-700/85 to-yellow-800/90 group-hover:from-amber-500/80 group-hover:to-yellow-700/85 transition-colors pointer-events-none" />
          <span className="relative z-10 bg-black/50 backdrop-blur-sm text-amber-100 px-2 py-0.5 rounded-md text-[9.5px] font-semibold leading-none shadow-sm">
            {horaLabel}
          </span>
          <span className="relative z-10 text-[10px] font-extrabold text-amber-200 leading-none drop-shadow flex items-center justify-center gap-0.5">
            🔍 Admin
          </span>
          <span className="relative z-10 bg-emerald-600/95 group-hover:bg-emerald-500 text-white border border-emerald-300/50 px-2 py-[1.5px] rounded-full text-[8.5px] font-bold leading-tight shadow-md transition-colors">
            {isBloqueado ? 'Pendiente' : 'Reservado'}
          </span>
        </button>
      )
    }

    return (
      <div
        className="mini-pitch-slot mini-pitch-reservado hover:shadow-md transition-all duration-200"
        style={{ backgroundImage: `url("${resolvedBg}")` }}
        title={title || (isBloqueado ? 'Reserva en proceso de pago' : 'Horario ya reservado')}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-amber-600/75 via-amber-700/80 to-amber-900/85 pointer-events-none" />
        <span className="relative z-10 bg-black/40 backdrop-blur-sm text-amber-100 px-2 py-0.5 rounded-md text-[9.5px] font-semibold leading-none shadow-sm">
          {horaLabel}
        </span>
        <span className="relative z-10 text-sm leading-none drop-shadow-md">
          {isBloqueado ? '⏳' : '🔒'}
        </span>
        <span className="relative z-10 bg-amber-950/70 backdrop-blur-sm text-amber-200 border border-amber-400/30 px-2 py-[1.5px] rounded-full text-[8.5px] font-bold leading-tight shadow-sm">
          {isBloqueado ? 'Pendiente' : 'Reservado'}
        </span>
      </div>
    )
  }

  // 3. LIBRE: Mini cancha sintética verde vibrante, moderno y con alto impacto visual para reservas
  return (
    <button
      type="button"
      onClick={onClick}
      className="mini-pitch-slot mini-pitch-libre group relative"
      style={{ backgroundImage: `url("${resolvedBg}")` }}
      title={title || `Reservar ${horaLabel} - ${precioLabel}`}
    >
      <div className="absolute inset-0 bg-gradient-to-b from-emerald-950/25 via-emerald-900/10 to-emerald-950/45 group-hover:from-emerald-900/15 group-hover:to-emerald-950/35 transition-colors pointer-events-none" />
      <span className="relative z-10 bg-black/60 backdrop-blur-md text-white px-2 py-0.5 rounded-md text-[9.5px] font-bold tracking-tight leading-none shadow-sm border border-white/20 group-hover:border-emerald-300/70 transition-colors">
        {horaLabel}
      </span>
      <span className="relative z-10 font-extrabold text-[11.5px] text-white pitch-text-shadow leading-none tracking-tight drop-shadow-md group-hover:scale-105 transition-transform">
        {precioLabel}
      </span>
      <span className="relative z-10 bg-emerald-500 group-hover:bg-emerald-400 text-white font-black text-[8.5px] px-2.5 py-[2px] rounded-full shadow-md shadow-emerald-950/40 leading-tight transition-all group-hover:shadow-emerald-500/50 tracking-wide uppercase">
        Libre
      </span>
    </button>
  )
}
