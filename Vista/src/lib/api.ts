import axios from 'axios'
import { useAuthStore } from '../store/authStore'
import type {
  AparienciaConfigDto, BloqueHorarioDto, BloqueoMantenimientoDto, CanchaDto, ComplejoDto, EmailLog,
  EmailLogsPayload, EstadoPago, EventStats, ForgotPasswordResponse, LoginResponse, MetodoPago, PagoDto,
  ReservaDto, TipoCancha, User, WompiPrepararResponse
} from './types'

const getApiBase = (): string => {
  if (typeof window !== 'undefined' && window.location) {
    const { hostname, protocol } = window.location
    if (hostname && hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return `${protocol}//${hostname}:8000`
    }
  }
  return 'http://localhost:8000'
}

export const API_BASE = getApiBase()

export const api = axios.create({ baseURL: API_BASE })

// Request interceptor: attach JWT
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Response interceptor: on 401, logout
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { email, password }).then(r => r.data),

  register: (data: { nombre: string; email: string; password: string; telefono: string }) =>
    api.post<User>('/auth/register', data).then(r => r.data),

  registerAdmin: (data: {
    nombre: string; email: string; password: string; telefono: string
    establecimiento_nombre: string; establecimiento_direccion: string
  }) => api.post<User>('/auth/register-admin', data).then(r => r.data),

  forgotPassword: (email: string) =>
    api.post<ForgotPasswordResponse>('/auth/forgot-password', { email }).then(r => r.data),

  resetPassword: (token: string, new_password: string) =>
    api.post<{ detail?: string; message?: string }>('/auth/reset-password', {
      token,
      nueva_password: new_password,
      new_password,
    }).then(r => r.data),
}

// ─── Perfil ───────────────────────────────────────────────────────────────────
export const perfilApi = {
  get: () => api.get<User>('/usuarios/perfil').then(r => r.data),
  update: (data: { nombre?: string; telefono?: string }) =>
    api.put<User>('/usuarios/perfil', data).then(r => r.data),
  changePassword: (current_password: string, new_password: string) =>
    api.put('/usuarios/perfil/password', { current_password, new_password }).then(r => r.data),
}

