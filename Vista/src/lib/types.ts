// Definiciones TypeScript de entidades y DTOs sincronizados con el backend (Capa Modelo)

export interface User {
  id: string
  nombre: string
  email: string
  telefono?: string
  rol: 'USUARIO' | 'ADMIN_ESTABLECIMIENTO'
  establecimiento_id: string | null
  activo: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  usuario?: User
  usuario_id?: string
  rol?: User['rol']
  nombre?: string
  email?: string
  establecimiento_id?: string | null
}

export interface ForgotPasswordResponse {
  token?: string
  detail?: string
  message?: string
}

export type TipoCancha = 'FUTBOL_5' | 'FUTBOL_7' | 'FUTBOL_8'

export interface CanchaDto {
  id: string
  complejo_id: string
  nombre: string
  tipo: TipoCancha
  tarifa_por_hora: number
  descripcion?: string
  imagen_url?: string | null
  activo: boolean
  hora_apertura: string
  hora_cierre: string
}

export interface ComplejoDto {
  id: string
  nombre: string
  direccion: string
  barrio: string
  ciudad: string
  descripcion?: string
  imagen_url?: string | null
  activo: boolean
  canchas: CanchaDto[]
}

export interface AparienciaConfigDto {
  fondo_general_url?: string | null
  fondo_slot_url?: string | null
  updated_at?: string
}

export type EstadoBloque = 'LIBRE' | 'BLOQUEADO_TEMPORAL' | 'OCUPADO' | 'MANTENIMIENTO'

export interface BloqueoMantenimientoDto {
  id: string
  cancha_id: string
  fecha: string
  hora_inicio: string
  hora_fin: string
  motivo?: string
  activo: boolean
  created_at: string
}

export interface BloqueHorarioDto {
  id: string
  cancha_id: string
  fecha: string
  hora_inicio: string
  hora_fin: string
  estado: EstadoBloque
  reserva_id?: string | null
}

export type EstadoReserva =
  | 'PENDIENTE_PAGO'
  | 'CONFIRMADA'
  | 'CANCELADA'
  | 'CANCELADA_ADMIN'
  | 'CONFIRMADA_PRESENCIAL'

export interface ReservaDto {
  id: string
  codigo_uid: string
  cancha_id: string
  complejo_id: string
  usuario_id?: string | null
  nombre_cliente?: string | null
  cliente_nombre?: string | null
  usuario_nombre?: string | null
  cliente_email?: string | null
  telefono_cliente?: string | null
  fecha: string
  hora_inicio: string
  hora_fin: string
  estado: EstadoReserva
  motivo_cancelacion?: string | null
  monto: number
  created_at: string
  updated_at: string
}

export type EstadoPago = 'PENDIENTE' | 'APROBADO' | 'RECHAZADO'
export type MetodoPago =
  | 'WOMPI_NEQUI'
  | 'WOMPI_PSE'
  | 'WOMPI_BANCOLOMBIA'
  | 'WOMPI_CARD'
  | 'TARJETA'
  | 'BRE_B'
  | 'EFECTIVO'
  | 'TRANSFERENCIA'

export interface WompiPrepararResponse {
  referencia_externa: string
  amount_in_cents: number
  currency: string
  public_key: string
  integrity_signature?: string | null
  sandbox: boolean
}

export interface PagoDto {
  id: string
  reserva_id: string
  usuario_id?: string | null
  admin_id?: string | null
  complejo_id: string
  monto: number
  metodo: MetodoPago
  estado: EstadoPago
  referencia_externa?: string | null
  observaciones?: string | null
  created_at: string
}

export interface EmailLog {
  id: string
  to_email: string
  to_name: string
  subject: string
  body: string
  event_type: string
  aggregate_id: string
  timestamp: string
  status: string
  error_detail?: string | null
}

export interface EventStats {
  total_correos: number
  por_evento: Record<string, number>
}

export type EmailLogsPayload =
  | EmailLog[]
  | { correos?: EmailLog[]; logs?: EmailLog[] }
