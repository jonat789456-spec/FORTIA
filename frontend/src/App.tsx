import { useEffect, useRef, useState } from 'react'
import { Activity, CircleHelp, Clock3, Cpu, Menu, Moon, Play, RotateCcw, Settings2, Volume2, VolumeX } from 'lucide-react'
import { AlertsPanel, BinaryModelPanel, HealthPanel, InventoryPanel, MainPredictionCard, Modal, RecommendationsPanel, SequencePanel, StreamViewer } from './components'
import { useDashboardStore } from './store'
import { ApiError, api, connectWebSocket } from './services'
import type { ModuleStatus } from './types'
import { time } from './ui'
import ParticleBackground from './ParticleBackground'
import { VoiceControlPanel } from './voice'
import './styles.css'

const connectionLabels: Partial<Record<ModuleStatus, string>> = { idle: 'Sin iniciar', waiting: 'Conectando con el servidor', processing: 'Procesando', ready: 'API conectada', stale: 'Datos desactualizados', unavailable: 'No disponible', error: 'Error recuperable', offline: 'Backend no disponible', reconnecting: 'Reconectando' }
const sessionLabels = { idle: 'Listo para iniciar', waiting: 'Esperando datos', analyzing: 'Analizando en tiempo real', paused: 'Análisis pausado', finished: 'Sesión finalizada', offline: 'Sin conexión', reconnecting: 'Reconectando' }
const errorText = (error: unknown) => error instanceof ApiError ? error.message : 'No se pudo establecer conexión con la API.'

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

  async function start() {
    setConnectionError(null)
    try {
      state.setConnection('processing')
      await api.status()
      const created = await api.createSession()
      state.setSessionId(created.sessionId)
      await api.start(created.sessionId)
      state.setSessionStatus('analyzing')
      apiCleanup.current = connectWebSocket(created.sessionId, (payload) => {
        const event = payload as { type?: string; data?: Record<string, unknown> }; const data = event.data ?? {}
        if (event.type === 'session.status' && data.sessionStatus) state.setSessionStatus(data.sessionStatus as typeof state.sessionStatus)
        if (event.type === 'capture.status') state.setStream({ sessionId: String(data.sessionId), predictionId: String(data.predictionId), timestamp: String(data.timestamp), source: 'capture', status: data.status === 'ready' ? 'ready' : 'processing', available: false, resolution: '—', fps: 0, message: String(data.message ?? 'Buscando Fortnite.'), captureState: String(data.captureState ?? 'searching'), framesDropped: Number(data.framesDropped ?? 0) })
        if (event.type === 'stream.updated') state.setStream(data as unknown as Parameters<typeof state.setStream>[0])
        if (event.type === 'map.updated') state.setMap(data as unknown as Parameters<typeof state.setMap>[0])
        if (event.type === 'frame_sequence.updated') state.setSequence(data as unknown as Parameters<typeof state.setSequence>[0])
        if (event.type === 'main_prediction.updated') state.setMainPrediction(data as unknown as Parameters<typeof state.setMainPrediction>[0])
        if (event.type === 'health_shield.updated') state.setHealthShield(data as unknown as Parameters<typeof state.setHealthShield>[0])
        if (event.type === 'inventory.updated' && data.items) state.setInventory(data as unknown as Parameters<typeof state.setInventory>[0])
        if (event.type === 'audio_prediction.updated') state.setAudio(data as unknown as Parameters<typeof state.setAudio>[0])
        if (event.type === 'recommendation.updated') { state.addRecommendation(data as unknown as Parameters<typeof state.addRecommendation>[0]); state.addAlert({ id: String(data.id ?? data.eventId), severity: data.priority === 'alta' ? 'critical' : 'warning', title: String(data.title ?? 'Recomendación'), message: String(data.explanation ?? data.text ?? ''), timestamp: String(data.timestamp ?? new Date().toISOString()) }) }
      }, (socketStatus) => { if (socketStatus === 'open') { state.setConnection('ready'); setConnectionError(null) } else if (socketStatus === 'reconnecting') { state.setConnection('reconnecting'); setConnectionError('WebSocket desconectado. Intentando reconectar.') } else if (socketStatus === 'error') { state.setConnection('error'); setConnectionError('WebSocket desconectado. Revisa el backend y reintenta.') } })
    } catch (error) { state.setConnection('error'); setConnectionError(errorText(error)) }
  }
  async function pause() { if (state.sessionId) await api.pause(state.sessionId).catch((error) => { state.setConnection('error'); setConnectionError(errorText(error)) }); state.pause() }
  async function resume() { if (state.sessionId) await api.resume(state.sessionId).then(() => state.resume()).catch((error) => { state.setConnection('error'); setConnectionError(errorText(error)) }) }
  async function reset() { apiCleanup.current?.(); apiCleanup.current = undefined; if (state.sessionId) await api.reset(state.sessionId).catch(() => undefined); state.reset(); void checkApi() }

  return <div className='app-shell'>
    <ParticleBackground />
    <header className='topbar'><div className='brand'><div className='brand-mark'><img src='/assets/branding/fortia-logo.png' alt='Logo de FORTIA' className='brand-logo' /></div><div><strong>FORTIA</strong><small>INTELIGENCIA MULTIMODAL EN TIEMPO REAL</small></div></div><div className='top-context'><span className='live-dot' /> Análisis en tiempo real <span className='divider' /> <span className='api-badge'>API EN TIEMPO REAL</span></div><div className='top-actions'><div className='connection'><span className={'connection-dot ' + status} /><div><small>SISTEMA</small><strong>{connectionLabels[status]}</strong></div></div><button className='icon-button' title='Ayuda' aria-label='Ayuda'><CircleHelp size={18} /></button><button className='icon-button' title='Preferencias' aria-label='Preferencias'><Settings2 size={18} /></button><button className='menu-button' aria-label='Menú'><Menu size={19} /></button></div></header>
    <main className='dashboard'>
      <div className='status-strip'><div><span className='eyebrow'>SESIÓN DE ANÁLISIS</span><strong>{sessionLabels[state.sessionStatus]}</strong></div><div className='status-strip-right'><span><Clock3 size={14} /> Última actualización: {time(state.lastUpdate)}</span>{connectionError ? <span className='api-error-inline' role='alert'>{connectionError}<button className='retry-button' onClick={() => void checkApi()}>Reintentar</button></span> : <span className='api-status-inline'>Datos exclusivamente del backend</span>}</div></div>
      <section className='kpi-grid'><MainPredictionCard data={state.mainPrediction} /><div className='kpi-side'><div className='mini-kpi'><span>Latencia media</span><strong>{state.mainPrediction ? state.mainPrediction.latencyMs + ' ms' : '—'}</strong><small><Activity size={13} /> objetivo &lt; 200 ms</small></div><div className='mini-kpi'><span>Modelos activos</span><strong>5/5</strong><small><Cpu size={13} /> multimodal listo</small></div></div></section>
      <div className='main-grid'><aside className='left-column'><HealthPanel data={state.healthShield} /><BinaryModelPanel title='Audio' icon={<Volume2 size={17} />} data={state.audio} empty='Sin señal de audio disponible.' /><BinaryModelPanel title='Mapa' icon={<Moon size={17} />} data={state.map} empty='Sin información del mapa.' />{state.map && <div className='map-preview'><img src={state.map.image} alt='Vista previa del mapa' /><span>MAPA ACTUAL</span></div>}</aside><section className='center-column'><StreamViewer data={state.stream} /><SequencePanel data={state.sequence} onOpen={(image, label) => setModal({ image, label })} /></section><aside className='right-column'><InventoryPanel data={state.inventory} /><AlertsPanel alerts={state.alerts} /><RecommendationsPanel recommendations={state.recommendations} /></aside></div>
      <footer className='control-dock'><div className='dock-status'><span className='live-dot' /> <strong>API EN TIEMPO REAL</strong><span>· Sesión {state.sessionId ?? 'no iniciada'}</span></div><div className='dock-controls'><VoiceControlPanel />{!running && state.sessionStatus !== 'paused' ? <button className='primary-button' onClick={start} disabled={state.connection === 'offline' || state.connection === 'waiting'}><Play size={16} fill='currentColor' /> Iniciar análisis</button> : state.sessionStatus === 'paused' ? <button className='primary-button' onClick={resume}><Play size={16} fill='currentColor' /> Reanudar</button> : <button className='secondary-button' onClick={pause}>Pausar</button>}<button className='secondary-button' onClick={reset}><RotateCcw size={15} /> Reiniciar</button><button className='icon-button' onClick={state.toggleSound} aria-label={state.soundEnabled ? 'Silenciar alertas' : 'Activar alertas'}>{state.soundEnabled ? <Volume2 size={17} /> : <VolumeX size={17} />}</button></div></footer>
    </main>{modal && <Modal image={modal.image} label={modal.label} onClose={() => setModal(null)} />}
  </div>
}