// ─── Canchas / Complejos ──────────────────────────────────────────────────────
export const canchasApi = {
  getComplejos: () => api.get<ComplejoDto[]>('/canchas/complejos').then(r => Array.isArray(r.data) ? r.data : []).catch(() => []),
  getComplejo: (id: string) => api.get<ComplejoDto>(`/canchas/complejos/${id}`).then(r => r.data),
  getDisponibilidad: (canchaId: string, fecha: string) =>
    api.get<BloqueHorarioDto[] | { bloques?: BloqueHorarioDto[] }>(`/canchas/${canchaId}/disponibilidad`, { params: { fecha } })
      .then(r => {
        const data = r.data
        if (Array.isArray(data)) return data
        if (data && typeof data === 'object' && Array.isArray(data.bloques)) {
          return data.bloques
        }
        return []
      })
      .catch(() => []),
  buscar: (fecha: string, tipo?: TipoCancha) =>
    api.get<ComplejoDto[]>('/canchas/buscar', { params: { fecha, tipo } }).then(r => Array.isArray(r.data) ? r.data : []).catch(() => []),

  // Admin
  getMisCanchas: () =>
    api.get<Array<CanchaDto | { canchas?: CanchaDto[]; nombre?: string }>>('/canchas/admin/mis-canchas')
      .then(r => {
        const data = r.data
        if (Array.isArray(data)) {
          if (data.length > 0 && 'tarifa_por_hora' in data[0]) {
            return data as CanchaDto[]
          }
          const flat: CanchaDto[] = []
          data.forEach(item => {
            if (item && 'canchas' in item && Array.isArray(item.canchas)) {
              flat.push(...item.canchas)
            } else if (item && 'tarifa_por_hora' in item && item.nombre) {
              flat.push(item as CanchaDto)
            }
          })
          return flat
        }
        return []
      })
      .catch(() => []),

  crearComplejo: (data: { nombre: string; direccion: string; barrio?: string; ciudad?: string; descripcion?: string; imagen_url?: string | null }) =>
    api.post<ComplejoDto>('/canchas/admin/complejos', data).then(r => r.data).catch(() => api.post<ComplejoDto>('/canchas/complejos', data).then(r => r.data)),

  updateComplejo: (id: string, data: Partial<ComplejoDto>) =>
    api.put<ComplejoDto>(`/canchas/admin/complejos/${id}`, data).then(r => r.data),

  crearCancha: (data: Partial<CanchaDto>) =>
    api.post<CanchaDto>('/canchas/admin/canchas', data).then(r => r.data),

  updateCancha: (id: string, data: Partial<CanchaDto>) =>
    api.put<CanchaDto>(`/canchas/admin/canchas/${id}`, data).then(r => r.data),

  toggleEstadoCancha: (id: string, activo?: boolean) =>
    api.patch<CanchaDto>(`/canchas/admin/canchas/${id}/estado`, null, {
      params: activo !== undefined ? { activo } : {},
    }).then(r => r.data),

  eliminarCancha: async (id: string) => {
    try {
      const res = await api.delete(`/canchas/admin/canchas/${id}`)
      return res.data
    } catch {
      const res2 = await api.delete(`/canchas/${id}`)
      return res2.data
    }
  },

  crearMantenimiento: (data: {
    cancha_id: string
    fecha: string
    hora_inicio: string
    hora_fin: string
    motivo?: string
  }) => api.post<BloqueoMantenimientoDto>('/canchas/admin/mantenimientos', data).then(r => r.data).catch(() => api.post<BloqueoMantenimientoDto>('/canchas/mantenimientos', data).then(r => r.data)),

  getMantenimientos: (params?: { cancha_id?: string; fecha?: string }) =>
    api.get<BloqueoMantenimientoDto[]>('/canchas/admin/mantenimientos', { params })
      .then(r => Array.isArray(r.data) ? r.data : [])
      .catch(() => api.get<BloqueoMantenimientoDto[]>('/canchas/mantenimientos', { params }).then(r => Array.isArray(r.data) ? r.data : []).catch(() => [])),

  eliminarMantenimiento: (id: string) =>
    api.delete(`/canchas/admin/mantenimientos/${id}`).then(r => r.data).catch(() => api.delete(`/canchas/mantenimientos/${id}`).then(r => r.data)),

  // Apariencia y Fondos
  getApariencia: () =>
    api.get<AparienciaConfigDto>('/canchas/apariencia')
      .then(r => r.data)
      .catch(() => ({
        fondo_general_url: '/assets/backgrounds/hero-stadium-bg.svg',
        fondo_slot_url: '/assets/backgrounds/cancha-slot-bg.svg',
      } as AparienciaConfigDto)),

  updateApariencia: (data: { fondo_general_url?: string | null; fondo_slot_url?: string | null }) =>
    api.put<AparienciaConfigDto>('/canchas/admin/apariencia', data).then(r => r.data),

  restaurarApariencia: (restaurarComplejosYCanchas = false) =>
    api.post<AparienciaConfigDto>('/canchas/admin/apariencia/restaurar', null, {
      params: { restaurar_complejos_y_canchas: restaurarComplejosYCanchas },
    }).then(r => r.data),

  uploadBackgroundImage: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ filename: string; url: string }>('/canchas/admin/uploads/backgrounds', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
}

export function renderizarDisponibilidad(bloques: unknown): BloqueHorarioDto[] {
  if (!Array.isArray(bloques)) {
    console.warn('renderizarDisponibilidad: bloques no es un array válido', bloques)
    return []
  }
  const lista: BloqueHorarioDto[] = []
  bloques.forEach((b) => {
    if (b && typeof b === 'object') lista.push(b as BloqueHorarioDto)
  })
  return lista
}

