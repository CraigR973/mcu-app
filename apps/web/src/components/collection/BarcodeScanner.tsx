import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, Keyboard, ScanLine, Square } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { hasProductCodeLength, normaliseProductCode } from '@/lib/barcode'

type ScannerStatus = 'idle' | 'starting' | 'scanning' | 'detected'

interface Props {
  onDetected: (barcode: string) => void
  disabled?: boolean
}

interface ResettableReader {
  reset: () => void
}

function cameraErrorMessage(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
      return 'Camera access was blocked. Allow it in your browser settings, or type the barcode below.'
    }
    if (error.name === 'NotFoundError' || error.name === 'OverconstrainedError') {
      return 'No usable camera was found. You can type the barcode below instead.'
    }
    if (error.name === 'NotReadableError') {
      return 'The camera is being used by another app. Close it there and try again.'
    }
  }
  return 'The camera could not start. You can type the barcode below instead.'
}

/**
 * Phase 3.3's mobile camera path.
 *
 * The ZXing chunk is loaded only after the person asks to scan: most visits to the add
 * page use title search, and a camera decoder should not sit in that route's initial
 * bundle. The reader is also constrained to retail product codes, so a QR code on the
 * same sleeve cannot accidentally enter the UPC lookup chain.
 */
export default function BarcodeScanner({ onDetected, disabled = false }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const readerRef = useRef<ResettableReader | null>(null)
  const attemptRef = useRef(0)
  const [status, setStatus] = useState<ScannerStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [manualCode, setManualCode] = useState('')
  const digits = normaliseProductCode(manualCode)

  const releaseCamera = useCallback(() => {
    try {
      readerRef.current?.reset()
    } catch {
      // ZXing can throw while resetting a stream that the browser already ended. The
      // tracks below are the actual resource, so cleanup still completes.
    }
    readerRef.current = null

    const stream = videoRef.current?.srcObject
    if (typeof MediaStream !== 'undefined' && stream instanceof MediaStream) {
      for (const track of stream.getTracks()) track.stop()
    }
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  const stopCamera = useCallback(() => {
    attemptRef.current += 1
    releaseCamera()
    setStatus('idle')
  }, [releaseCamera])

  useEffect(
    () => () => {
      attemptRef.current += 1
      releaseCamera()
    },
    [releaseCamera],
  )

  async function startCamera() {
    setError(null)
    releaseCamera()

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('This browser cannot use the camera here. You can type the barcode below instead.')
      return
    }

    const attempt = ++attemptRef.current
    setStatus('starting')

    try {
      // Conditional by design: ZXing is needed only after this click.
      const { BarcodeFormat, BrowserMultiFormatReader, DecodeHintType } = await import(
        '@zxing/library'
      )
      if (attempt !== attemptRef.current) return

      const video = videoRef.current
      if (!video) throw new Error('Camera preview is unavailable')

      const hints = new Map()
      hints.set(DecodeHintType.POSSIBLE_FORMATS, [
        BarcodeFormat.EAN_8,
        BarcodeFormat.EAN_13,
        BarcodeFormat.UPC_A,
      ])
      const reader = new BrowserMultiFormatReader(hints, 100)
      readerRef.current = reader
      setStatus('scanning')

      await reader.decodeFromConstraints(
        {
          audio: false,
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
        },
        video,
        (result) => {
          if (!result || attempt !== attemptRef.current) return
          const code = normaliseProductCode(result.getText())
          if (!hasProductCodeLength(code)) return

          attemptRef.current += 1
          releaseCamera()
          setStatus('detected')
          onDetected(code)
        },
      )
      // The person may have pressed Stop while the browser's permission prompt was
      // open. In that case the stream did not exist when `stopCamera` first reset the
      // reader, so release the just-created stream as soon as ZXing hands control back.
      if (attempt !== attemptRef.current) releaseCamera()
    } catch (caught) {
      if (attempt !== attemptRef.current) return
      releaseCamera()
      setStatus('idle')
      setError(cameraErrorMessage(caught))
    }
  }

  function submitManualCode(event: React.FormEvent) {
    event.preventDefault()
    if (!hasProductCodeLength(digits)) return
    attemptRef.current += 1
    releaseCamera()
    setError(null)
    setStatus('detected')
    onDetected(digits)
  }

  const cameraActive = status === 'starting' || status === 'scanning'

  return (
    <div className="space-y-4">
      <div
        className={`relative overflow-hidden rounded-lg border bg-black ${cameraActive ? 'aspect-[4/3]' : 'hidden'}`}
      >
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          aria-label="Barcode camera preview"
          className="h-full w-full object-cover"
        />
        <div className="pointer-events-none absolute inset-x-[10%] top-1/2 h-24 -translate-y-1/2 rounded-md border-2 border-primary shadow-[0_0_0_999px_rgb(0_0_0/0.38)]" />
        <p className="absolute inset-x-3 bottom-3 rounded bg-black/70 px-3 py-2 text-center text-xs text-white">
          Hold the bars inside the frame
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {cameraActive ? (
          <Button type="button" variant="outline" onClick={stopCamera}>
            <Square className="h-4 w-4" />
            Stop camera
          </Button>
        ) : (
          <Button type="button" onClick={() => void startCamera()} disabled={disabled}>
            <Camera className="h-4 w-4" />
            Open camera
          </Button>
        )}
        {status === 'scanning' && (
          <span className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
            <ScanLine className="h-4 w-4" />
            Looking for an EAN or UPC…
          </span>
        )}
        {status === 'starting' && (
          <span className="inline-flex min-h-11 items-center text-sm text-muted-foreground" aria-live="polite">
            Starting the camera…
          </span>
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="border-t border-border pt-4">
        <form className="space-y-2" onSubmit={submitManualCode}>
          <label htmlFor="manual-barcode" className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Keyboard className="h-4 w-4" />
            Or type the digits
          </label>
          <div className="flex gap-2">
            <Input
              id="manual-barcode"
              inputMode="numeric"
              autoComplete="off"
              value={manualCode}
              onChange={(event) => setManualCode(event.target.value)}
              placeholder="EAN-13 or UPC-A"
              aria-describedby="barcode-length-hint"
              disabled={disabled}
            />
            <Button type="submit" variant="outline" disabled={disabled || !hasProductCodeLength(digits)}>
              Look up
            </Button>
          </div>
          <p id="barcode-length-hint" className="text-xs text-muted-foreground">
            Enter the 8, 12 or 13 digits printed below the bars.
          </p>
        </form>
      </div>
    </div>
  )
}
