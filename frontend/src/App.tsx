import { useEffect, useRef, useState } from 'react'
import { Activity, CircleHelp, Clock3, Cpu, Menu, Play, RotateCcw, Settings2, Volume2, VolumeX } from 'lucide-react'
import { AlertsPanel, AudioPanel, HealthPanel, InventoryPanel, MainPredictionCard, MapPanel, Modal, RecommendationsPanel, SequencePanel, StreamViewer } from './components'
import { useDashboardStore } from './store'
import { ApiError, api, connectVisualWebSocket, connectWebSocket, sendWebSocketCommand } from './services'
import type { ModuleStatus } from './types'
import { time } from './ui'
import ParticleBackground from './ParticleBackground'
import { VoiceControlPanel } from './voice'
import './styles.css'

function requestBrowserCapture(): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getDisplayMedia) throw new ApiError('Este navegador no permite compartir pantalla.')
  return navigator.mediaDevices.getDisplayMedia({ video: { frameRate: { ideal: 5, max: 10 }, width: { ideal: 1280, max: 1280 } }, audio: false })
}

function startBrowserFrameLoop(stream: MediaStream, send: (frame: Blob) => Promise<unknown>, onStopped: () => void, onError: (message: string) => void = (message) => { window.dispatchEvent(new CustomEvent('fortia-capture-error', { detail: message })) }): () => void {
  const video = document.createElement('video')
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d', { alpha: false })
  let timer: number | undefined
  let stopped = false
  let sending = false
  let loopStarted = false
  let lastSentAt = 0
  const intervalMs = 200
  const schedule = (delay = intervalMs) => { if (!stopped) timer = window.setTimeout(capture, delay) }
  const stop = () => {
    if (stopped) return
    stopped = true
    if (timer !== undefined) window.clearTimeout(timer)
    video.onloadedmetadata = null
    video.onplaying = null
    video.onpause = null
    video.onended = null
    video.srcObject = null
    stream.getTracks().forEach((track) => track.stop())
  }
  const capture = () => {
    if (stopped) return
    if (sending || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || video.videoWidth <= 0 || video.videoHeight <= 0) { schedule(100); return }
    const now = performance.now()
    if (now - lastSentAt < intervalMs) { schedule(intervalMs - (now - lastSentAt)); return }
    const scale = Math.min(1, 1280 / video.videoWidth)
    canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
    canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
    context?.drawImage(video, 0, 0, canvas.width, canvas.height)
    if (!context) { onError('El navegador no pudo crear el canvas de captura.'); schedule(500); return }
    canvas.toBlob((blob) => {
      if (stopped) return
      if (!blob) { onError('No se pudo comprimir el frame de captura.'); schedule(500); return }
      sending = true
      lastSentAt = performance.now()
      void send(blob).catch(() => {
        onError('No se pudo enviar un frame; reintentando la captura.')
      }).finally(() => { sending = false; schedule() })
    }, 'image/jpeg', 0.72)
  }
  const startLoop = () => { if (!loopStarted && !stopped) { loopStarted = true; capture() } }
  const resumeVideo = () => { if (!stopped && video.paused) void video.play().then(startLoop).catch(() => onError('El video de captura no pudo continuar reproduciéndose.')) }
  const handleEnded = () => { if (!stopped) { stop(); onStopped() } }
  stream.getVideoTracks().forEach((track) => track.addEventListener('ended', handleEnded, { once: true }))
  video.muted = true
  video.playsInline = true
  video.autoplay = true
  video.preload = 'auto'
  video.onloadedmetadata = () => { void video.play().then(startLoop).catch(() => onError('El video de captura no pudo iniciar.')) }
  video.onplaying = startLoop
  video.onpause = () => { if (!stopped && stream.active) resumeVideo() }
  video.onended = handleEnded
  video.srcObject = stream
  void video.play().then(startLoop).catch(() => { if (video.readyState !== HTMLMediaElement.HAVE_NOTHING) onError('El navegador bloqueó la reproducción de la captura compartida.') })
  return stop
}

