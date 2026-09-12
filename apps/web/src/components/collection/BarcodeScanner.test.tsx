import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import BarcodeScanner from './BarcodeScanner'
import { hasProductCodeLength, normaliseProductCode } from '@/lib/barcode'

describe('BarcodeScanner', () => {
  it('offers both the mobile camera and the typed fallback', () => {
    const html = renderToStaticMarkup(<BarcodeScanner onDetected={() => {}} />)

    expect(html).toContain('Open camera')
    expect(html).toContain('Or type the digits')
    expect(html).toContain('inputMode="numeric"')
    expect(html).toContain('playsinline=""')
  })

  it('normalises scanner decoration but accepts only retail-code lengths', () => {
    expect(normaliseProductCode('EAN 5-051892-211475')).toBe('5051892211475')
    expect(hasProductCodeLength('96385074')).toBe(true)
    expect(hasProductCodeLength('883929665495')).toBe(true)
    expect(hasProductCodeLength('5051892211475')).toBe(true)
    expect(hasProductCodeLength('5051892211')).toBe(false)
  })
})
