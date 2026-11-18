import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { canchasApi, extractErrorMessage, reservasApi } from '../lib/api'
import type { BloqueHorarioDto, ReservaDto } from '../lib/types'
import { DEFAULT_GENERAL_BG, resolveMediaUrl, useAppearanceStore } from '../store/appearanceStore'

export const RESERVA_HOURS = Array.from({ length: 14 }, (_, i) => `${String(i + 8).padStart(2, '0')}:00`)

export function normalizeEstado(estado?: string | null): string {
  return String(estado ?? '').trim().toUpperCase()
}

export function isReservaActiva(r: ReservaDto): boolean {
  const estado = normalizeEstado(r.estado)
  if (!estado) return false
  if (
    estado.startsWith('CANCEL') ||
    estado === 'FINALIZADA' ||
    estado === 'COMPLETADA' ||
    estado === 'RECHAZADA'
  ) {
    return false
  }
  return ['CONFIRMADA', 'PENDIENTE', 'PENDIENTE_PAGO', 'CONFIRMADA_PRESENCIAL'].includes(estado)
}

export function getTodayColombia(): string {
  return new Date(Date.now() - 5 * 3600000).toISOString().split('T')[0]
}

export function useMisReservasController() {
  const queryClient = useQueryClient()
  const { fondoGeneralUrl } = useAppearanceStore()
  const resolvedGeneralBg = resolveMediaUrl(fondoGeneralUrl, DEFAULT_GENERAL_BG)

  const [cancelModal, setCancelModal] = useState<ReservaDto | null>(null)
  const [cancelError, setCancelError] = useState('')
  const [reprogramarModal, setReprogramarModal] = useState<ReservaDto | null>(null)
  const [nuevaFecha, setNuevaFecha] = useState('')
  const [nuevaHora, setNuevaHora] = useState('')
  const [reprogramarError, setReprogramarError] = useState('')
  const [feedback, setFeedback] = useState('')

  const { data: reservas = [], isLoading } = useQuery({
    queryKey: ['mis-reservas'],
    queryFn: reservasApi.misReservas,
  })

  const { data: complejos = [] } = useQuery({
    queryKey: ['complejos-public'],
    queryFn: canchasApi.getComplejos,
  })

  const canchaNameById = useMemo(() => {
    const map: Record<string, string> = {}
    for (const comp of complejos) {
      for (const c of comp.canchas ?? []) {
        map[c.id] = `${c.nombre} (${comp.nombre})`
      }
    }
    return map
  }, [complejos])

  const { data: disponibilidad = [], isFetching: cargandoDisponibilidad } = useQuery({
    queryKey: ['disponibilidad-reagendar', reprogramarModal?.cancha_id, nuevaFecha],
    queryFn: () => canchasApi.getDisponibilidad(reprogramarModal!.cancha_id, nuevaFecha),
    enabled: Boolean(reprogramarModal?.cancha_id && nuevaFecha),
  })

  const slotByHour = useMemo(() => {
    const map: Record<string, BloqueHorarioDto> = {}
    for (const s of disponibilidad) {
      map[String(s.hora_inicio).substring(0, 5)] = s
    }
    return map
  }, [disponibilidad])

  const openReprogramarModal = (reserva: ReservaDto) => {
    setReprogramarError('')
    setNuevaFecha(reserva.fecha)
    setNuevaHora('')
    setReprogramarModal(reserva)
  }

  const { mutate: cancelar, isPending: cancelando } = useMutation({
    mutationFn: (id: string) => reservasApi.cancelar(id),
    onSuccess: () => {
      setCancelModal(null)
      setCancelError('')
      setFeedback('Reserva cancelada correctamente.')
      queryClient.invalidateQueries({ queryKey: ['mis-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['disponibilidad'] })
    },
    onError: (err: unknown) => setCancelError(extractErrorMessage(err, 'No se pudo cancelar la reserva.')),
  })

  const { mutate: reprogramar, isPending: reprogramando } = useMutation({
    mutationFn: ({ id, nuevaFecha: targetFecha, nuevaHora: targetHora }: { id: string; nuevaFecha: string; nuevaHora: string }) =>
      reservasApi.reprogramar(id, {
        nueva_fecha: targetFecha,
        nueva_hora_inicio: `${targetHora}:00`,
        nueva_hora_fin: `${String(Number(targetHora.split(':')[0]) + 1).padStart(2, '0')}:00:00`,
      }),
    onSuccess: (updated) => {
      setReprogramarModal(null)
      setReprogramarError('')
      setFeedback(`Reserva ${updated.codigo_uid} reagendada para el ${updated.fecha} a las ${updated.hora_inicio.substring(0, 5)}.`)
      queryClient.invalidateQueries({ queryKey: ['mis-reservas'] })
      queryClient.invalidateQueries({ queryKey: ['disponibilidad'] })
      queryClient.invalidateQueries({ queryKey: ['disponibilidad-reagendar'] })
    },
    onError: (err: unknown) => setReprogramarError(extractErrorMessage(err, 'No se pudo reagendar la reserva en ese horario.')),
  })

  return {
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
    todayColombia: getTodayColombia(),
  }
}