const connectionLabels: Partial<Record<ModuleStatus, string>> = { idle: 'Sin iniciar', waiting: 'Conectando con el servidor', processing: 'Procesando', ready: 'API conectada', stale: 'Datos desactualizados', unavailable: 'No disponible', error: 'Error recuperable', offline: 'Backend no disponible', reconnecting: 'Reconectando' }
const sessionLabels = { idle: 'Listo para iniciar', waiting: 'Esperando datos', analyzing: 'Analizando en tiempo real', paused: 'AnÃ¡lisis pausado', finished: 'SesiÃ³n finalizada', offline: 'Sin conexiÃ³n', reconnecting: 'Reconectando' }
const errorText = (error: unknown) => error instanceof ApiError ? error.message : 'No se pudo establecer conexiÃ³n con la API.'

const normalizeInventoryEvent = (raw: Record<string, unknown>) => {
  const rawProbabilities = raw.classProbabilities
  const source = rawProbabilities && typeof rawProbabilities === 'object' ? rawProbabilities as Record<string, unknown> : {}
  const classes = ['Eliminado', 'Eliminacion', 'Victoria'] as const
  const values = classes.map((name) => Number(source[name] ?? 0))
  const scale = Math.max(...values) > 1 ? 100 : 1
  const classProbabilities = Object.fromEntries(classes.map((name, index) => [name, Math.max(0, values[index] / scale)])) as Record<string, number>
  const dominant = classes.reduce((best, name) => classProbabilities[name] > classProbabilities[best] ? name : best, classes[0])
  const backendConfidence = Number(raw.confidence ?? raw.predictionConfidence)
  const confidence = Number.isFinite(backendConfidence) ? (backendConfidence > 1 ? backendConfidence / 100 : backendConfidence) : classProbabilities[dominant]
  const backendImage = typeof raw.inventoryImage === 'string' && raw.inventoryImage.startsWith('data:image/') ? raw.inventoryImage : undefined
  const legacyImage = typeof raw.image === 'string' && raw.image.startsWith('data:image/') ? raw.image : undefined
  const image = backendImage ?? legacyImage
  return { ...raw, inventoryImage: image, image, classProbabilities, predictedClass: typeof raw.predictedClass === 'string' ? raw.predictedClass : dominant, confidence } as Record<string, unknown>
}

