import { useState } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, Phone, Mail, ChevronRight, ShieldCheck, X } from 'lucide-react'
import { useAuthStore } from '../store/authStore'

function SoccerBallIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-5 h-5 text-white"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="9.5" />
      <polygon points="12 7.5 16 10.4 14.5 15 9.5 15 8 10.4" fill="currentColor" fillOpacity="0.25" />
      <line x1="12" y1="2.5" x2="12" y2="7.5" />
      <line x1="21" y1="9" x2="16" y2="10.4" />
      <line x1="17.6" y1="19.6" x2="14.5" y2="15" />
      <line x1="6.4" y1="19.6" x2="9.5" y2="15" />
      <line x1="3" y1="9" x2="8" y2="10.4" />
    </svg>
  )
}

export default function Footer() {
  const [legalModal, setLegalModal] = useState<'privacidad' | 'terminos' | null>(null)
  const { isAuthenticated, user } = useAuthStore()
  const isAdmin = isAuthenticated && (user?.rol === 'ADMIN_ESTABLECIMIENTO' || user?.rol?.toLowerCase() === 'admin')

  return (
    <footer className="bg-white text-gray-600 border-t border-gray-200 relative z-10 shadow-[0_-4px_20px_-6px_rgba(0,0,0,0.06)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-10">
          {/* Columna 1: Marca y Misión */}
          <div className="space-y-4">
            <Link to="/" className="inline-flex items-center gap-3 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-700 flex items-center justify-center shadow-sm shadow-emerald-600/25 group-hover:scale-105 transition-transform">
                <SoccerBallIcon />
              </div>
              <div className="flex flex-col leading-none">
                <span className="text-lg font-extrabold tracking-tight text-gray-900">
                  Canchas <span className="text-emerald-600">Popayán</span>
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-gray-500 mt-1">
                  Complejos Sintéticos
                </span>
              </div>
            </Link>

            <p className="text-sm text-gray-600 leading-relaxed">
              La plataforma líder para la reserva de canchas sintéticas y gestión deportiva en Popayán. Disponibilidad en tiempo real, pagos seguros y confirmación inmediata.
            </p>

            <div className="inline-flex items-center gap-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-1.5 font-medium">
              <MapPin size={13} className="shrink-0 text-emerald-600" />
              <span>Popayán, Cauca · 8:00 a.m. – 10:00 p.m.</span>
            </div>
          </div>

          {/* Columna 2: Complejos Deportivos y Contacto */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-2">
              <span className="w-1.5 h-4 rounded-full bg-emerald-600 inline-block" />
              Complejos y Contacto
            </h3>

            <div className="space-y-3 text-sm">
              <div className="bg-gray-50 border border-gray-200/80 rounded-xl p-3 space-y-1">
                <p className="font-semibold text-gray-900 text-xs">Complejo Deportivo Balón de Oro</p>
                <p className="text-xs text-gray-600 flex items-center gap-1.5">
                  <MapPin size={12} className="text-emerald-600 shrink-0" />
                  Carrera 15 # 12-45, San José
                </p>
                <a
                  href="tel:+573001234567"
                  className="text-xs text-emerald-700 hover:text-emerald-600 font-semibold flex items-center gap-1.5 pt-0.5 transition-colors"
                >
                  <Phone size={12} className="shrink-0" />
                  Tel: +57 300 1234567
                </a>
              </div>

              <div className="bg-gray-50 border border-gray-200/80 rounded-xl p-3 space-y-1">
                <p className="font-semibold text-gray-900 text-xs">Complejo Sintético Bernabéu</p>
                <p className="text-xs text-gray-600 flex items-center gap-1.5">
                  <MapPin size={12} className="text-emerald-600 shrink-0" />
                  Vía Julumito Km 2, Julumito
                </p>
                <a
                  href="tel:+573119876543"
                  className="text-xs text-emerald-700 hover:text-emerald-600 font-semibold flex items-center gap-1.5 pt-0.5 transition-colors"
                >
                  <Phone size={12} className="shrink-0" />
                  Tel: +57 311 9876543
                </a>
              </div>

              <a
                href="mailto:soporte@canchaspopayan.co"
                className="inline-flex items-center gap-2 text-xs text-gray-600 hover:text-emerald-600 font-medium transition-colors pt-1"
              >
                <Mail size={13} className="text-emerald-600" />
                soporte@canchaspopayan.co
              </a>
            </div>
          </div>

          {/* Columna 3: Enlaces Rápidos */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-2">
              <span className="w-1.5 h-4 rounded-full bg-emerald-600 inline-block" />
              Enlaces Rápidos
            </h3>

            <ul className="space-y-2.5 text-sm">
              {[
                { label: 'Catálogo de Canchas', to: '/catalogo' },
                ...(isAdmin ? [
                  { label: 'Reportes', to: '/reportes' },
                  { label: 'Portal Admin', to: '/admin/taquilla' },
                ] : []),
                ...(isAuthenticated && !isAdmin ? [{ label: 'Mis Reservas', to: '/mis-reservas' }] : []),
              ].map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="inline-flex items-center gap-1.5 text-gray-600 hover:text-emerald-600 font-medium transition-colors group"
                  >
                    <ChevronRight size={14} className="text-emerald-600/80 group-hover:translate-x-0.5 transition-transform" />
                    <span>{item.label}</span>
                  </Link>
                </li>
              ))}
              <li>
                <a
                  href="mailto:soporte@canchaspopayan.co?subject=Soporte%20Canchas%20Popay%C3%A1n"
                  className="inline-flex items-center gap-1.5 text-gray-600 hover:text-emerald-600 font-medium transition-colors group"
                >
                  <ChevronRight size={14} className="text-emerald-600/80 group-hover:translate-x-0.5 transition-transform" />
                  <span>Soporte</span>
                </a>
              </li>
            </ul>
          </div>

          {/* Columna 4: Redes y Legal */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-2">
              <span className="w-1.5 h-4 rounded-full bg-emerald-600 inline-block" />
              Redes y Legal
            </h3>

            <p className="text-xs text-gray-600 leading-relaxed">
              Síguenos para enterarte de torneos relámpago, horarios nocturnos y promociones especiales en Popayán.
            </p>

            {/* Redes Sociales */}
            <div className="flex items-center gap-2.5">
              <a
                href="https://instagram.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Instagram"
                title="Instagram"
                className="w-10 h-10 rounded-xl bg-gray-50 border border-gray-200 flex items-center justify-center text-gray-600 hover:border-emerald-400 hover:bg-emerald-50 hover:text-emerald-600 transition-all"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect width="20" height="20" x="2" y="2" rx="5" ry="5" />
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                  <line x1="17.5" x2="17.51" y1="6.5" y2="6.5" />
                </svg>
              </a>

              <a
                href="https://wa.me/573001234567"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="WhatsApp"
                title="WhatsApp"
                className="w-10 h-10 rounded-xl bg-gray-50 border border-gray-200 flex items-center justify-center text-gray-600 hover:border-emerald-400 hover:bg-emerald-50 hover:text-emerald-600 transition-all"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                </svg>
              </a>

              <a
                href="https://facebook.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Facebook"
                title="Facebook"
                className="w-10 h-10 rounded-xl bg-gray-50 border border-gray-200 flex items-center justify-center text-gray-600 hover:border-emerald-400 hover:bg-emerald-50 hover:text-emerald-600 transition-all"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
                </svg>
              </a>
            </div>

            {/* Enlaces Legales */}
            <div className="pt-2 space-y-1.5 text-xs">
              <button
                type="button"
                onClick={() => setLegalModal('privacidad')}
                className="block text-gray-600 hover:text-emerald-600 font-medium transition-colors"
              >
                Política de Privacidad
              </button>
              <button
                type="button"
                onClick={() => setLegalModal('terminos')}
                className="block text-gray-600 hover:text-emerald-600 font-medium transition-colors"
              >
                Términos y Condiciones
              </button>
            </div>
          </div>
        </div>

        {/* Línea divisoria y Copyright */}
        <div className="mt-10 pt-6 border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500">
          <p>© 2026 Canchas Popayán EDA. Todos los derechos reservados.</p>
          <div className="flex items-center gap-1.5 text-gray-600 font-medium">
            <ShieldCheck size={14} className="text-emerald-600" />
            <span>Plataforma deportiva · Popayán, Cauca</span>
          </div>
        </div>
      </div>

      {/* Modal informativo legal */}
      {legalModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white text-gray-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-100">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-bold text-lg text-gray-900">
                {legalModal === 'privacidad' ? 'Política de Privacidad' : 'Términos y Condiciones'}
              </h4>
              <button
                type="button"
                onClick={() => setLegalModal(null)}
                className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={18} />
              </button>
            </div>
            <div className="text-sm text-gray-600 space-y-2 leading-relaxed">
              {legalModal === 'privacidad' ? (
                <>
                  <p>
                    En <strong>Canchas Popayán EDA</strong> protegemos tus datos personales conforme a la Ley 1581 de 2012 (Habeas Data - Colombia).
                  </p>
                  <p>
                    Tu nombre, correo y teléfono se utilizan exclusivamente para gestionar reservas deportivas, comprobantes de pago y notificaciones de disponibilidad en Popayán.
                  </p>
                </>
              ) : (
                <>
                  <p>
                    Las reservas confirmadas garantizan el uso exclusivo de la cancha sintética seleccionada durante la franja horaria de 60 minutos reservada.
                  </p>
                  <p>
                    Se permite cancelar o reprogramar sin penalidad hasta 2 horas antes del inicio del partido. En caso de mantenimiento programado, se notificará al usuario de forma inmediata.
                  </p>
                </>
              )}
            </div>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setLegalModal(null)}
                className="btn-primary text-sm px-5 py-2"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </footer>
  )
}
