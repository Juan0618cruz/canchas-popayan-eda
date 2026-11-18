/**
 * Capa MVC: Vista — VistaReportes.tsx (también exportado como VistaAdmin.tsx)
 * Monitor en tiempo real de eventos EDA (Event-Driven Architecture) y métricas de notificación.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw, Mail, Activity, ChevronDown, ChevronUp } from 'lucide-react'
import { notificacionesApi } from './lib/api'
import type { EmailLog } from './lib/types'
import Navbar from './components/Navbar'
import LoadingSpinner from './components/LoadingSpinner'

const EVENT_CONFIG: Record<string, { label: string; color: string; bg: string; emoji: string }> = {
  ReservaSolicitada:            { label: 'Reserva Solicitada',         color: 'text-blue-700',   bg: 'bg-blue-100',   emoji: '📋' },
  PagoAprobado:                 { label: 'Pago Aprobado',              color: 'text-green-700',  bg: 'bg-green-100',  emoji: '✅' },
  PagoRechazado:                { label: 'Pago Rechazado',             color: 'text-red-700',    bg: 'bg-red-100',    emoji: '❌' },
  PagoPresencialValidado:       { label: 'Pago Presencial Validado',   color: 'text-teal-700',   bg: 'bg-teal-100',   emoji: '💵' },
  ReservaCancelada:             { label: 'Reserva Cancelada',          color: 'text-gray-700',   bg: 'bg-gray-100',   emoji: '🚫' },
  ReservaReprogramada:          { label: 'Reserva Reprogramada',       color: 'text-purple-700', bg: 'bg-purple-100', emoji: '🔄' },
  ClaveRestablecimientoSolicitada: { label: 'Reset Contraseña',        color: 'text-orange-700', bg: 'bg-orange-100', emoji: '🔑' },
  CanchaActualizada:            { label: 'Cancha Actualizada',         color: 'text-indigo-700', bg: 'bg-indigo-100', emoji: '✏️' },
}

function getEventConfig(eventType: string) {
  return EVENT_CONFIG[eventType] ?? { label: eventType, color: 'text-gray-700', bg: 'bg-gray-100', emoji: '📨' }
}

function formatTimestamp(ts: string) {
  try {
    return new Intl.DateTimeFormat('es-CO', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).format(new Date(ts))
  } catch {
    return ts
  }
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  ENVIADO_SMTP: { label: 'SMTP Enviado', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  SIN_CREDENCIALES_SMTP: { label: 'Sin credenciales SMTP (BD)', cls: 'bg-amber-100 text-amber-800 border-amber-300' },
  ERROR_SMTP: { label: 'Error SMTP (BD)', cls: 'bg-red-100 text-red-800 border-red-300' },
  ENVIADO_SIMULADO: { label: 'Demo / Simulado', cls: 'bg-gray-100 text-gray-700 border-gray-300' },
}

function EmailCard({ email }: { email: EmailLog }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = getEventConfig(email?.event_type || '')
  const bodyText = email?.body ? String(email.body) : ''
  const deliveryBadge = STATUS_BADGE[email?.status] ?? {
    label: email?.status || 'Registrado',
    cls: 'bg-gray-100 text-gray-700 border-gray-300',
  }

  return (
    <div className={`rounded-xl border p-4 ${cfg.bg} border-opacity-50`} style={{ borderColor: 'currentColor' }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="text-2xl shrink-0">{cfg.emoji}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`badge ${cfg.bg} ${cfg.color} text-xs font-semibold`}>{cfg.label}</span>
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${deliveryBadge.cls}`}>
                {deliveryBadge.label}
              </span>
              <span className="text-xs text-gray-500">{formatTimestamp(email?.timestamp || '')}</span>
            </div>
            <div className="flex items-center gap-1 mt-1.5">
              <Mail size={12} className="text-gray-400 shrink-0" />
              <p className="text-sm text-gray-700 truncate">
                <strong>{email?.to_name || 'Usuario'}</strong> &lt;{email?.to_email || 'sin-correo'}&gt;
              </p>
            </div>
            <p className={`text-sm font-medium mt-0.5 ${cfg.color}`}>{email?.subject || 'Notificación'}</p>
            {email?.error_detail && (
              <p className="text-[11px] text-gray-600 mt-1 bg-white/70 border border-gray-200 rounded px-2 py-1">
                Detalle envío: {email.error_detail}
              </p>
            )}
            {!expanded && bodyText && (
              <p className="text-xs text-gray-500 mt-1 line-clamp-2">{bodyText.substring(0, 150)}...</p>
            )}
            {expanded && bodyText && (
              <pre className="text-xs text-gray-600 mt-2 bg-white/60 rounded-lg p-3 whitespace-pre-wrap font-sans border">
                {bodyText}
              </pre>
            )}
          </div>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-gray-400 hover:text-gray-600 shrink-0 p-1"
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>
    </div>
  )
}

export default function VistaReportes() {
  const [filterType, setFilterType] = useState('')

  const { data: rawLogs = [], isLoading: loadingLogs, refetch, isFetching } = useQuery({
    queryKey: ['eda-logs', filterType],
    queryFn: () => notificacionesApi.getLogs(filterType || undefined),
    refetchInterval: 3000,
  })

  const logs: EmailLog[] = Array.isArray(rawLogs) ? rawLogs : []

  const { data: stats } = useQuery({
    queryKey: ['eda-stats'],
    queryFn: notificacionesApi.getStats,
    refetchInterval: 3000,
  })

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <Navbar />

      {/* Header */}
      <div className="bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 border-b border-gray-700 px-6 py-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Activity size={24} className="text-green-400" />
                Reportes — Eventos & Notificaciones
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Panel en tiempo real de eventos RabbitMQ procesados · Actualiza cada 3 segundos
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isFetching ? 'bg-green-400 animate-pulse' : 'bg-green-500'}`} />
                <span className="text-xs text-gray-400">En vivo</span>
              </div>
              <button onClick={() => refetch()} className="border border-gray-600 text-gray-300 hover:text-white hover:border-gray-400 px-3 py-1.5 rounded-lg text-sm flex items-center gap-1 transition-colors">
                <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} /> Actualizar
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
            <div className="bg-gray-800 rounded-xl p-3 col-span-1 border border-gray-700 text-center">
              <p className="text-2xl font-bold text-white">{stats.total_correos}</p>
              <p className="text-xs text-gray-400 mt-0.5">Total Emails</p>
            </div>
            {Object.entries(stats.por_evento ?? {}).map(([tipo, count]) => {
              const cfg = getEventConfig(tipo)
              return (
                <button
                  key={tipo}
                  onClick={() => setFilterType(filterType === tipo ? '' : tipo)}
                  className={`rounded-xl p-3 border text-center transition-all ${
                    filterType === tipo
                      ? 'border-green-500 bg-green-900/40'
                      : 'border-gray-700 bg-gray-800 hover:border-gray-500'
                  }`}
                >
                  <p className="text-xl">{cfg.emoji}</p>
                  <p className="text-lg font-bold text-white">{count}</p>
                  <p className="text-[9px] text-gray-400 leading-tight">{cfg.label}</p>
                </button>
              )
            })}
          </div>
        )}

        {/* Saga flow explanation */}
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 mb-6">
          <h2 className="text-sm font-bold text-green-400 mb-3 flex items-center gap-2">
            🔄 Flujo Saga en Tiempo Real:
          </h2>
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-300">
            <span className="bg-blue-900/50 border border-blue-700 px-2 py-1 rounded">📋 ReservaSolicitada</span>
            <span className="text-gray-500">→</span>
            <span className="text-gray-400">ms_canchas bloquea slot</span>
            <span className="text-gray-500">→</span>
            <span className="bg-green-900/50 border border-green-700 px-2 py-1 rounded">✅ PagoAprobado</span>
            <span className="text-gray-500">→</span>
            <span className="text-gray-400">ms_reservas confirma · ms_canchas OCUPADO</span>
            <span className="text-gray-500 mx-2">|</span>
            <span className="bg-red-900/50 border border-red-700 px-2 py-1 rounded">❌ PagoRechazado</span>
            <span className="text-gray-500">→</span>
            <span className="text-gray-400">SAGA ROLLBACK: slot → LIBRE</span>
          </div>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-gray-400">Filtrar por tipo:</span>
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="bg-gray-800 border border-gray-600 text-white text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-500"
          >
            <option value="">Todos los eventos</option>
            {Object.entries(EVENT_CONFIG).map(([key, cfg]) => (
              <option key={key} value={key}>{cfg.emoji} {cfg.label}</option>
            ))}
          </select>
          {filterType && (
            <button onClick={() => setFilterType('')} className="text-xs text-gray-400 hover:text-white underline">
              Limpiar filtro
            </button>
          )}
          <span className="text-xs text-gray-500 ml-auto">{logs.length} notificaciones</span>
        </div>

        {/* Email logs */}
        {loadingLogs ? (
          <LoadingSpinner text="Cargando notificaciones..." />
        ) : logs.length === 0 ? (
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-16 text-center">
            <div className="text-5xl mb-4">📭</div>
            <p className="text-gray-400">No hay notificaciones aún.</p>
            <p className="text-xs text-gray-500 mt-1">Realiza una reserva o un pago para ver los eventos aquí.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {logs.map(log => (
              <EmailCard key={log.id} email={log} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export { VistaReportes as VistaAdmin }
