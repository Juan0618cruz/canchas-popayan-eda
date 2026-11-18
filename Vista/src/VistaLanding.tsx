/**
 * Capa MVC: Vista — VistaLanding.tsx
 * Vista pública principal de presentación de la plataforma Canchas Popayán.
 */

import { Link } from 'react-router-dom'
import { Clock, Shield, RotateCcw, MapPin, Star } from 'lucide-react'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import PageBackground from './components/PageBackground'
import { DEFAULT_GENERAL_BG, resolveMediaUrl, useAppearanceStore } from './store/appearanceStore'

export default function VistaLanding() {
  const { fondoGeneralUrl } = useAppearanceStore()
  const resolvedHeroBg = resolveMediaUrl(fondoGeneralUrl, DEFAULT_GENERAL_BG)

  return (
    <PageBackground imageUrl={resolvedHeroBg}>
      <Navbar />

      {/* Sección Hero principal */}
      <section className="relative bg-transparent text-white overflow-hidden min-h-[85vh] lg:min-h-[90vh] flex flex-col justify-center">
        <div className="relative max-w-5xl mx-auto px-6 py-14 sm:py-20 lg:py-24 text-center drop-shadow-[0_2px_10px_rgba(0,0,0,0.65)] my-auto w-full">
          <div className="inline-flex items-center gap-2 bg-white/20 backdrop-blur rounded-full px-4 py-2 text-sm font-medium mb-6">
            <MapPin size={14} /> Popayán, Cauca — Colombia
          </div>
          <h1 className="text-4xl md:text-6xl font-extrabold mb-4 leading-tight">
            Reserva tu Cancha<br />
            <span className="text-green-200">en Popayán</span>
          </h1>
          <p className="text-lg md:text-xl text-green-100 mb-8 max-w-2xl mx-auto">
            2 complejos deportivos · Fútbol 5, 7 y 8 · Reserva en segundos · Pago en línea
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/catalogo"
              className="bg-white text-green-700 font-bold px-8 py-4 rounded-xl text-lg hover:bg-green-50 transition-colors shadow-lg">
              Ver Canchas Disponibles →
            </Link>
            <Link to="/login"
              className="border-2 border-white text-white font-bold px-8 py-4 rounded-xl text-lg hover:bg-white/10 transition-colors">
              Iniciar Sesión
            </Link>
          </div>
        </div>
      </section>

      {/* Características del servicio */}
      <section className="max-w-5xl mx-auto px-6 py-16 bg-transparent">
        <div className="text-center mb-10">
          <h2 className="inline-block text-2xl font-bold text-gray-900 bg-white px-6 py-2.5 rounded-2xl shadow-md border border-gray-100">
            ¿Por qué Canchas Popayán?
          </h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: <Clock size={32} className="text-green-600" />, title: 'Reserva Online 24/7', desc: 'Reserva tu cancha favorita a cualquier hora, desde cualquier dispositivo.' },
            { icon: <Shield size={32} className="text-green-600" />, title: 'Pago Seguro', desc: 'Integración con Wompi y Bre-B. Tus transacciones 100% protegidas.' },
            { icon: <RotateCcw size={32} className="text-green-600" />, title: 'Cancela si necesitas', desc: 'Cancela gratis hasta 2 horas antes del partido sin complicaciones.' },
          ].map((f, i) => (
            <div key={i} className="card text-center">
              <div className="flex justify-center mb-4">{f.icon}</div>
              <h3 className="font-bold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Vista previa de complejos deportivos */}
      <section className="bg-white py-16">
        <div className="max-w-5xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-gray-800 mb-8 text-center">Nuestros Complejos</h2>
          <div className="grid md:grid-cols-2 gap-6">
            {[
              {
                nombre: 'Complejo Deportivo Balón de Oro',
                barrio: 'Barrio San José',
                canchas: 'Fútbol 5, 7 y 8',
                desde: '$50.000',
                emoji: '🥇',
                color: 'green',
              },
              {
                nombre: 'Complejo Sintético Bernabéu',
                barrio: 'Julumito',
                canchas: 'Fútbol 5, 7 y 8',
                desde: '$60.000',
                emoji: '🏟️',
                color: 'emerald',
              },
            ].map((c, i) => (
              <div key={i} className="rounded-2xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
                <div className={`bg-gradient-to-r from-${c.color}-600 to-${c.color}-500 p-8 text-center text-white`}>
                  <div className="text-5xl mb-2">{c.emoji}</div>
                  <h3 className="text-xl font-bold">{c.nombre}</h3>
                  <div className="flex items-center justify-center gap-1 mt-2 text-sm opacity-90">
                    <MapPin size={12} /> {c.barrio}, Popayán
                  </div>
                </div>
                <div className="p-5">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-sm text-gray-500">Modalidades</span>
                    <span className="font-semibold text-gray-800">{c.canchas}</span>
                  </div>
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-sm text-gray-500">Desde</span>
                    <span className="font-bold text-green-700 text-lg">{c.desde} COP/hora</span>
                  </div>
                  <div className="flex items-center gap-1 text-yellow-500 mb-4">
                    {[1,2,3,4,5].map(s => <Star key={s} size={14} fill="currentColor" />)}
                    <span className="text-xs text-gray-400 ml-1">5.0 · Horario 8:00–22:00</span>
                  </div>
                  <Link to="/catalogo" className="btn-primary w-full text-center block">
                    Ver disponibilidad →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Footer />
    </PageBackground>
  )
}