export default function App() {
  const state = useDashboardStore()
  const [modal, setModal] = useState<{ image: string; label: string } | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const apiCleanup = useRef<(() => void) | undefined>(undefined)
  const running = state.sessionStatus === 'analyzing'
  const status = state.sessionStatus === 'paused' ? 'processing' : state.connection

  const checkApi = async () => {
    state.setConnection('waiting'); setConnectionError(null)
    try { await api.status(); state.setConnection('ready') } catch (error) { state.setConnection('offline'); setConnectionError(errorText(error)) }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void checkApi(); return () => apiCleanup.current?.() }, [])
  useEffect(() => {
    const handleCaptureError = (event: Event) => {
      const message = (event as CustomEvent<string>).detail
      if (typeof message === 'string' && state.sessionStatus === 'analyzing') setConnectionError(message)
    }
    window.addEventListener('fortia-capture-error', handleCaptureError)
    return () => window.removeEventListener('fortia-capture-error', handleCaptureError)
  }, [state.sessionStatus])

  async function start() {
    setConnectionError(null)
    let stream: MediaStream | undefined
    try {
      state.setConnection('processing')
      await api.status()
      stream = await requestBrowserCapture()
      const created = await api.createSession()
      state.setSessionId(created.sessionId)
      await api.start(created.sessionId)
      state.setSessionStatus('analyzing')
      const stopBrowserCapture = startBrowserFrameLoop(stream, (frame) => api.ingestFrame(created.sessionId, frame), () => { state.setConnection('error'); setConnectionError('La captura de pantalla se detuvo. Puedes iniciar otra sesiÃ³n.') })
      const onTts = (event: Event) => sendWebSocketCommand(created.sessionId, { type: 'audio.tts', active: Boolean((event as CustomEvent<{ active?: boolean }>).detail?.active) })
      window.addEventListener('fortia-tts', onTts)
      const closeWebSocket = connectWebSocket(created.sessionId, (payload) => {
        const event = payload as { type?: string; data?: Record<string, unknown> }; const data = event.data ?? {}
        if (event.type === 'session.status' && data.sessionStatus) state.setSessionStatus(data.sessionStatus as typeof state.sessionStatus)
        if (event.type === 'capture.status') state.setStream({ sessionId: String(data.sessionId), predictionId: String(data.predictionId), timestamp: String(data.timestamp), source: 'capture', status: data.status === 'ready' ? 'ready' : 'processing', available: false, resolution: 'â€”', fps: 0, message: String(data.message ?? 'Buscando Fortnite.'), captureState: String(data.captureState ?? 'searching'), framesDropped: Number(data.framesDropped ?? 0) })
        if (event.type === 'map.updated') state.setMap(data as unknown as Parameters<typeof state.setMap>[0])
        if (event.type === 'frame_sequence.updated') state.setSequence(data as unknown as Parameters<typeof state.setSequence>[0])
        if (event.type === 'main_prediction.updated') state.setMainPrediction(data as unknown as Parameters<typeof state.setMainPrediction>[0])
        if (event.type === 'health_shield.updated') state.setHealthShield({ ...data, displayedAt: Date.now() / 1000 } as unknown as Parameters<typeof state.setHealthShield>[0])
        if (event.type === 'inventory.updated' && (data.items || data.inventoryImage || data.image)) {
          const inventory = normalizeInventoryEvent(data)
          if (import.meta.env.DEV) console.debug('[FORTIA] inventory.updated recibido', { imagePresent: Boolean(inventory.image), imageChars: typeof inventory.image === 'string' ? inventory.image.length : 0, status: inventory.status, predictedClass: inventory.predictedClass, confidence: inventory.confidence, probabilities: inventory.classProbabilities })
          state.setInventory(inventory as unknown as Parameters<typeof state.setInventory>[0])
        }
        if (event.type === 'audio_prediction.updated') { if (import.meta.env.DEV && (data.status === 'ready' || data.status === 'silence' || data.status === 'device_unavailable')) console.debug('[FORTIA] audio_prediction.updated recibido', { status: data.status, level: data.level, rms: data.rms, peak: data.peak, device: data.device }); state.setAudio(data as unknown as Parameters<typeof state.setAudio>[0]) }
        if (event.type === 'recommendation.updated') { state.addRecommendation(data as unknown as Parameters<typeof state.addRecommendation>[0]); state.addAlert({ id: String(data.id ?? data.eventId), severity: data.priority === 'alta' ? 'critical' : 'warning', title: String(data.title ?? 'RecomendaciÃ³n'), message: String(data.explanation ?? data.text ?? ''), timestamp: String(data.timestamp ?? new Date().toISOString()) }) }
      }, (socketStatus) => { if (socketStatus === 'open') { state.setConnection('ready'); setConnectionError(null) } else if (socketStatus === 'reconnecting') { state.setConnection('reconnecting'); setConnectionError('WebSocket desconectado. Intentando reconectar.') } else if (socketStatus === 'error') { state.setConnection('error'); setConnectionError('WebSocket desconectado. Revisa el backend y reintenta.') } })
      const closeVisualWebSocket = connectVisualWebSocket(created.sessionId, (data) => window.dispatchEvent(new CustomEvent('fortia-stream-frame', { detail: data })), () => undefined)
      apiCleanup.current = () => { window.removeEventListener('fortia-tts', onTts); stopBrowserCapture(); closeWebSocket(); closeVisualWebSocket() }
    } catch (error) { stream?.getTracks().forEach((track) => track.stop()); state.setConnection('error'); setConnectionError(error instanceof DOMException && error.name === 'NotAllowedError' ? 'Permiso de compartir pantalla rechazado.' : errorText(error)) }
  }
  async function pause() { if (state.sessionId) await api.pause(state.sessionId).catch((error) => { state.setConnection('error'); setConnectionError(errorText(error)) }); state.pause() }
  async function resume() { if (state.sessionId) await api.resume(state.sessionId).then(() => state.resume()).catch((error) => { state.setConnection('error'); setConnectionError(errorText(error)) }) }
  async function reset() { apiCleanup.current?.(); apiCleanup.current = undefined; if (state.sessionId) await api.reset(state.sessionId).catch(() => undefined); state.reset(); void checkApi() }

  return <div className='app-shell'>
    <ParticleBackground />
    <header className='topbar'><div className='brand'><div className='brand-mark'><img src='/assets/branding/fortia-logo.png' alt='Logo de FORTIA' className='brand-logo' /></div><div><strong>FORTIA</strong><small>INTELIGENCIA MULTIMODAL EN TIEMPO REAL</small></div></div><div className='top-context'><span className='live-dot' /> AnÃ¡lisis en tiempo real <span className='divider' /> <span className='api-badge'>API EN TIEMPO REAL</span></div><div className='top-actions'><div className='connection'><span className={'connection-dot ' + status} /><div><small>SISTEMA</small><strong>{connectionLabels[status]}</strong></div></div><button className='icon-button' title='Ayuda' aria-label='Ayuda'><CircleHelp size={18} /></button><button className='icon-button' title='Preferencias' aria-label='Preferencias'><Settings2 size={18} /></button><button className='menu-button' aria-label='MenÃº'><Menu size={19} /></button></div></header>
    <main className='dashboard'>
      <div className='status-strip'><div><span className='eyebrow'>SESIÃ“N DE ANÃLISIS</span><strong>{sessionLabels[state.sessionStatus]}</strong></div><div className='status-strip-right'><span><Clock3 size={14} /> Ãšltima actualizaciÃ³n: {time(state.lastUpdate)}</span>{connectionError ? <span className='api-error-inline' role='alert'>{connectionError}<button className='retry-button' onClick={() => void checkApi()}>Reintentar</button></span> : <span className='api-status-inline'>Datos exclusivamente del backend</span>}</div></div>
      <p className='privacy-notice'>Privacidad: al iniciar, el navegador pedira permiso para compartir la pantalla seleccionada. FORTIA envia frames JPEG reducidos temporalmente y no guarda video ni audio por defecto. Puedes detener la captura en cualquier momento.</p>
      <section className='kpi-grid'><MainPredictionCard data={state.mainPrediction} /><div className='kpi-side'><div className='mini-kpi'><span>Latencia media</span><strong>{state.mainPrediction ? state.mainPrediction.latencyMs + ' ms' : 'â€”'}</strong><small><Activity size={13} /> objetivo &lt; 200 ms</small></div><div className='mini-kpi'><span>Modelos activos</span><strong>5/5</strong><small><Cpu size={13} /> multimodal listo</small></div></div></section>
      <div className='main-grid'><aside className='left-column'><HealthPanel data={state.healthShield} /><InventoryPanel data={state.inventory} /></aside><section className='center-column'><StreamViewer data={state.stream} /><SequencePanel data={state.sequence} onOpen={(image, label) => setModal({ image, label })} /></section><aside className='right-column'><div className='right-utility-grid'><MapPanel data={state.map} /><AudioPanel data={state.audio} /></div><div className='right-insight-grid'><AlertsPanel alerts={state.alerts} /><RecommendationsPanel recommendations={state.recommendations} /></div></aside></div>
      <footer className='control-dock'><div className='dock-status'><span className='live-dot' /> <strong>API EN TIEMPO REAL</strong><span>Â· SesiÃ³n {state.sessionId ?? 'no iniciada'}</span></div><div className='dock-controls'><VoiceControlPanel />{!running && state.sessionStatus !== 'paused' ? <button className='primary-button' onClick={start} disabled={state.connection === 'offline' || state.connection === 'waiting'}><Play size={16} fill='currentColor' /> Iniciar anÃ¡lisis</button> : state.sessionStatus === 'paused' ? <button className='primary-button' onClick={resume}><Play size={16} fill='currentColor' /> Reanudar</button> : <button className='secondary-button' onClick={pause}>Pausar</button>}<button className='secondary-button' onClick={reset}><RotateCcw size={15} /> Reiniciar</button><button className='icon-button' onClick={state.toggleSound} aria-label={state.soundEnabled ? 'Silenciar alertas' : 'Activar alertas'}>{state.soundEnabled ? <Volume2 size={17} /> : <VolumeX size={17} />}</button></div></footer>
    </main>{modal && <Modal image={modal.image} label={modal.label} onClose={() => setModal(null)} />}
  </div>
}
