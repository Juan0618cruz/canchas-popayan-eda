import React from 'react'
import { resolveMediaUrl, DEFAULT_GENERAL_BG, useAppearanceStore } from '../store/appearanceStore'

interface PageBackgroundProps {
  imageUrl?: string
  className?: string
  children?: React.ReactNode
}

/**
 * Componente unificado de fondo responsivo y proporcional para toda la aplicación.
 * Garantiza que la imagen llene el espacio de forma fluida y simétrica (bg-cover bg-center bg-no-repeat w-full h-full)
 * sin estirarse, sin cortes visuales y sin zoom gigantesco en dispositivos móviles.
 */
export default function PageBackground({
  imageUrl,
  className = '',
  children,
}: PageBackgroundProps) {
  const { fondoGeneralUrl } = useAppearanceStore()
  const resolvedBg = resolveMediaUrl(imageUrl || fondoGeneralUrl, DEFAULT_GENERAL_BG)

  return (
    <div className={`min-h-screen w-full flex flex-col relative bg-transparent overflow-x-hidden ${className}`}>
      {/* Capa de fondo fija y proporcional: 100% de la ventana sin distorsión ni saltos */}
      <div
        className="fixed inset-0 z-0 h-full w-full bg-cover bg-center bg-no-repeat pointer-events-none"
        style={{
          backgroundImage: `url("${resolvedBg}")`,
          backgroundColor: '#064e3b',
        }}
      />

      {/* Contenedor del contenido en plano superior */}
      <div className="relative z-10 flex-1 flex flex-col w-full">
        {children}
      </div>
    </div>
  )
}
