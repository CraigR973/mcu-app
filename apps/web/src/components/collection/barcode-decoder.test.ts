import {
  BarcodeFormat,
  BinaryBitmap,
  DecodeHintType,
  HybridBinarizer,
  MultiFormatReader,
  RGBLuminanceSource,
} from '@zxing/library'
import { describe, expect, it } from 'vitest'

const LEFT_ODD = [
  '0001101',
  '0011001',
  '0010011',
  '0111101',
  '0100011',
  '0110001',
  '0101111',
  '0111011',
  '0110111',
  '0001011',
]

const LEFT_EVEN = [
  '0100111',
  '0110011',
  '0011011',
  '0100001',
  '0011101',
  '0111001',
  '0000101',
  '0010001',
  '0001001',
  '0010111',
]

const RIGHT = [
  '1110010',
  '1100110',
  '1101100',
  '1000010',
  '1011100',
  '1001110',
  '1010000',
  '1000100',
  '1001000',
  '1110100',
]

const PARITY = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL']

/** A deterministic EAN-13 fixture as raw image pixels, including a ten-module quiet zone. */
function ean13Image(code: string): { pixels: Uint8ClampedArray; width: number; height: number } {
  const digits = [...code].map(Number)
  const left = digits
    .slice(1, 7)
    .map((digit, index) => (PARITY[digits[0]][index] === 'L' ? LEFT_ODD : LEFT_EVEN)[digit])
    .join('')
  const right = digits.slice(7).map((digit) => RIGHT[digit]).join('')
  const modules = `0000000000${`101${left}01010${right}101`}0000000000`
  const scale = 4
  const width = modules.length * scale
  const height = 140
  const pixels = new Uint8ClampedArray(width * height)
  pixels.fill(255)

  for (let y = 10; y < height - 10; y += 1) {
    for (let module = 0; module < modules.length; module += 1) {
      if (modules[module] !== '1') continue
      const start = y * width + module * scale
      pixels.fill(0, start, start + scale)
    }
  }
  return { pixels, width, height }
}

describe('the pinned ZXing decoder', () => {
  it('decodes a real EAN-13 value from image pixels', () => {
    const fixture = ean13Image('5051892211475')
    const bitmap = new BinaryBitmap(
      new HybridBinarizer(
        new RGBLuminanceSource(fixture.pixels, fixture.width, fixture.height),
      ),
    )
    const hints = new Map()
    hints.set(DecodeHintType.POSSIBLE_FORMATS, [BarcodeFormat.EAN_13])

    const result = new MultiFormatReader().decode(bitmap, hints)

    expect(result.getText()).toBe('5051892211475')
    expect(result.getBarcodeFormat()).toBe(BarcodeFormat.EAN_13)
  })
})