export async function buscarDisponibilidad(canchaId: string, fecha: string): Promise<BloqueHorarioDto[]> {
  try {
    const data = await canchasApi.getDisponibilidad(canchaId, fecha)
    return renderizarDisponibilidad(data)
  } catch (err) {
    console.warn(`buscarDisponibilidad: error en cancha ${canchaId}`, err)
    return []
  }
}

// ─── Reservas ─────────────────────────────────────────────────────────────────
export const reservasApi = {
  crear: (data: {
    cancha_id: string; complejo_id: string
    fecha: string; hora_inicio: string; hora_fin: string; monto: number
    nombre_cliente?: string; cliente_nombre?: string; cliente_email?: string; telefono_cliente?: string
  }) => api.post<ReservaDto>('/reservas', data).then(r => r.data),

  misReservas: () => api.get<ReservaDto[]>('/reservas/mis-reservas').then(r => r.data),

  cancelar: (id: string, motivo?: string) =>
    api.delete<ReservaDto>(`/reservas/${id}`, { data: { motivo } }).then(r => r.data),

  reprogramar: (id: string, data: { nueva_fecha: string; nueva_hora_inicio: string; nueva_hora_fin: string }) =>
    api.put<ReservaDto>(`/reservas/${id}/reprogramar`, data).then(r => r.data),

  // Admin
  todasAdmin: (fecha?: string) =>
    api.get<ReservaDto[]>('/reservas/admin/todas', { params: fecha ? { fecha } : {} }).then(r => r.data),

  getPorSlot: (canchaId: string, fecha: string, horaInicio: string) =>
    api.get<ReservaDto>('/reservas/admin/por-slot', {
      params: { cancha_id: canchaId, fecha, hora_inicio: horaInicio },
    }).then(r => r.data),

  getByIdAdmin: (id: string) =>
    api.get<ReservaDto>(`/reservas/admin/${id}`).then(r => r.data),

  confirmarAdmin: (id: string) =>
    api.post<ReservaDto>(`/reservas/admin/${id}/confirmar`).then(r => r.data),

  crearPresencial: (data: {
    cancha_id: string; complejo_id?: string
    nombre_cliente?: string; cliente_nombre?: string; cliente_email?: string; telefono_cliente?: string
    fecha: string; hora_inicio: string; hora_fin?: string; monto: number
    admin_id?: string
    estado?: EstadoReserva
    pagado?: boolean
    metodo_pago?: string
  }) => api.post<ReservaDto>('/reservas/admin/presencial', data).then(r => r.data),

  cancelarAdmin: (id: string, motivo: string) =>
    api.delete<ReservaDto>(`/reservas/admin/${id}`, { data: { motivo } }).then(r => r.data),

  reprogramarAdmin: (id: string, data: { nueva_fecha: string; nueva_hora_inicio: string; nueva_hora_fin: string }) =>
    api.put<ReservaDto>(`/reservas/admin/${id}/reprogramar`, data).then(r => r.data),
}

// ─── Pagos & Wompi Colombia ───────────────────────────────────────────────────
export const pagosApi = {
  prepararWompi: (data: { reserva_id: string; monto: number; referencia_externa?: string }) =>
    api.post<WompiPrepararResponse>('/pagos/wompi/preparar', data).then(r => r.data),

  wompiWebhook: (data: {
    reference: string
    status: 'APPROVED' | 'DECLINED'
    metodo_pago: MetodoPago
    reserva_id: string
    usuario_id?: string
    complejo_id?: string
    monto: number
    transaction_id?: string
    customer_email?: string
    observaciones?: string
  }) => api.post<PagoDto>('/pagos/wompi/webhook', data).then(r => r.data),

  procesar: (data: {
    reserva_id: string; usuario_id: string; complejo_id: string
    monto: number; metodo: MetodoPago; simular_resultado: 'APROBADO' | 'RECHAZADO'
    referencia_externa?: string; observaciones?: string; datos_metodo?: Record<string, string>
  }) => api.post<PagoDto>('/pagos/procesar', data).then(r => r.data),

  misPagos: () => api.get<PagoDto[]>('/pagos/mis-pagos').then(r => r.data),

  reportesAdmin: (params: { complejo_id?: string; fecha_inicio?: string; fecha_fin?: string; estado?: EstadoPago }) =>
    api.get<PagoDto[]>('/pagos/admin/reportes', { params })
      .then(r => Array.isArray(r.data) ? r.data : [])
      .catch(() => []),

  registrarPresencial: (data: {
    reserva_id: string; complejo_id?: string; monto: number
    metodo: 'EFECTIVO' | 'TRANSFERENCIA' | 'NEQUI' | 'TARJETA' | MetodoPago; fecha?: string; observaciones?: string
  }) =>
    api.post<PagoDto>('/pagos/presencial', data)
      .then(r => r.data)
      .catch(() => api.post<PagoDto>('/pagos/admin/presencial', data).then(r => r.data)),

  getPorReserva: (reservaId: string) =>
    api.get<PagoDto | null>(`/pagos/reserva/${reservaId}`).then(r => r.data).catch(() => null),
}

