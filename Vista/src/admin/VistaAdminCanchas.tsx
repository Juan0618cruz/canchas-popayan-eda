import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Edit2, Loader2, Plus, Save, X, Wrench, CheckCircle2, Trash2, Building2, Filter, Upload } from 'lucide-react'
import { canchasApi, formatCOP, TIPO_LABELS, extractErrorMessage } from '../lib/api'
import { resolveMediaUrl } from '../store/appearanceStore'
import type { CanchaDto, TipoCancha } from '../lib/types'
import Modal from '../components/Modal'
import LoadingSpinner from '../components/LoadingSpinner'

interface CanchaFormData {
  complejo_id: string
  nombre: string
  tipo: TipoCancha
  tarifa_por_hora: string
  descripcion: string
  imagen_url: string
  activo: boolean
}

const DEFAULT_FORM: CanchaFormData = {
  complejo_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  nombre: '',
  tipo: 'FUTBOL_5',
  tarifa_por_hora: '70000',
  descripcion: '',
  imagen_url: '',
  activo: true,
}

const HOURS_OPCIONES = Array.from({ length: 15 }, (_, i) => `${String(i + 8).padStart(2, '0')}:00`)
const HOURS_FIN_OPCIONES = Array.from({ length: 15 }, (_, i) => `${String(i + 9).padStart(2, '0')}:00`)

