import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import BarcodeLookupPanel from './BarcodeLookupPanel'

describe('BarcodeLookupPanel', () => {
  it('starts with an explicit camera action and manual-code fallback', () => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const html = renderToStaticMarkup(
      <QueryClientProvider client={client}>
        <BarcodeLookupPanel
          onConfirmed={async () => {}}
          onManualSearch={() => {}}
          onBarcodeChange={() => {}}
        />
      </QueryClientProvider>,
    )

    expect(html).toContain('Open camera')
    expect(html).toContain('Or type the digits')
    // Camera permission is requested only from a click; the initial render never opens it.
    expect(html).not.toContain('Looking for an EAN or UPC')
  })
})
