import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const DEFAULT_GENERAL_BG = '/assets/backgrounds/hero-stadium-bg.svg'
export const DEFAULT_SLOT_BG = '/assets/backgrounds/cancha-slot-bg.svg'
function getApiBase(): string {
  if (typeof window !== 'undefined' && window.location) {
    const { hostname, protocol } = window.location
    if (hostname && hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return `${protocol}//${hostname}:8000`
    }
  }
  return 'http://localhost:8000'
}

const API_BASE = getApiBase()

export function resolveMediaUrl(url?: string | null, fallback?: string): string {
  const value = url && url.trim() ? url.trim() : (fallback || '')
  if (!value) return ''
  if (value.startsWith('/canchas/')) {
    return `${API_BASE}${value}`
  }
  return value
}

interface AppearanceState {
  fondoGeneralUrl: string
  fondoSlotUrl: string
  setAppearance: (partial: { fondoGeneralUrl?: string | null; fondoSlotUrl?: string | null }) => void
  resetDefaults: () => void
}

export const useAppearanceStore = create<AppearanceState>()(
  persist(
    (set) => ({
      fondoGeneralUrl: DEFAULT_GENERAL_BG,
      fondoSlotUrl: DEFAULT_SLOT_BG,
      setAppearance: (partial) =>
        set((state) => ({
          fondoGeneralUrl: partial.fondoGeneralUrl !== undefined
            ? (partial.fondoGeneralUrl || DEFAULT_GENERAL_BG)
            : state.fondoGeneralUrl,
          fondoSlotUrl: partial.fondoSlotUrl !== undefined
            ? (partial.fondoSlotUrl || DEFAULT_SLOT_BG)
            : state.fondoSlotUrl,
        })),
      resetDefaults: () =>
        set({
          fondoGeneralUrl: DEFAULT_GENERAL_BG,
          fondoSlotUrl: DEFAULT_SLOT_BG,
        }),
    }),
    { name: 'canchas-appearance' }
  )
)