export default function VistaAdminCanchas() {
  const queryClient = useQueryClient()
  const [editModal, setEditModal] = useState<CanchaDto | null>(null)
  const [createModal, setCreateModal] = useState(false)
  const [nuevoComplejoModal, setNuevoComplejoModal] = useState(false)
  const [form, setForm] = useState<CanchaFormData>(DEFAULT_FORM)
  const [errorMsg, setErrorMsg] = useState('')
  const [selectedComplejoFilter, setSelectedComplejoFilter] = useState<string>('ALL')
  const [uploadingImg, setUploadingImg] = useState(false)

  // Formulario para registrar un nuevo complejo deportivo
  const [nuevoCompForm, setNuevoCompForm] = useState({
    nombre: '',
    direccion: '',
    barrio: '',
    ciudad: 'Popayán',
    descripcion: '',
    imagen_url: '',
  })

  // Estado para Mantenimiento por Franja Horaria
  const [mantenimientoModal, setMantenimientoModal] = useState(false)
  const [mantForm, setMantForm] = useState({
    cancha_id: '',
    fecha: new Date().toISOString().split('T')[0],
    hora_inicio: '14:00',
    hora_fin: '16:00',
    motivo: 'Mantenimiento preventivo / césped',
  })

  // Invalidar caché de forma inmediata en todas las consultas para reflejar cambios sin retraso
  const invalidateAllCaches = () => {
    queryClient.invalidateQueries({ queryKey: ['admin-canchas'] })
    queryClient.invalidateQueries({ queryKey: ['complejos'] })
    queryClient.invalidateQueries({ queryKey: ['disponibilidad'] })
    queryClient.invalidateQueries({ queryKey: ['mantenimientos'] })
  }

  // Consulta de canchas (retorna todas las canchas de todos los complejos gestionados)
  const { data: canchas = [], isLoading: loadingCanchas } = useQuery({
    queryKey: ['admin-canchas'],
    queryFn: canchasApi.getMisCanchas,
  })

  // Consulta de complejos deportivos registrados (Balón de Oro, Bernabéu, etc.)
  const { data: complejos = [], isLoading: loadingComplejos } = useQuery({
    queryKey: ['complejos'],
    queryFn: canchasApi.getComplejos,
  })

  // Consulta de bloqueos de mantenimiento por franjas horarias
  const { data: mantenimientos = [] } = useQuery({
    queryKey: ['mantenimientos'],
    queryFn: () => canchasApi.getMantenimientos(),
  })

  // Mutación para Crear Cancha
  const { mutate: crearCancha, isPending: creando } = useMutation({
    mutationFn: () => {
      const tarifa = Number(form.tarifa_por_hora)
      if (!form.nombre.trim()) throw new Error('El nombre de la cancha es obligatorio.')
      if (isNaN(tarifa) || tarifa <= 0) throw new Error('La tarifa debe ser un monto numérico mayor a $0.')
      return canchasApi.crearCancha({
        complejo_id: form.complejo_id || (complejos[0]?.id || 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'),
        nombre: form.nombre.trim(),
        tipo: form.tipo,
        tarifa_por_hora: tarifa,
        descripcion: form.descripcion.trim() || undefined,
        imagen_url: form.imagen_url.trim() || null,
        activo: form.activo,
      })
    },
    onSuccess: () => {
      setCreateModal(false)
      setForm(DEFAULT_FORM)
      invalidateAllCaches()
    },
    onError: (err: unknown) => setErrorMsg(extractErrorMessage(err, 'Error al crear la cancha.')),
  })

  // Mutación para Editar Cancha
  const { mutate: updateCancha, isPending: updating } = useMutation({
    mutationFn: () => {
      if (!editModal) throw new Error('No se ha seleccionado ninguna cancha.')
      const tarifa = Number(form.tarifa_por_hora)
      if (!form.nombre.trim()) throw new Error('El nombre de la cancha es obligatorio.')
      if (isNaN(tarifa) || tarifa <= 0) throw new Error('La tarifa debe ser mayor a $0.')
      return canchasApi.updateCancha(editModal.id, {
        complejo_id: form.complejo_id || undefined,
        nombre: form.nombre.trim(),
        tipo: form.tipo,
        tarifa_por_hora: tarifa,
        descripcion: form.descripcion.trim() || undefined,
        imagen_url: form.imagen_url.trim() || null,
        activo: form.activo,
      })
    },
    onSuccess: () => {
      setEditModal(null)
      invalidateAllCaches()
    },
    onError: (err: unknown) => setErrorMsg(extractErrorMessage(err, 'Error al actualizar.')),
  })

  // Mutación para Eliminar Cancha
  const { mutate: eliminarCancha, isPending: eliminando } = useMutation({
    mutationFn: (id: string) => canchasApi.eliminarCancha(id),
    onSuccess: () => {
      invalidateAllCaches()
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al eliminar la cancha.')),
  })

  // Mutación para Registrar Nuevo Complejo Deportivo
  const { mutate: crearComplejoMut, isPending: guardandoComplejo } = useMutation({
    mutationFn: () => {
      if (!nuevoCompForm.nombre.trim()) throw new Error('El nombre del complejo es obligatorio.')
      if (!nuevoCompForm.direccion.trim()) throw new Error('La dirección es obligatoria.')
      return canchasApi.crearComplejo({
        nombre: nuevoCompForm.nombre.trim(),
        direccion: nuevoCompForm.direccion.trim(),
        barrio: nuevoCompForm.barrio.trim() || 'Centro',
        ciudad: nuevoCompForm.ciudad.trim() || 'Popayán',
        descripcion: nuevoCompForm.descripcion.trim() || undefined,
        imagen_url: nuevoCompForm.imagen_url.trim() || null,
      })
    },
    onSuccess: (nuevo) => {
      setNuevoComplejoModal(false)
      setNuevoCompForm({ nombre: '', direccion: '', barrio: '', ciudad: 'Popayán', descripcion: '', imagen_url: '' })
      invalidateAllCaches()
      if (nuevo?.id) {
        setForm(f => ({ ...f, complejo_id: nuevo.id }))
      }
      alert('✅ Complejo deportivo registrado exitosamente.')
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al crear el complejo deportivo.')),
  })

  // Mutación para Programar Mantenimiento por Franja Horaria
  const { mutate: guardarMantenimiento, isPending: guardandoMantenimiento } = useMutation({
    mutationFn: () => {
      if (!mantForm.cancha_id) throw new Error('Debes seleccionar una cancha.')
      if (!mantForm.fecha) throw new Error('La fecha es requerida.')
      if (mantForm.hora_fin <= mantForm.hora_inicio) throw new Error('La hora de fin debe ser posterior a la de inicio.')
      return canchasApi.crearMantenimiento({
        cancha_id: mantForm.cancha_id,
        fecha: mantForm.fecha,
        hora_inicio: mantForm.hora_inicio.length === 5 ? mantForm.hora_inicio + ':00' : mantForm.hora_inicio,
        hora_fin: mantForm.hora_fin.length === 5 ? mantForm.hora_fin + ':00' : mantForm.hora_fin,
        motivo: mantForm.motivo,
      })
    },
    onSuccess: () => {
      setMantenimientoModal(false)
      invalidateAllCaches()
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al programar el mantenimiento.')),
  })

  // Mutación para Eliminar Bloqueo de Mantenimiento
  const { mutate: eliminarMantenimiento, isPending: eliminandoMantenimiento } = useMutation({
    mutationFn: (id: string) => canchasApi.eliminarMantenimiento(id),
    onSuccess: () => {
      invalidateAllCaches()
    },
    onError: (err: unknown) => alert('❌ ' + extractErrorMessage(err, 'Error al eliminar el mantenimiento.')),
  })

  const openEdit = (cancha: CanchaDto) => {
    setForm({
      complejo_id: cancha.complejo_id || (complejos[0]?.id || ''),
      nombre: cancha.nombre,
      tipo: cancha.tipo,
      tarifa_por_hora: String(cancha.tarifa_por_hora),
      descripcion: cancha.descripcion || '',
      imagen_url: cancha.imagen_url || '',
      activo: cancha.activo,
    })
    setErrorMsg('')
    setEditModal(cancha)
  }

  const openCreate = () => {
    const defaultCompId = selectedComplejoFilter !== 'ALL'
      ? selectedComplejoFilter
      : (complejos[0]?.id || 'a1b2c3d4-e5f6-7890-abcd-ef1234567890')

    setForm({
      ...DEFAULT_FORM,
      complejo_id: defaultCompId,
    })
    setErrorMsg('')
    setCreateModal(true)
  }

  const openMantenimiento = (cancha?: CanchaDto) => {
    setMantForm({
      cancha_id: cancha ? cancha.id : (canchas.length > 0 ? canchas[0].id : ''),
      fecha: new Date().toISOString().split('T')[0],
      hora_inicio: '14:00',
      hora_fin: '16:00',
      motivo: 'Mantenimiento preventivo / césped',
    })
    setMantenimientoModal(true)
  }

  const handleUploadImage = async (file: File | undefined, onDone: (url: string) => void) => {
    if (!file) return
    setUploadingImg(true)
    try {
      const res = await canchasApi.uploadBackgroundImage(file)
      onDone(res.url)
    } catch (err: unknown) {
      setErrorMsg(extractErrorMessage(err, 'Error al subir la imagen.'))
    } finally {
      setUploadingImg(false)
    }
  }

  // Filtrado de canchas según complejo seleccionado
  const canchasFiltradas = selectedComplejoFilter === 'ALL'
    ? canchas
    : canchas.filter(c => c.complejo_id === selectedComplejoFilter)

  if (loadingCanchas || loadingComplejos) return <LoadingSpinner />

  return (
    <div>
      {/* Cabecera y Barra de Acciones */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900">🏟️ Mis Canchas y Sedes</h2>
          <p className="text-sm text-gray-500">
            Administra las canchas de todas las sedes deportivas (Balón de Oro, Bernabéu) y programa mantenimientos por franja horaria
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => setNuevoComplejoModal(true)}
            className="btn-secondary flex items-center gap-1.5 text-xs border-blue-200 text-blue-700 bg-blue-50 hover:bg-blue-100"
          >
            <Building2 size={15} /> + Nueva Sede
          </button>
          <button
            onClick={() => openMantenimiento()}
            className="btn-secondary flex items-center gap-1.5 text-xs border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100"
          >
            <Wrench size={15} /> Programar Franja Mantenimiento
          </button>
          <button onClick={openCreate} className="btn-primary flex items-center gap-1.5 text-xs">
            <Plus size={15} /> Nueva Cancha
          </button>
        </div>
      </div>

      {/* Barra de Filtro por Complejo Deportivo */}
      <div className="bg-white p-3.5 rounded-xl border border-gray-200 shadow-sm mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-gray-500" />
          <span className="text-xs font-semibold text-gray-700 uppercase tracking-wide">FILTRAR POR SEDE:</span>
          <select
            value={selectedComplejoFilter}
            onChange={e => setSelectedComplejoFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-lg px-3 py-1.5 bg-gray-50 font-medium text-gray-800 focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            <option value="ALL">🏢 Todas las sedes ({canchas.length} canchas en total)</option>
            {complejos.map(comp => {
              const cant = canchas.filter(c => c.complejo_id === comp.id).length
              return (
                <option key={comp.id} value={comp.id}>
                  🏟️ {comp.nombre} ({cant} {cant === 1 ? 'cancha' : 'canchas'})
                </option>
              )
            })}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge bg-green-100 text-green-700 text-xs">
            {canchasFiltradas.length} {canchasFiltradas.length === 1 ? 'cancha mostrada' : 'canchas mostradas'}
          </span>
        </div>
      </div>

      {/* Tabla de Canchas */}
      {canchasFiltradas.length === 0 ? (
        <div className="card text-center py-12">
          <Building2 size={36} className="mx-auto text-gray-300 mb-2" />
          <p className="text-gray-500 font-medium mb-1">No hay canchas registradas en esta sede.</p>
          <p className="text-xs text-gray-400 mb-4">Puedes registrar una nueva cancha sintética asociada a esta sede deportiva.</p>
          <button onClick={openCreate} className="btn-primary inline-flex items-center gap-2 text-sm">
            <Plus size={16} /> Registrar Cancha en esta Sede
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Nombre', 'Sede Deportiva', 'Tipo', 'Tarifa/hora', 'Estado Operativo', 'Acciones'].map(h => (
                  <th key={h} className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {canchasFiltradas.map(cancha => {
                const comp = complejos.find(cp => cp.id === cancha.complejo_id)
                return (
                  <tr key={cancha.id} className="hover:bg-gray-50 transition-colors">
                    {/* 1. Nombre */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        {cancha.imagen_url ? (
                          <img
                            src={resolveMediaUrl(cancha.imagen_url)}
                            alt={cancha.nombre}
                            className="w-9 h-9 rounded-lg object-cover border border-emerald-200 shrink-0"
                          />
                        ) : (
                          <div className="w-9 h-9 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm shrink-0">
                            ⚽
                          </div>
                        )}
                        <div>
                          <p className="font-semibold text-gray-900 text-sm">{cancha.nombre}</p>
                          {cancha.descripcion && <p className="text-xs text-gray-400 line-clamp-1">{cancha.descripcion}</p>}
                        </div>
                      </div>
                    </td>

                    {/* 2. Complejo Deportivo */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-xs text-gray-800 font-medium">
                        <Building2 size={14} className="text-blue-600 flex-shrink-0" />
                        <span>{comp?.nombre || 'Complejo Deportivo'}</span>
                      </div>
                      {comp?.barrio && <span className="text-[11px] text-gray-400 block">{comp.barrio}</span>}
                    </td>

                    {/* 3. Tipo */}
                    <td className="px-4 py-3">
                      <span className={`badge text-xs ${
                        cancha.tipo === 'FUTBOL_5' ? 'bg-blue-100 text-blue-700' :
                        cancha.tipo === 'FUTBOL_7' ? 'bg-purple-100 text-purple-700' :
                        'bg-orange-100 text-orange-700'
                      }`}>
                        {TIPO_LABELS[cancha.tipo]}
                      </span>
                    </td>

                    {/* 4. Tarifa/hora */}
                    <td className="px-4 py-3 font-semibold text-green-700 text-sm">
                      {formatCOP(Number(cancha.tarifa_por_hora))}
                    </td>

                    {/* 5. Estado Operativo */}
                    <td className="px-4 py-3">
                      <span className={`badge text-xs flex items-center gap-1 w-fit ${
                        cancha.activo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                      }`}>
                        {cancha.activo ? <CheckCircle2 size={12} /> : <Wrench size={12} />}
                        {cancha.activo ? 'OPERATIVA' : 'INACTIVA'}
                      </span>
                    </td>

                    {/* 6. Acciones (Editar, Franja Mant, Eliminar) */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => openEdit(cancha)}
                          className="btn-secondary py-1.5 px-2.5 text-xs flex items-center gap-1"
                        >
                          <Edit2 size={12} /> Editar
                        </button>
                        <button
                          onClick={() => openMantenimiento(cancha)}
                          title="Programar mantenimiento por franja horaria en esta cancha"
                          className="py-1.5 px-2.5 text-xs rounded-lg font-medium border border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100 transition-colors flex items-center gap-1"
                        >
                          <Wrench size={12} /> Franja Mant.
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm(`¿Estás seguro de que deseas eliminar permanentemente la cancha "${cancha.nombre}"?`)) {
                              eliminarCancha(cancha.id)
                            }
                          }}
                          disabled={eliminando}
                          title="Eliminar Cancha"
                          className="py-1.5 px-2.5 text-xs rounded-lg font-medium border border-red-200 text-red-600 bg-red-50 hover:bg-red-100 transition-colors flex items-center gap-1"
                        >
                          <Trash2 size={12} /> Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal Crear Cancha */}
      <Modal isOpen={createModal} onClose={() => setCreateModal(false)} title="➕ Nueva Cancha Sintética">
        <div className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">Sede Deportiva</label>
              <button
                type="button"
                onClick={() => {
                  setCreateModal(false)
                  setNuevoComplejoModal(true)
                }}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
              >
                <Plus size={12} /> + Registrar Nueva Sede
              </button>
            </div>
            <select
              value={form.complejo_id}
              onChange={e => setForm(f => ({ ...f, complejo_id: e.target.value }))}
              className="input-field"
            >
              {complejos.map(comp => (
                <option key={comp.id} value={comp.id}>
                  🏢 {comp.nombre} ({comp.barrio || comp.direccion})
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-0.5">Permite asignar la cancha a Balón de Oro, Bernabéu u otra sede</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre de la cancha</label>
            <input
              type="text"
              value={form.nombre}
              onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
              placeholder="Ej: Cancha 1 - Sintética Techada"
              className="input-field"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de cancha</label>
            <select
              value={form.tipo}
              onChange={e => setForm(f => ({ ...f, tipo: e.target.value as TipoCancha }))}
              className="input-field"
            >
              <option value="FUTBOL_5">Fútbol 5</option>
              <option value="FUTBOL_7">Fútbol 7</option>
              <option value="FUTBOL_8">Fútbol 8</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tarifa por hora (COP)</label>
            <input
              type="text"
              inputMode="numeric"
              value={form.tarifa_por_hora}
              onChange={e => setForm(f => ({ ...f, tarifa_por_hora: e.target.value.replace(/[^0-9]/g, '') }))}
              placeholder="70000"
              className="input-field"
            />
            <p className="text-xs text-gray-400 mt-0.5">Ingresa el valor numérico deseado</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Descripción (opcional)</label>
            <textarea
              value={form.descripcion}
              onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
              placeholder="Ej: Grama sintética de última generación, iluminación LED nocturna..."
              className="input-field"
              rows={2}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Imagen de la cancha (opcional)</label>
            <div className="flex gap-2 items-center">
              <input
                type="text"
                value={form.imagen_url}
                onChange={e => setForm(f => ({ ...f, imagen_url: e.target.value }))}
                placeholder="URL de imagen o sube un archivo..."
                className="input-field flex-1 text-xs"
              />
              <label className="btn-secondary py-2 px-3 text-xs flex items-center gap-1 cursor-pointer shrink-0">
                {uploadingImg ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                Subir
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,.svg,image/*"
                  className="hidden"
                  onChange={e => {
                    handleUploadImage(e.target.files?.[0], url => setForm(f => ({ ...f, imagen_url: url })))
                    e.target.value = ''
                  }}
                />
              </label>
            </div>
          </div>

          {errorMsg && <p className="text-sm text-red-600">❌ {errorMsg}</p>}

          <div className="flex gap-3 pt-2">
            <button onClick={() => setCreateModal(false)} className="btn-secondary flex-1 flex items-center justify-center gap-1">
              <X size={15} /> Cancelar
            </button>
            <button onClick={() => crearCancha()} disabled={creando} className="btn-primary flex-1 flex items-center justify-center gap-2">
              {creando ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              Crear Cancha
            </button>
          </div>
        </div>
      </Modal>

      {/* Modal Editar Cancha */}
      <Modal isOpen={!!editModal} onClose={() => setEditModal(null)} title="✏️ Editar Cancha">
        {editModal && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Sede Deportiva</label>
              <select
                value={form.complejo_id}
                onChange={e => setForm(f => ({ ...f, complejo_id: e.target.value }))}
                className="input-field"
              >
                {complejos.map(comp => (
                  <option key={comp.id} value={comp.id}>
                    🏢 {comp.nombre} ({comp.barrio || comp.direccion})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
              <input
                type="text"
                value={form.nombre}
                onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
                className="input-field"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de cancha</label>
              <select
                value={form.tipo}
                onChange={e => setForm(f => ({ ...f, tipo: e.target.value as TipoCancha }))}
                className="input-field"
              >
                <option value="FUTBOL_5">Fútbol 5</option>
                <option value="FUTBOL_7">Fútbol 7</option>
                <option value="FUTBOL_8">Fútbol 8</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tarifa por hora (COP)</label>
              <input
                type="text"
                inputMode="numeric"
                value={form.tarifa_por_hora}
                onChange={e => setForm(f => ({ ...f, tarifa_por_hora: e.target.value.replace(/[^0-9]/g, '') }))}
                className="input-field"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
              <textarea
                value={form.descripcion}
                onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
                className="input-field"
                rows={2}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Imagen de la cancha (opcional)</label>
              <div className="flex gap-2 items-center">
                <input
                  type="text"
                  value={form.imagen_url}
                  onChange={e => setForm(f => ({ ...f, imagen_url: e.target.value }))}
                  placeholder="URL de imagen o sube un archivo..."
                  className="input-field flex-1 text-xs"
                />
                <label className="btn-secondary py-2 px-3 text-xs flex items-center gap-1 cursor-pointer shrink-0">
                  {uploadingImg ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                  Subir
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp,.svg,image/*"
                    className="hidden"
                    onChange={e => {
                      handleUploadImage(e.target.files?.[0], url => setForm(f => ({ ...f, imagen_url: url })))
                      e.target.value = ''
                    }}
                  />
                </label>
              </div>
            </div>

            {errorMsg && <p className="text-sm text-red-600">❌ {errorMsg}</p>}

            <div className="flex gap-3 pt-2">
              <button onClick={() => setEditModal(null)} className="btn-secondary flex-1 flex items-center justify-center gap-1">
                <X size={15} /> Cancelar
              </button>
              <button onClick={() => updateCancha()} disabled={updating} className="btn-primary flex-1 flex items-center justify-center gap-2">
                {updating ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                Guardar Cambios
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Modal Registrar Nuevo Complejo Deportivo */}
      <Modal isOpen={nuevoComplejoModal} onClose={() => setNuevoComplejoModal(false)} title="🏢 Registrar Nueva Sede Deportiva">
        <div className="space-y-4">
          <p className="text-xs text-gray-500">
            Registra una nueva sede deportiva para comenzar a gestionar sus canchas y reservas en Popayán.
          </p>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre de la Sede</label>
            <input
              type="text"
              value={nuevoCompForm.nombre}
              onChange={e => setNuevoCompForm(f => ({ ...f, nombre: e.target.value }))}
              placeholder="Ej: Complejo Sintético Bernabéu"
              className="input-field"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Dirección</label>
            <input
              type="text"
              value={nuevoCompForm.direccion}
              onChange={e => setNuevoCompForm(f => ({ ...f, direccion: e.target.value }))}
              placeholder="Ej: Calle 5 # 23-10, Sector Norte"
              className="input-field"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Barrio / Sector</label>
              <input
                type="text"
                value={nuevoCompForm.barrio}
                onChange={e => setNuevoCompForm(f => ({ ...f, barrio: e.target.value }))}
                placeholder="Ej: Modelo"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ciudad</label>
              <input
                type="text"
                value={nuevoCompForm.ciudad}
                onChange={e => setNuevoCompForm(f => ({ ...f, ciudad: e.target.value }))}
                placeholder="Popayán"
                className="input-field"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Descripción (opcional)</label>
            <textarea
              value={nuevoCompForm.descripcion}
              onChange={e => setNuevoCompForm(f => ({ ...f, descripcion: e.target.value }))}
              placeholder="Ej: Instalaciones modernas, parqueadero privado, cafetería..."
              className="input-field"
              rows={2}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Banner de la Sede (opcional)</label>
            <div className="flex gap-2 items-center">
              <input
                type="text"
                value={nuevoCompForm.imagen_url}
                onChange={e => setNuevoCompForm(f => ({ ...f, imagen_url: e.target.value }))}
                placeholder="URL del banner o sube una imagen..."
                className="input-field flex-1 text-xs"
              />
              <label className="btn-secondary py-2 px-3 text-xs flex items-center gap-1 cursor-pointer shrink-0">
                {uploadingImg ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                Subir
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,.svg,image/*"
                  className="hidden"
                  onChange={e => {
                    handleUploadImage(e.target.files?.[0], url => setNuevoCompForm(f => ({ ...f, imagen_url: url })))
                    e.target.value = ''
                  }}
                />
              </label>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={() => setNuevoComplejoModal(false)} className="btn-secondary flex-1">
              Cancelar
            </button>
            <button
              onClick={() => crearComplejoMut()}
              disabled={guardandoComplejo}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {guardandoComplejo ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Guardar Sede
            </button>
          </div>
        </div>
      </Modal>

      {/* Sección de Mantenimientos por Franja Horaria (Parcial) */}
      <div className="mt-8 bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <Wrench size={18} className="text-amber-600" />
              Bloqueos de Mantenimiento por Franja Horaria (Parcial)
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Solo las horas bloqueadas se marcarán como no disponibles ("-") en el Catálogo, manteniendo libres las demás horas del día.
            </p>
          </div>
          <button
            onClick={() => openMantenimiento()}
            className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5 border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100"
          >
            <Plus size={14} /> Nueva Franja
          </button>
        </div>

        {mantenimientos.length === 0 ? (
          <div className="text-center py-6 border border-dashed border-gray-200 rounded-lg text-gray-400 text-xs">
            No hay bloqueos de mantenimiento parciales programados. Todas las canchas operan en su horario regular.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-100 text-gray-500 font-semibold uppercase">
                <tr>
                  <th className="py-2.5 px-3">Cancha</th>
                  <th className="py-2.5 px-3">Complejo</th>
                  <th className="py-2.5 px-3">Fecha</th>
                  <th className="py-2.5 px-3">Horario Afectado</th>
                  <th className="py-2.5 px-3">Motivo</th>
                  <th className="py-2.5 px-3 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mantenimientos.map(m => {
                  const cancha = canchas.find(c => c.id === m.cancha_id)
                  const comp = complejos.find(cp => cp.id === cancha?.complejo_id)
                  return (
                    <tr key={m.id} className="hover:bg-amber-50/40 transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-gray-900">{cancha?.nombre || 'Cancha'}</td>
                      <td className="py-2.5 px-3 text-gray-600">{comp?.nombre || 'Complejo Deportivo'}</td>
                      <td className="py-2.5 px-3 text-gray-600">{m.fecha}</td>
                      <td className="py-2.5 px-3">
                        <span className="badge bg-amber-100 text-amber-800 font-bold">
                          {String(m.hora_inicio).substring(0, 5)} — {String(m.hora_fin).substring(0, 5)}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-gray-500">{m.motivo || 'Mantenimiento preventivo'}</td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() => {
                            if (window.confirm('¿Deseas levantar este bloqueo de mantenimiento y liberar las horas?')) {
                              eliminarMantenimiento(m.id)
                            }
                          }}
                          disabled={eliminandoMantenimiento}
                          className="text-red-600 hover:text-red-800 font-medium underline"
                        >
                          Eliminar bloqueo
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal Programar Mantenimiento por Horario */}
      <Modal isOpen={mantenimientoModal} onClose={() => setMantenimientoModal(false)} title="🛠️ Programar Mantenimiento por Franja Horaria">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cancha a intervenir</label>
            <select
              value={mantForm.cancha_id}
              onChange={e => setMantForm(f => ({ ...f, cancha_id: e.target.value }))}
              className="input-field"
            >
              <option value="">Selecciona una cancha...</option>
              {canchas.map(c => {
                const comp = complejos.find(cp => cp.id === c.complejo_id)
                return (
                  <option key={c.id} value={c.id}>
                    {c.nombre} ({comp?.nombre || 'Complejo'}) — {TIPO_LABELS[c.tipo]}
                  </option>
                )
              })}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Fecha del mantenimiento</label>
            <input
              type="date"
              value={mantForm.fecha}
              onChange={e => setMantForm(f => ({ ...f, fecha: e.target.value }))}
              className="input-field"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Hora Inicio</label>
              <select
                value={mantForm.hora_inicio}
                onChange={e => setMantForm(f => ({ ...f, hora_inicio: e.target.value }))}
                className="input-field"
              >
                {HOURS_OPCIONES.map(h => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Hora Fin</label>
              <select
                value={mantForm.hora_fin}
                onChange={e => setMantForm(f => ({ ...f, hora_fin: e.target.value }))}
                className="input-field"
              >
                {HOURS_FIN_OPCIONES.map(h => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Motivo / Tarea</label>
            <input
              type="text"
              value={mantForm.motivo}
              onChange={e => setMantForm(f => ({ ...f, motivo: e.target.value }))}
              placeholder="Ej: Mantenimiento césped sintético / cepillado"
              className="input-field"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={() => setMantenimientoModal(false)} className="btn-secondary flex-1">
              Cancelar
            </button>
            <button
              onClick={() => guardarMantenimiento()}
              disabled={guardandoMantenimiento}
              className="btn-primary flex-1 flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 border-amber-600"
            >
              {guardandoMantenimiento ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Guardar Mantenimiento
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
