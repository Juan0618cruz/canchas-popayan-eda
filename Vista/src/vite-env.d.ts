/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WOMPI_PUBLIC_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface WompiWidgetTransaction {
  id: string
  reference?: string
  status: string
  paymentMethodType?: string
  amountInCents?: number
}

interface WompiWidgetResult {
  transaction?: WompiWidgetTransaction
}

interface WompiWidgetOptions {
  currency: 'COP'
  amountInCents: number
  reference: string
  publicKey: string
  signature?: { integrity: string }
  customerData?: {
    email?: string
    fullName?: string
  }
}

interface WompiWidgetCheckoutInstance {
  open: (callback: (result: WompiWidgetResult) => void) => void
}

interface Window {
  WidgetCheckout?: new (options: WompiWidgetOptions) => WompiWidgetCheckoutInstance
}
