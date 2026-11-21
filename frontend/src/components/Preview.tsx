import { useEffect, useMemo, useRef, useState } from 'react'

import { api, type FitCheck } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useStore } from '@/store'

// The template only sets margins for print (@page). On screen, draw it as an A4 sheet.
const PAGE_WIDTH_PX = 794 // 210mm at 96dpi
const FRAME_WIDTH_PX = PAGE_WIDTH_PX + 32
const SCREEN_CSS = `<style>@media screen {
  html { background: #e5e7eb; overflow: hidden; }
  body { box-sizing: border-box; width: 210mm; min-height: 297mm; margin: 16px auto; padding: 13mm 15mm 11mm 15mm;
         background: #fff; box-shadow: 0 1px 4px rgb(0 0 0 / 0.15); }
}</style>`

/** Run `fn(value)` once `value` has stopped changing for `delay` ms; abort the previous run. */
function useDebounced<T>(value: T, fn: (value: T, signal: AbortSignal) => void, delay: number) {
  const fnRef = useRef(fn)
  useEffect(() => { fnRef.current = fn })
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => fnRef.current(value, controller.signal), delay)
    return () => { clearTimeout(timer); controller.abort() }
  }, [value, delay])
}

export function Preview() {
  const { cv, busy, exportPdf } = useStore()
  const [html, setHtml] = useState('')
  const [fit, setFit] = useState<FitCheck | null>(null)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scale, setScale] = useState(1)
  const wrapper = useRef<HTMLDivElement>(null)
  const frame = useRef<HTMLIFrameElement>(null)
  const scaleRef = useRef(scale)
  scaleRef.current = scale

  // Shrink the page with CSS zoom, not transform: zoom lays the page out again at the smaller size,
  // so text is drawn sharp (a scaled iframe can show a stretched, blurry bitmap) and wraps exactly
  // as at full size. New HTML starts at the current zoom; resizes then update it without a reload.
  const srcDoc = useMemo(
    () => html.replace('</head>', `<style>html { zoom: ${scaleRef.current}; }</style></head>`),
    [html],
  )
  useEffect(() => {
    const root = frame.current?.contentDocument?.documentElement
    if (root) root.style.zoom = String(scale)
  }, [scale])

  useEffect(() => {
    const el = wrapper.current
    if (!el) return
    const observer = new ResizeObserver(([e]) => setScale(Math.min(1, e.contentRect.width / FRAME_WIDTH_PX)))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useDebounced(cv, (cv, signal) => {
    if (!cv) return
    api.renderHtml(cv, signal)
      .then(h => { setHtml(h.replace('</head>', `${SCREEN_CSS}</head>`)); setError(null) })
      .catch(e => { if (!signal.aborted) setError(String(e.message ?? e)) })
  }, 300)

  // Page count needs a real PDF render (~1s), so it waits for a longer pause in typing.
  useDebounced(cv, (cv, signal) => {
    if (!cv) return
    setChecking(true)
    api.checkFit(cv, signal)
      .then(setFit)
      .catch(() => { /* the preview shows render errors */ })
      .finally(() => { if (!signal.aborted) setChecking(false) })
  }, 1200)

  if (!cv) return null
  const frameHeight = 1123 + 32

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="truncate text-sm font-medium">{cv.filename}.pdf</span>
        {fit && (fit.fits
          ? <Badge variant="secondary" title={`fit step ${fit.fit_step} of 4`}>
              1 page{fit.fit_step > 0 ? ` (tightened ×${fit.fit_step})` : ''}
            </Badge>
          : <Badge variant="destructive">{fit.pages} pages: cut a bullet</Badge>)}
        {checking && <span className="text-xs text-muted-foreground">checking fit…</span>}
        <Button className="ml-auto" onClick={exportPdf} disabled={busy !== null || fit?.fits === false}>
          {busy === 'export' ? 'Exporting…' : 'Download PDF'}
        </Button>
      </div>
      {error && <div className="text-sm text-red-700">{error}</div>}
      <div ref={wrapper} className="overflow-hidden rounded-lg border" style={{ height: frameHeight * scale }}>
        {/* allow-same-origin lets the zoom effect reach the page; scripts stay blocked. */}
        <iframe
          ref={frame}
          title="CV preview"
          srcDoc={srcDoc}
          sandbox="allow-same-origin"
          onLoad={e => {
            const root = e.currentTarget.contentDocument?.documentElement
            if (root) root.style.zoom = String(scaleRef.current)
          }}
          style={{ display: 'block', width: FRAME_WIDTH_PX * scale, height: frameHeight * scale }}
        />
      </div>
    </div>
  )
}
