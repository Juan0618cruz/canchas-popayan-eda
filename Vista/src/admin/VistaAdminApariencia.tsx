import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Palette, Upload, Link as LinkIcon, RotateCcw, Loader2,
  Building2, Image as ImageIcon, CheckCircle2, Trash2, Sparkles
} from 'lucide-react'
import { canchasApi, extractErrorMessage, TIPO_LABELS } from '../lib/api'
import {
  DEFAULT_GENERAL_BG,
  DEFAULT_SLOT_BG,
  resolveMediaUrl,
  useAppearanceStore,
} from '../store/appearanceStore'
import MiniCanchaSlot from '../components/MiniCanchaSlot'
import LoadingSpinner from '../components/LoadingSpinner'

export default function VistaAdminApariencia() {
  const queryClient = useQueryClient()
  const {
    fondoGeneralUrl,
    fondoSlotUrl,
    setAppearance,
    resetDefaults,
  } = useAppearanceStore()

  const [generalUrlInput, setGeneralUrlInput] = useState('')
  const [slotUrlInput, setSlotUrlInput] = useState('')
  const [complejoUrlInputs, setComplejoUrlInputs] = useState<Record<string, string>>({})
  const [canchaUrlInputs, setCanchaUrlInputs] = useState<Record<string, string>>({})
  const [uploadingKey, setUploadingKey] = useState<string | null>(null)
  const [statusMsg, setStatusMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const notify = (type: 'ok' | 'err', text: string) => {
    setStatusMsg({ type, text })
    setTimeout(() => setStatusMsg(null), 4000)
  }

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['complejos'] })
    queryClient.invalidateQueries({ queryKey: ['admin-canchas'] })
    queryClient.invalidateQueries({ queryKey: ['apariencia'] })
  }

  // Cargar complejos y canchas
  const { data: complejos = [], isLoading: loadingComplejos } = useQuery({
    queryKey: ['complejos'],
    queryFn: canchasApi.getComplejos,
  })

  const { data: canchas = [], isLoading: loadingCanchas } = useQuery({
    queryKey: ['admin-canchas'],
    queryFn: canchasApi.getMisCanchas,
  })

  // Guardar configuración general / slot en backend y store en tiempo real
  const { mutateAsync: guardarApariencia, isPending: guardandoApariencia } = useMutation({
    mutationFn: (payload: { fondo_general_url?: string | null; fondo_slot_url?: string | null }) =>
      canchasApi.updateApariencia(payload),
    onSuccess: (data) => {
      setAppearance({
        fondoGeneralUrl: data.fondo_general_url ?? DEFAULT_GENERAL_BG,
        fondoSlotUrl: data.fondo_slot_url ?? DEFAULT_SLOT_BG,
      })
      invalidateAll()
      notify('ok', 'Apariencia actualizada en tiempo real.')
    },
    onError: (err: unknown) => notify('err', extractErrorMessage(err, 'Error al actualizar apariencia.')),
  })

  // Restaurar diseño por defecto
  const { mutate: restaurarPorDefecto, isPending: restaurando } = useMutation({
    mutationFn: (limpiarTodos: boolean) => canchasApi.restaurarApariencia(limpiarTodos),
    onSuccess: () => {
      resetDefaults()
      setGeneralUrlInput('')
      setSlotUrlInput('')
      invalidateAll()
      notify('ok', 'Diseño de cancha sintética restaurado por defecto.')
    },
    onError: (err: unknown) => notify('err', extractErrorMessage(err, 'Error al restaurar diseño.')),
  })

  // Actualizar banner de un complejo
  const updateComplejoImagen = async (complejoId: string, imagenUrl: string | null) => {
    try {
      await canchasApi.updateComplejo(complejoId, { imagen_url: imagenUrl ?? '' })
      invalidateAll()
      notify('ok', imagenUrl ? 'Banner del complejo actualizado.' : 'Banner del complejo restaurado.')
    } catch (err: unknown) {
      notify('err', extractErrorMessage(err, 'No se pudo actualizar el banner del complejo.'))
    }
  }

  // Actualizar imagen de una cancha
  const updateCanchaImagen = async (canchaId: string, imagenUrl: string | null) => {
    try {
      await canchasApi.updateCancha(canchaId, { imagen_url: imagenUrl ?? '' })
      invalidateAll()
      notify('ok', imagenUrl ? 'Imagen de cancha actualizada.' : 'Imagen de cancha eliminada.')
    } catch (err: unknown) {
      notify('err', extractErrorMessage(err, 'No se pudo actualizar la imagen de la cancha.'))
    }
  }

  // Subida genérica de archivo al microservicio ms_canchas
  const handleFileUpload = async (
    file: File | undefined,
    key: string,
    onUrlReady: (uploadedUrl: string) => Promise<void>
  ) => {
    if (!file) return
    setUploadingKey(key)
    try {
      const res = await canchasApi.uploadBackgroundImage(file)
      await onUrlReady(res.url)
    } catch (err: unknown) {
      notify('err', extractErrorMessage(err, 'Error al subir la imagen. Verifica que sea JPG, PNG, WEBP o SVG.'))
    } finally {
      setUploadingKey(null)
    }
  }

  if (loadingComplejos || loadingCanchas) return <LoadingSpinner />

  const resolvedGeneral = resolveMediaUrl(fondoGeneralUrl, DEFAULT_GENERAL_BG)
  const resolvedSlot = resolveMediaUrl(fondoSlotUrl, DEFAULT_SLOT_BG)

  return (
    <div className="space-y-6">
      {/* Cabecera */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Palette className="text-green-600" size={22} />
            Apariencia y Fondos Personalizados
          </h2>
          <p className="text-sm text-gray-500">
            Personaliza el fondo general, la textura de las mini canchas en los horarios y los banners de cada complejo deportivo en tiempo real.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => restaurarPorDefecto(false)}
            disabled={restaurando}
            className="btn-secondary flex items-center gap-2 text-xs border-emerald-300 text-emerald-800 bg-emerald-50 hover:bg-emerald-100"
          >
            {restaurando ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
            Restaurar diseño de cancha por defecto
          </button>
          <button
            onClick={() => {
              if (window.confirm('¿Restaurar los fondos por defecto y quitar también todos los banners personalizados de complejos y canchas?')) {
                restaurarPorDefecto(true)
              }
            }}
            disabled={restaurando}
            className="btn-secondary flex items-center gap-1.5 text-xs text-gray-600"
          >
            <Trash2 size={14} /> Restablecer todo
          </button>
        </div>
      </div>

      {/* Mensaje de estado */}
      {statusMsg && (
        <div className={`px-4 py-3 rounded-xl border text-sm font-medium flex items-center gap-2 ${
          statusMsg.type === 'ok'
            ? 'bg-green-50 border-green-200 text-green-800'
            : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          {statusMsg.type === 'ok' && <CheckCircle2 size={16} />}
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* Sección 1 y 2: Fondo General y Fondo de Mini Canchas */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* 1) Fondo General de la Aplicación */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-gray-900 flex items-center gap-2">
                <Sparkles size={16} className="text-emerald-600" />
                1. Fondo General de la Plataforma
              </h3>
              <p className="text-xs text-gray-500">Se muestra detrás del catálogo de canchas y en la portada principal.</p>
            </div>
            <button
              type="button"
              onClick={() => guardarApariencia({ fondo_general_url: DEFAULT_GENERAL_BG })}
              className="text-xs text-emerald-700 hover:underline font-medium"
            >
              Usar SVG Estadio
            </button>
          </div>

          {/* Vista Previa */}
          <div
            className="h-36 w-full rounded-xl border border-gray-200 overflow-hidden relative flex items-end p-3 bg-cover bg-center bg-no-repeat app-banner-bg"
            style={{
              backgroundImage: `url("${resolvedGeneral}")`,
              backgroundColor: '#064e3b',
            }}
          >
            <span className="text-xs text-gray-900 font-semibold bg-white border border-gray-200 px-2.5 py-1 rounded-lg shadow-sm">
              Vista previa del fondo general (nitidez original)
            </span>
          </div>

          {/* Subir archivo */}
          <div className="space-y-3">
            <label className="flex items-center justify-center gap-2 w-full py-2.5 px-4 border-2 border-dashed border-emerald-300 rounded-xl bg-emerald-50/60 hover:bg-emerald-50 text-emerald-800 text-xs font-semibold cursor-pointer transition-colors">
              {uploadingKey === 'general' ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
              <span>Subir imagen desde tu computador (JPG, PNG, WEBP, SVG)</span>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.svg,image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  handleFileUpload(f, 'general', async (url) => {
                    await guardarApariencia({ fondo_general_url: url })
                  })
                  e.target.value = ''
                }}
              />
            </label>

            {/* Pegar URL */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <LinkIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="url"
                  value={generalUrlInput}
                  onChange={(e) => setGeneralUrlInput(e.target.value)}
                  placeholder="O pega una URL de imagen (https://...)"
                  className="input-field pl-8 text-xs"
                />
              </div>
              <button
                type="button"
                disabled={!generalUrlInput.trim() || guardandoApariencia}
                onClick={async () => {
                  await guardarApariencia({ fondo_general_url: generalUrlInput.trim() })
                  setGeneralUrlInput('')
                }}
                className="btn-primary text-xs px-3 py-2"
              >
                Aplicar URL
              </button>
            </div>
          </div>
        </div>

        {/* 2) Fondo de Casillas de Reserva (Mini Canchas) */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-gray-900 flex items-center gap-2">
                ⚽ 2. Fondo de Casillas (Mini Canchas)
              </h3>
              <p className="text-xs text-gray-500">Textura cenital usada en los bloques horarios del catálogo.</p>
            </div>
            <button
              type="button"
              onClick={() => guardarApariencia({ fondo_slot_url: DEFAULT_SLOT_BG })}
              className="text-xs text-emerald-700 hover:underline font-medium"
            >
              Usar SVG Cancha
            </button>
          </div>

          {/* Vista Previa en Vivo de los 3 estados */}
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
            <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2.5">
              Vista previa en tiempo real (Catálogo)
            </p>
            <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto">
              <div className="w-24">
                <MiniCanchaSlot
                  horaInicio="18:00"
                  tarifa={70000}
                  estado="LIBRE"
                  slotBgUrl={resolvedSlot}
                />
              </div>
              <div className="w-24">
                <MiniCanchaSlot
                  horaInicio="19:00"
                  tarifa={70000}
                  estado="OCUPADO"
                  slotBgUrl={resolvedSlot}
                />
              </div>
              <div className="w-24">
                <MiniCanchaSlot
                  horaInicio="20:00"
                  tarifa={70000}
                  estado="MANTENIMIENTO"
                  slotBgUrl={resolvedSlot}
                />
              </div>
            </div>
          </div>

          {/* Subir archivo */}
          <div className="space-y-3">
            <label className="flex items-center justify-center gap-2 w-full py-2.5 px-4 border-2 border-dashed border-emerald-300 rounded-xl bg-emerald-50/60 hover:bg-emerald-50 text-emerald-800 text-xs font-semibold cursor-pointer transition-colors">
              {uploadingKey === 'slot' ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
              <span>Subir textura de cancha (JPG, PNG, WEBP, SVG)</span>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.svg,image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  handleFileUpload(f, 'slot', async (url) => {
                    await guardarApariencia({ fondo_slot_url: url })
                  })
                  e.target.value = ''
                }}
              />
            </label>

            {/* Pegar URL */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <LinkIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="url"
                  value={slotUrlInput}
                  onChange={(e) => setSlotUrlInput(e.target.value)}
                  placeholder="O pega una URL para las casillas (https://...)"
                  className="input-field pl-8 text-xs"
                />
              </div>
              <button
                type="button"
                disabled={!slotUrlInput.trim() || guardandoApariencia}
                onClick={async () => {
                  await guardarApariencia({ fondo_slot_url: slotUrlInput.trim() })
                  setSlotUrlInput('')
                }}
                className="btn-primary text-xs px-3 py-2"
              >
                Aplicar URL
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Sección 3: Banners por Complejo Deportivo */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-4">
        <div>
          <h3 className="font-bold text-gray-900 flex items-center gap-2">
            <Building2 size={18} className="text-blue-600" />
            3. Banner de Encabezado por Complejo Deportivo
          </h3>
          <p className="text-xs text-gray-500">
            Personaliza la imagen de encabezado de cada sede (Balón de Oro, Bernabéu, etc.) visible en el catálogo.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          {complejos.map((comp) => {
            const bannerUrl = resolveMediaUrl(comp.imagen_url, resolvedGeneral)
            const inputVal = complejoUrlInputs[comp.id] || ''
            return (
              <div key={comp.id} className="border border-gray-200 rounded-xl overflow-hidden bg-gray-50/50">
                <div
                  className="px-4 py-4 text-white relative bg-cover bg-center bg-no-repeat app-banner-bg"
                  style={{
                    backgroundImage: `linear-gradient(95deg, rgba(6, 78, 59, 0.90), rgba(5, 46, 22, 0.72)), url("${bannerUrl}")`,
                  }}
                >
                  <p className="font-bold text-sm drop-shadow">{comp.nombre}</p>
                  <p className="text-[11px] text-emerald-100">{comp.direccion} · {comp.barrio}</p>
                </div>

                <div className="p-3.5 space-y-2.5">
                  <div className="flex items-center gap-2">
                    <label className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 border border-emerald-300 rounded-lg bg-white hover:bg-emerald-50 text-emerald-800 text-xs font-semibold cursor-pointer transition-colors">
                      {uploadingKey === `comp-${comp.id}` ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                      <span>Subir Banner</span>
                      <input
                        type="file"
                        accept=".jpg,.jpeg,.png,.webp,.svg,image/*"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          handleFileUpload(f, `comp-${comp.id}`, async (url) => {
                            await updateComplejoImagen(comp.id, url)
                          })
                          e.target.value = ''
                        }}
                      />
                    </label>
                    {comp.imagen_url && (
                      <button
                        type="button"
                        onClick={() => updateComplejoImagen(comp.id, null)}
                        className="py-2 px-2.5 text-xs rounded-lg border border-gray-300 bg-white hover:bg-gray-100 text-gray-600"
                        title="Volver al banner por defecto"
                      >
                        <RotateCcw size={14} />
                      </button>
                    )}
                  </div>

                  <div className="flex gap-1.5">
                    <input
                      type="url"
                      value={inputVal}
                      onChange={(e) => setComplejoUrlInputs(prev => ({ ...prev, [comp.id]: e.target.value }))}
                      placeholder="URL de imagen del complejo..."
                      className="input-field text-xs py-1.5"
                    />
                    <button
                      type="button"
                      disabled={!inputVal.trim()}
                      onClick={async () => {
                        await updateComplejoImagen(comp.id, inputVal.trim())
                        setComplejoUrlInputs(prev => ({ ...prev, [comp.id]: '' }))
                      }}
                      className="btn-primary text-xs px-2.5 py-1.5"
                    >
                      Aplicar
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Sección 4: Imágenes Individuales por Cancha */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-4">
        <div>
          <h3 className="font-bold text-gray-900 flex items-center gap-2">
            <ImageIcon size={18} className="text-emerald-600" />
            4. Foto Individual por Cancha Sintética
          </h3>
          <p className="text-xs text-gray-500">
            Sube una fotografía o imagen representativa para cada cancha específica; aparecerá en el catálogo junto a sus características.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {canchas.map((cancha) => {
            const comp = complejos.find(cp => cp.id === cancha.complejo_id)
            const imgResolved = cancha.imagen_url ? resolveMediaUrl(cancha.imagen_url) : ''
            const urlVal = canchaUrlInputs[cancha.id] || ''
            return (
              <div key={cancha.id} className="border border-gray-200 rounded-xl p-3.5 bg-gray-50/50 space-y-3">
                <div className="flex items-center gap-3">
                  {imgResolved ? (
                    <img
                      src={imgResolved}
                      alt={cancha.nombre}
                      className="w-14 h-14 rounded-xl object-cover border border-emerald-200 shrink-0"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center text-xl shrink-0">
                      ⚽
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="font-bold text-xs text-gray-900 truncate">{cancha.nombre}</p>
                    <p className="text-[11px] text-gray-500 truncate">{comp?.nombre || 'Complejo'}</p>
                    <span className="badge bg-blue-100 text-blue-700 text-[10px] mt-0.5">
                      {TIPO_LABELS[cancha.tipo]}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <label className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 border border-emerald-300 rounded-lg bg-white hover:bg-emerald-50 text-emerald-800 text-xs font-semibold cursor-pointer">
                    {uploadingKey === `cancha-${cancha.id}` ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                    <span>Subir Foto</span>
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.svg,image/*"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        handleFileUpload(f, `cancha-${cancha.id}`, async (url) => {
                          await updateCanchaImagen(cancha.id, url)
                        })
                        e.target.value = ''
                      }}
                    />
                  </label>
                  {cancha.imagen_url && (
                    <button
                      type="button"
                      onClick={() => updateCanchaImagen(cancha.id, null)}
                      className="py-1.5 px-2 text-xs rounded-lg border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
                      title="Quitar foto"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>

                <div className="flex gap-1.5">
                  <input
                    type="url"
                    value={urlVal}
                    onChange={(e) => setCanchaUrlInputs(prev => ({ ...prev, [cancha.id]: e.target.value }))}
                    placeholder="URL foto cancha..."
                    className="input-field text-xs py-1"
                  />
                  <button
                    type="button"
                    disabled={!urlVal.trim()}
                    onClick={async () => {
                      await updateCanchaImagen(cancha.id, urlVal.trim())
                      setCanchaUrlInputs(prev => ({ ...prev, [cancha.id]: '' }))
                    }}
                    className="btn-secondary text-xs px-2 py-1"
                  >
                    OK
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