// ─── Notificaciones ───────────────────────────────────────────────────────────
export const notificacionesApi = {
  getLogs: (event_type?: string) =>
    api
      .get<EmailLogsPayload>('/notificaciones/logs', { params: event_type ? { event_type } : {} })
      .then(r => {
        if (!r.data) return []
        if (Array.isArray(r.data)) return r.data
        if (Array.isArray(r.data.correos)) return r.data.correos
        if (Array.isArray(r.data.logs)) return r.data.logs
        return []
      })
      .catch(() => []),
  getStats: () =>
    api
      .get<EventStats>('/notificaciones/logs/stats')
      .then(r => r.data)
      .catch(() => ({ total_correos: 0, por_evento: {} })),
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
interface ValidationErrorItem {
  loc?: unknown[]
  msg?: string
}

interface HttpErrorLike {
  response?: {
    data?: {
      detail?: string | Array<string | ValidationErrorItem> | { message?: string; msg?: string }
      message?: string
    }
  }
  message?: string
}

export function extractErrorMessage(err: unknown, fallback = 'Ha ocurrido un error inesperado'): string {
  if (!err || typeof err !== 'object') return fallback
  const httpErr = err as HttpErrorLike
  const detail = httpErr.response?.data?.detail
  if (detail) {
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') return item
          const loc = Array.isArray(item.loc)
            ? item.loc.filter((x) => x !== 'body').join('.')
            : ''
          const msg = item.msg || JSON.stringify(item)
          return loc ? `${loc}: ${msg}` : msg
        })
        .join(' | ')
    }
    if (typeof detail === 'object') {
      return detail.message || detail.msg || JSON.stringify(detail)
    }
  }
  return httpErr.response?.data?.message || httpErr.message || fallback
}

export const formatCOP = (amount: number) =>
  new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', minimumFractionDigits: 0 }).format(amount)

export function isSlotInPast(fechaStr?: string, horaInicioStr?: string): boolean {
  if (!fechaStr || !horaInicioStr) return false
  const now = new Date()
  const horaClean = horaInicioStr.substring(0, 5)
  const [year, month, day] = fechaStr.split('-').map(Number)
  const [hours, minutes] = horaClean.split(':').map(Number)
  if (isNaN(year) || isNaN(month) || isNaN(day) || isNaN(hours)) return false
  const slotDate = new Date(year, month - 1, day, hours, minutes || 0, 0)
  return slotDate.getTime() < now.getTime()
}

export const TIPO_LABELS: Record<string, string> = {
  FUTBOL_5: 'Fútbol 5',
  FUTBOL_7: 'Fútbol 7',
  FUTBOL_8: 'Fútbol 8',
}

export const ESTADO_RESERVA_LABELS: Record<string, string> = {
  PENDIENTE_PAGO: 'Pendiente Pago',
  CONFIRMADA: 'Confirmada',
  CANCELADA: 'Cancelada',
  CANCELADA_ADMIN: 'Cancelada (Admin)',
  CONFIRMADA_PRESENCIAL: 'Confirmada Presencial',
}
