import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  buscarDisponibilidad,
  canchasApi,
  extractErrorMessage,
  isSlotInPast,
  renderizarDisponibilidad,
  reservasApi,
} from '../lib/api'
import type { BloqueHorarioDto, CanchaDto, ComplejoDto, ReservaDto, TipoCancha } from '../lib/types'
import { useAuthStore } from '../store/authStore'
import { DEFAULT_GENERAL_BG, resolveMediaUrl, useAppearanceStore } from '../store/appearanceStore'

export const CATALOG_HOURS = Array.from({ length: 14 }, (_, i) => `${String(i + 8).padStart(2, '0')}:00`)

export interface SlotMap {
  [canchaId: string]: BloqueHorarioDto[]
}

export interface ReservaModalData {
  cancha: CanchaDto
  complejo: ComplejoDto
  bloque: BloqueHorarioDto
}

export function getTodayIso(): string {
  return new Date().toISOString().split('T')[0]
}

export function getCanchaSlots(
  cancha: CanchaDto,
  rawSlots?: BloqueHorarioDto[],
  targetFecha?: string
): BloqueHorarioDto[] {
  const safeList = renderizarDisponibilidad(rawSlots)
  if (safeList.length > 0) {
    return safeList
  }
  const fechaActual = targetFecha || getTodayIso()
  return CATALOG_HOURS.map(h => ({
    id: `virtual-${cancha.id}-${h}`,
    cancha_id: cancha.id,
    fecha: fechaActual,
    hora_inicio: `${h}:00`,
    hora_fin: `${String(Number(h.split(':')[0]) + 1).padStart(2, '0')}:00:00`,
    estado: 'LIBRE' as const,
    reserva_id: undefined,
  }))
}

export function useCatalogoController() {
  const navigate = useNavigate()
  const { isAuthenticated, user } = useAuthStore()
  const { fondoGeneralUrl } = useAppearanceStore()
  const queryClient = useQueryClient()

  const [fecha, setFecha] = useState(getTodayIso())
  const [horaFiltro, setHoraFiltro] = useState('')
  const [tipoFiltro, setTipoFiltro] = useState<TipoCancha | ''>('')
  const [reservaModal, setReservaModal] = useState<ReservaModalData | null>(null)
  const [pagoModal, setPagoModal] = useState<ReservaDto | null>(null)
  const [slotMap, setSlotMap] = useState<SlotMap>({})
  const [loadingSlots, setLoadingSlots] = useState(false)

  const { data: complejos = [], isLoading, error } = useQuery({
    queryKey: ['complejos'],
    queryFn: canchasApi.getComplejos,
  })

  const cargarDisponibilidadCanchas = useCallback(async (canchasList: CanchaDto[], fechaConsulta: string) => {
    if (!canchasList || canchasList.length === 0) return
    setLoadingSlots(true)
    const newMap: SlotMap = {}

    await Promise.all(
      canchasList.map(async (cancha) => {
        try {
          const slots = await buscarDisponibilidad(cancha.id, fechaConsulta)
          const valid = renderizarDisponibilidad(slots)
          newMap[cancha.id] = valid.length > 0 ? valid : getCanchaSlots(cancha, [], fechaConsulta)
        } catch {
          newMap[cancha.id] = getCanchaSlots(cancha, [], fechaConsulta)
        }
      })
    )

    setSlotMap(prev => ({ ...prev, ...newMap }))
    setLoadingSlots(false)
  }, [])

  useEffect(() => {
    let activo = true

    async function inicializarCatalogo() {
      try {
        let listaComplejos = complejos
        if (!listaComplejos || listaComplejos.length === 0) {
          listaComplejos = await canchasApi.getComplejos()
        }
        if (!activo) return

        const allCanchas = (Array.isArray(listaComplejos) ? listaComplejos : [])
          .flatMap(c => (Array.isArray(c?.canchas) ? c.canchas : []))

        if (allCanchas.length > 0) {
          setSlotMap(prev => {
            const inicial: SlotMap = { ...prev }
            allCanchas.forEach(cancha => {
              if (!inicial[cancha.id] || inicial[cancha.id].length === 0) {
                inicial[cancha.id] = getCanchaSlots(cancha, [], fecha)
              }
            })
            return inicial
          })
          await cargarDisponibilidadCanchas(allCanchas, fecha)
        }
      } catch (err) {
        console.warn('Error en inicialización automática de disponibilidad:', err)
      }
    }

    inicializarCatalogo()
    return () => {
      activo = false
    }
  }, [fecha, complejos, cargarDisponibilidadCanchas])

  const { mutate: crearReserva, isPending: creandoReserva } = useMutation({
    mutationFn: (data: Parameters<typeof reservasApi.crear>[0]) => reservasApi.crear(data),
    onSuccess: (reservaCreada) => {
      setReservaModal(null)
      setPagoModal(reservaCreada)
      queryClient.invalidateQueries({ queryKey: ['complejos'] })
      const allCanchas = (Array.isArray(complejos) ? complejos : [])
        .flatMap(c => (Array.isArray(c?.canchas) ? c.canchas : []))
      cargarDisponibilidadCanchas(allCanchas, fecha)
    },
    onError: (err: unknown) => {
      alert('❌ ' + extractErrorMessage(err, 'Error al crear la reserva.'))
    },
  })

  const handleBlockClick = (cancha: CanchaDto, complejo: ComplejoDto, bloque: BloqueHorarioDto) => {
    if (bloque.estado !== 'LIBRE') return
    if (isSlotInPast(bloque.fecha, bloque.hora_inicio)) {
      alert('⚠️ No se pueden realizar reservas en horarios pasados.')
      return
    }
    if (!isAuthenticated) {
      navigate('/login')
      return
    }
    setReservaModal({ cancha, complejo, bloque })
  }

  const handleConfirmReserva = () => {
    if (!reservaModal) return
    const { cancha, complejo, bloque } = reservaModal
    crearReserva({
      cancha_id: cancha.id,
      complejo_id: complejo.id,
      fecha: bloque.fecha,
      hora_inicio: bloque.hora_inicio,
      hora_fin: bloque.hora_fin,
      monto: Number(cancha.tarifa_por_hora),
      nombre_cliente: user?.nombre,
      cliente_nombre: user?.nombre,
      cliente_email: user?.email,
      telefono_cliente: user?.telefono ?? undefined,
    })
  }

  const filteredComplejos = useMemo(
    () =>
      complejos
        .map(complejo => ({
          ...complejo,
          canchas: complejo.canchas.filter(c => {
            if (!c.activo) return false
            if (tipoFiltro && c.tipo !== tipoFiltro) return false
            return true
          }),
        }))
        .filter(c => c.canchas.length > 0),
    [complejos, tipoFiltro]
  )

  const resolvedGeneralBg = resolveMediaUrl(fondoGeneralUrl, DEFAULT_GENERAL_BG)

  return {
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
  }
}
