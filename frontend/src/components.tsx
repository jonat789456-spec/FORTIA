import { Activity, AlertTriangle, Box, ChevronRight, Crosshair, Gamepad2, Gauge, HeartPulse, Maximize2, Radio, Shield, Sparkles, Wifi, XCircle, Volume2 } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { BinaryPrediction, ModuleStatus, Recommendation, MainPrediction, HealthShieldData, InventoryData, SequenceData, StreamData, Alert } from './types'

import { pct } from './ui'
const time = (value?: string | null) => value ? new Date(value).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'
const statusText: Partial<Record<ModuleStatus, string>> = { idle: 'Sin iniciar', waiting: 'Esperando datos', processing: 'Procesando', ready: 'Disponible', available: 'Disponible', stale: 'Desactualizado', low_confidence: 'Baja confianza', not_detected: 'No detectado', not_applicable: 'No aplica', unavailable: 'No disponible', error: 'Error', offline: 'Sin conexión', reconnecting: 'Reconectando' }

statusText.low_confidence = 'Baja confianza'

export function Panel({ title, eyebrow, icon, children, className = '', action }: { title: string; eyebrow?: string; icon?: ReactNode; children: ReactNode; className?: string; action?: ReactNode }) {
  return <section className={'panel ' + className}><div className='panel-heading'><div className='heading-title'>{icon}<div>{eyebrow && <span className='eyebrow'>{eyebrow}</span>}<h2>{title}</h2></div></div>{action}</div>{children}</section>
}

export function StatusBadge({ status }: { status: ModuleStatus }) {
  return <span className={'status-badge status-' + status}><i />{statusText[status] ?? status.replaceAll('_', ' ')}</span>
}

export function BinaryPredictionView({ data }: { data: BinaryPrediction | null }) {
  if (data && (data.winProbability == null || data.lossProbability == null || data.status !== 'ready')) return <EmptyState text={data.reason ?? statusText[data.status] ?? 'No disponible'} />
  if (!data) return <EmptyState text='Aún no hay predicción disponible.' />
  return <div className='binary-prediction'><div><span>Victoria</span><strong className='text-green'>{pct(data.winProbability!)}%</strong></div><div><span>Derrota</span><strong className='text-red'>{pct(data.lossProbability!)}%</strong></div></div>
}

export function ProbabilityBar({ label, value, color }: { label: string; value: number; color: string }) {
  return <div className='prob-row' aria-label={label === 'Eliminación' ? 'Probabilidad de eliminación' : undefined}><div><span>{label}</span><strong>{pct(value)}%</strong></div><div className='prob-track'><span style={{ width: pct(value) + '%', background: color }} /></div></div>
}

export function EmptyState({ text, compact = false }: { text: string; compact?: boolean }) {
  return <div className={'empty-state ' + (compact ? 'compact' : '')}><Activity size={16} /><span>{text}</span></div>
}

export function MainPredictionCard({ data }: { data: MainPrediction | null }) {
  if (!data) return <Panel title='Predicción multimodal' eyebrow='MODELO PRINCIPAL' icon={<Sparkles size={17} />}><EmptyState text='Esperando el primer resultado del modelo principal.' /></Panel>
  const label = data.predictedClass === 'victory' ? 'Victoria' : data.predictedClass === 'elimination' ? 'Eliminación' : 'Eliminado'
  return <Panel title='Predicción multimodal' eyebrow='MODELO PRINCIPAL' icon={<Sparkles size={17} />} className='main-prediction'>
    <div className={'predicted-class class-' + data.predictedClass}><div className='prediction-orb'><Crosshair size={26} aria-hidden='true' /></div><div><span>Clase predicha</span><strong>{label}</strong><small className='prediction-risk'>{data.riskLabel ?? (data.predictedClass === 'eliminated' ? 'Riesgo alto de ser eliminado' : data.predictedClass === 'elimination' ? 'Oportunidad de eliminación' : 'Alta posibilidad de victoria')}</small></div><div className='confidence'><small>Confianza general</small><b>{pct(data.confidence)}%</b></div></div>
    <div className='main-bars'><ProbabilityBar label='Eliminado' value={data.eliminatedProbability} color='var(--pred-eliminated)' /><ProbabilityBar label='Eliminación' value={data.eliminationProbability} color='var(--pred-elimination)' /><ProbabilityBar label='Victoria' value={data.victoryProbability} color='var(--pred-victory)' /></div>
    <div className='main-recommendation'><Sparkles size={15} aria-hidden='true' /><span><strong>Recomendación principal</strong>{data.predictedClass === 'eliminated' ? 'Busca cobertura y prioriza recuperarte.' : data.predictedClass === 'elimination' ? 'Mantén la ventaja y prepárate para el siguiente enfrentamiento.' : 'La situación es favorable; mantén tu posición.'}</span></div>
    <div className='prediction-meta'><span><Gauge size={14} /> {data.latencyMs} ms</span><span><Activity size={14} /> Actualizado {time(data.timestamp)}</span><span>Estado: {statusText[data.status] ?? data.status}</span></div>
    <p className='disclaimer'>Esta predicción es una herramienta de apoyo y no garantiza el resultado de la partida.</p>
  </Panel>
}

export function StreamViewer({ data }: { data: StreamData }) {
  const imageRef = useRef<HTMLImageElement>(null)
  const pendingRef = useRef<StreamData | null>(null)
  const rafRef = useRef<number | null>(null)
  const lastUiUpdateRef = useRef(0)
  const renderCountRef = useRef(0)
  const renderWindowRef = useRef(performance.now())
  const renderFpsRef = useRef(0)
  const receivedCountRef = useRef(0)
  const lastRenderedSequenceRef = useRef(0)
  const lastReceivedAtRef = useRef(performance.now())
  const receivedFpsRef = useRef(0)
  const totalReceivedRef = useRef(0)
  const totalRenderedRef = useRef(0)
  const [display, setDisplay] = useState<StreamData>(data)
  useEffect(() => {
    const onFrame = (event: Event) => {
      pendingRef.current = (event as CustomEvent<StreamData>).detail
      if (rafRef.current !== null) return
      rafRef.current = window.requestAnimationFrame(() => {
        rafRef.current = null
        const frame = pendingRef.current
        pendingRef.current = null
        if (!frame) return
        if (frame.frameId != null && frame.frameId <= lastRenderedSequenceRef.current) return
        if (frame.frameId != null) lastRenderedSequenceRef.current = frame.frameId
        if (imageRef.current && frame.image) imageRef.current.src = frame.image
        const now = performance.now()
        renderCountRef.current += 1
        receivedCountRef.current += 1
        totalReceivedRef.current += 1
        totalRenderedRef.current += 1
        const receivedElapsed = now - lastReceivedAtRef.current
        if (receivedElapsed >= 1000) { receivedFpsRef.current = receivedCountRef.current * 1000 / receivedElapsed; receivedCountRef.current = 0; lastReceivedAtRef.current = now }
        const renderElapsed = now - renderWindowRef.current
        const renderFps = renderElapsed >= 1000 ? renderCountRef.current * 1000 / renderElapsed : renderFpsRef.current
        if (renderElapsed >= 1000) { renderFpsRef.current = renderFps; renderCountRef.current = 0; renderWindowRef.current = now }
        if (now - lastUiUpdateRef.current >= 500) { lastUiUpdateRef.current = now; setDisplay({ ...frame, receivedFps: receivedFpsRef.current, renderFps, framesReceived: totalReceivedRef.current, framesRendered: totalRenderedRef.current, screenLatencyMs: frame.capturedAt ? (Date.now() / 1000 - frame.capturedAt) * 1000 : frame.latencyMs }) }
      })
    }
    window.addEventListener('fortia-stream-frame', onFrame)
    return () => { window.removeEventListener('fortia-stream-frame', onFrame); if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current) }
  }, [])
  const shown = display
  return <Panel title='Vista de la partida' eyebrow='CAPTURA EN TIEMPO REAL' icon={<Radio size={17} />} className='stream-panel'>
    <div className={'stream-view ' + (shown.available ? 'is-live' : '')}><div className='stream-art'><img ref={imageRef} src={shown.image} alt='Captura actual de Fortnite' className='stream-image' style={{ display: shown.image ? 'block' : 'none' }} /><div className='scanline' /><div className='stream-crosshair'><Crosshair size={40} /></div><div className='stream-overlay'><span className='live-dot' /> LIVE // CAPTURE FEED</div>{!shown.image && <div className='stream-placeholder'><Gamepad2 size={42} /><strong>{shown.available ? 'CAPTURA ACTIVA' : 'ESPERANDO TRANSMISIÓN'}</strong><span>{shown.message}</span></div>}<div className='stream-hud'><span>HP 82</span><span>SH 73</span><span>ZONE 04:18</span></div></div></div>
    <div className='stream-footer'><span><Wifi size={14} /> {shown.available ? shown.message : 'Señal no disponible'}</span><span>{shown.resolution} · captura {shown.captureFps != null ? Math.round(shown.captureFps) : '—'} · recibidos {shown.receivedFps != null ? Math.round(shown.receivedFps) : '—'} · únicos {shown.renderFps != null ? Math.round(shown.renderFps) : '—'} FPS{shown.screenLatencyMs != null ? ` · ${Math.round(shown.screenLatencyMs)} ms` : ''}</span></div>
  </Panel>
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyHealthPanel({ data }: { data: HealthShieldData | null }) {
  if (!data) return <Panel title='Vida y escudo' icon={<HeartPulse size={17} />}><EmptyState text='Detectando HUD de Fortnite.' /></Panel>
  const reading = (kind: 'health' | 'shield') => kind === 'health' ? data.healthReading : data.shieldReading
  const valueFor = (kind: 'health' | 'shield') => { const legacy = kind === 'health' ? data.healthValue : data.shieldValue; const nested = kind === 'health' ? data.health : data.shield; return reading(kind)?.value ?? legacy ?? (typeof nested === 'object' && nested ? nested.current : nested) }
  const labelFor = (kind: 'health' | 'shield') => { const item = reading(kind); if (!item || item.value == null || item.status === 'stale' || item.status === 'no_reading') return 'Sin lectura reciente'; if (item.status === 'last_stable') return 'Última lectura estable'; if (item.status === 'estimated') return 'Estimado'; return 'Actual' }
  const statusClass = (kind: 'health' | 'shield') => { const item = reading(kind); if (!item || item.value == null || item.status === 'stale' || item.status === 'no_reading') return 'none'; if (item.status === 'last_stable') return 'stable'; if (item.status === 'estimated') return 'estimated'; return 'current' }
  const ageFor = (kind: 'health' | 'shield') => { const age = reading(kind)?.ageMs; return age == null ? '' : ` · hace ${(age / 1000).toFixed(1)} s` }
  const valueBlock = (kind: 'health' | 'shield', label: string, Icon: typeof HeartPulse) => { const value = valueFor(kind); const state = kind === 'health' ? data.health : data.shield; const max = typeof state === 'object' && state?.max != null ? state.max : kind === 'health' ? data.healthMax ?? 100 : data.shieldMax ?? 100; const visible = value != null && !['stale', 'no_reading'].includes(reading(kind)?.status ?? ''); const rounded = visible ? Math.round(value as number) : 0; const roundedMax = Math.round(max as number); return <div className='health-reading'><div className='vital-row'><span><Icon size={15} /> {label}</span><strong>{visible ? rounded : '—'}<small>{visible ? '/' + roundedMax : ''}</small></strong></div><div className={'health-reading-meta quality-' + statusClass(kind)}><span className='health-reading-dot' /> {labelFor(kind)}{ageFor(kind)}</div><div className={'vital-track ' + kind}><span style={{ width: (visible ? Math.min(100, rounded / Math.max(1, roundedMax) * 100) : 0) + '%' }} /></div></div> }
  const overall = data.status === 'not_detected' && valueFor('health') == null && valueFor('shield') == null ? 'not_detected' : 'available'
  return <Panel title='Vida y escudo' icon={<HeartPulse size={17} />} action={<StatusBadge status={overall} />}><div className='vitals'>{valueBlock('health', 'Vida', HeartPulse)}{valueBlock('shield', 'Escudo', Shield)}</div>{data.healthAlertActive && <div className='inline-alert critical'><AlertTriangle size={14} /> Vida baja: busca cobertura.</div>}<div className='panel-foot'>Lecturas independientes · Actualizado {time(data.timestamp)}</div></Panel>
}

/* Legacy implementation retained only in source history; the independent reader above is the active panel.
function LegacyHealthPanel({ data }: { data: HealthShieldData | null }) {
  const readable = data?.status === 'ready' || data?.status === 'available'
  const health = data?.healthValue ?? data?.health
  const shield = data?.shieldValue ?? data?.shield
  const confidence = data?.confidence ?? 0
  if (!data || !readable || health == null || shield == null || confidence < 0.75) return <Panel title='Vida y escudo' icon={<HeartPulse size={17} />} action={data && <StatusBadge status={data.status} />}><EmptyState text={!data ? 'Esperando datos de vida y escudo.' : data.status === 'low_confidence' ? 'Lectura de vida y escudo con baja confianza.' : data.reason ?? 'Vida y escudo no disponibles.'} />{data && <div className='panel-foot'>Actualizado {time(data.timestamp)}</div>}</Panel>
  const healthValue = Math.round(health); const shieldValue = Math.round(shield)
  return <Panel title='Vida y escudo' icon={<HeartPulse size={17} />} action={<StatusBadge status={data.status} />}><div className='vitals'><div className='vital-row'><span><HeartPulse size={15} /> Vida</span><strong>{healthValue}<small>/100</small></strong></div><div className='vital-track health'><span style={{ width: healthValue + '%' }} /></div><div className='vital-row'><span><Shield size={15} /> Escudo</span><strong>{shieldValue}<small>/100</small></strong></div><div className='vital-track shield'><span style={{ width: shieldValue + '%' }} /></div></div>{data.healthAlertActive && <div className='inline-alert critical'><AlertTriangle size={14} /> Vida baja: busca cobertura.</div>}<div className='panel-foot'>Confianza {Math.round(confidence * 100)}% · Actualizado {time(data.timestamp)}</div></Panel>
} */

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyInventoryPanel({ data }: { data: InventoryData | null }) {
  if (!data) return <Panel title='Inventario' icon={<Box size={17} />}><EmptyState text='Esperando captura del inventario.' /></Panel>
  const statusMessage: Record<string, string> = { waiting: 'Esperando captura', processing: 'Analizando inventario', low_confidence: 'Baja confianza', not_detected: 'Inventario no visible', unavailable: 'Modelo no disponible', model_missing: 'Modelo no disponible', error: 'Error recuperable' }
  const image = data.inventoryImage ?? data.image
  const imageLabel = data.imageIsStale ? `Última lectura válida · hace ${Math.max(1, Math.round((data.imageAgeMs ?? 0) / 1000))} s` : image ? 'Captura más reciente' : statusMessage[data.status] ?? 'Esperando captura'
  const probabilities = data.classProbabilities
  const classes = ['Eliminado', 'Eliminacion', 'Victoria'] as const
  const values = classes.map((name) => Number(probabilities?.[name] ?? 0))
  const scale = Math.max(...values) > 1 ? 100 : 1
  const normalizedProbabilities = Object.fromEntries(classes.map((name, index) => [name, Math.max(0, values[index] / scale)])) as Record<string, number>
  const dominant = data.predictedClass ?? classes.reduce((best, name) => normalizedProbabilities[name] > normalizedProbabilities[best] ? name : best, classes[0])
  const confidenceValue = data.confidence ?? data.predictionConfidence ?? normalizedProbabilities[dominant as typeof classes[number]]
  const dominantLabel = dominant === 'Eliminacion' || dominant === 'elimination' ? 'Eliminación' : dominant === 'Victoria' || dominant === 'victory' ? 'Victoria' : dominant === 'Eliminado' || dominant === 'eliminated' ? 'Eliminado' : dominant
  return <Panel title='Inventario' icon={<Box size={17} />} action={<StatusBadge status={data.status} />}>
    {image ? <div className='inventory-preview' style={{ position: 'relative', minHeight: 76, border: '1px solid rgba(34,211,238,.28)', borderRadius: 7, background: '#06101d', overflow: 'hidden', display: 'grid', placeItems: 'center' }}><img src={image} alt='Inventario completo de Fortnite' style={{ display: 'block', width: '100%', height: 92, objectFit: 'contain', objectPosition: 'center', imageRendering: 'auto' }} /><span style={{ position: 'absolute', left: 8, bottom: 6, padding: '3px 6px', borderRadius: 3, background: '#050b15cc', color: data.imageIsStale ? 'var(--gold)' : 'var(--text-secondary)', fontSize: 9 }}>{imageLabel}</span></div> : <EmptyState text={statusMessage[data.status] ?? 'Esperando captura del inventario.'} />}
    {probabilities && data.status === 'ready' ? <div className='main-bars inventory-bars'><ProbabilityBar label='Eliminado' value={normalizedProbabilities.Eliminado} color='var(--pred-eliminated)' /><ProbabilityBar label='Eliminación' value={normalizedProbabilities.Eliminacion} color='var(--pred-elimination)' /><ProbabilityBar label='Victoria' value={normalizedProbabilities.Victoria} color='var(--pred-victory)' /></div> : <EmptyState compact text={statusMessage[data.status] ?? data.reason ?? 'El modelo está procesando el inventario.'} />}
    <div className='inventory-meta'><span>Clase dominante: <strong>{dominantLabel || '—'}</strong></span><span>Confianza: <strong>{Number.isFinite(confidenceValue) ? pct(confidenceValue) + '%' : '—'}</strong></span></div>
    {data.recommendation && <div className='recommendation-mini'><Sparkles size={14} /><span>{data.recommendation}</span></div>}
    <div className='panel-foot'>{data.imageIsStale ? 'Última lectura válida · ' : ''}Actualizado {time(data.timestamp)}</div>
  </Panel>
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyBinaryModelPanel({ title, icon, data, empty }: { title: string; icon: ReactNode; data: BinaryPrediction | null; empty: string }) {
  return <Panel title={title} icon={icon} action={data && <StatusBadge status={data.status} />}>{!data ? <EmptyState text={empty} /> : <><BinaryPredictionView data={data} /><div className='panel-foot'>Actualizado {time(data.timestamp)}</div></>}</Panel>
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyAudioPanel({ data }: { data: BinaryPrediction | null }) {
  const probabilities = data?.classProbabilities
  const status = data?.status ?? 'unavailable'
  const label = status === 'silence' ? 'Captura activa · sin señal' : status === 'ready' || status === 'available' ? `Capturando · ${data?.predictedClass ?? 'Audio'}` : status === 'model_missing' ? 'Modelo de audio no cargado' : status === 'device_unavailable' ? 'Error de captura; reintentando' : status === 'device_search' ? 'Buscando dispositivo de salida…' : status === 'initializing' ? 'Inicializando captura WASAPI…' : status === 'buffering' ? 'Preparando ventana de audio…' : status === 'capturing' ? 'Capturando audio del sistema' : status === 'inference' ? 'Procesando inferencia' : status === 'unavailable' ? 'No disponible' : 'Error recuperable'
  const waveform = data?.waveform ?? []
  const reason = data?.reason?.toLowerCase().includes('espectrogramas png') ? status === 'model_missing' ? 'Modelo de audio no cargado.' : status === 'silence' ? 'Captura activa · sin señal.' : data?.bufferReady ? 'Captura cruda activa; esperando la siguiente inferencia.' : 'Inicializando captura de audio crudo.' : data?.reason ?? 'El audio no aporta evidencia suficiente.'
  return <Panel title='Audio' eyebrow='WASAPI LOOPBACK' icon={<Volume2 size={17} />} action={data && <StatusBadge status={status} />}>
    {!data ? <EmptyState text='Esperando captura de audio del sistema.' /> : <>
      <div className='audio-status-line'><strong>{label}</strong><span>Fuente: WASAPI Loopback{data.device ? ` · ${data.device}` : ''}</span></div>
      {probabilities && status === 'ready' ? <div className='main-bars audio-bars'>{Object.entries(probabilities).map(([name, value]) => <ProbabilityBar key={name} label={name} value={value} color={name === 'Victoria' ? 'var(--pred-victory)' : name === 'Eliminado' ? 'var(--pred-eliminated)' : 'var(--pred-elimination)'} />)}</div> : <EmptyState compact text={reason} />}
      <div className='audio-meter'><span>Nivel</span><div><i style={{ width: `${Math.min(100, Math.max(0, data.level ?? 0))}%` }} /></div><b>{Math.round(data.level ?? 0)}%</b></div>
      {waveform.length > 0 && <div className='audio-waveform' aria-label='Forma de onda capturada' style={{ display: 'flex', alignItems: 'center', gap: 2, height: 28, marginTop: 10, overflow: 'hidden' }}>{waveform.map((value, index) => <i key={index} style={{ display: 'block', flex: 1, minWidth: 1, height: `${Math.max(4, Math.min(100, Math.abs(value) * 1000))}%`, background: 'var(--cyan)', opacity: 0.75 }} />)}</div>}
      <div className='panel-foot'>{data.latencyMs != null ? `${data.latencyMs.toFixed(1)} ms · ` : ''}Actualizado {time(data.timestamp)}</div>
    </>}
  </Panel>
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacySequencePanel({ data, onOpen }: { data: SequenceData | null; onOpen: (image: string, label: string) => void }) {
  return <Panel title='Secuencia de seis frames' eyebrow='MODELO TEMPORAL' icon={<Activity size={17} />} action={data && <StatusBadge status={data.status} />}>{!data ? <EmptyState text='Esperando la secuencia de frames.' /> : <><div className='frames-grid'>{data.frames.map((frame) => <button className={'frame-card frame-' + frame.status} key={frame.id} onClick={() => onOpen(frame.image, 'Frame ' + frame.index)} aria-label={'Ampliar Frame ' + frame.index}><img src={frame.image} alt={'Frame ' + frame.index} /><span className='frame-number'>0{frame.index}</span><span className='frame-time'>{time(frame.timestamp)}</span>{frame.status === 'processing' && <span className='frame-processing'>Procesando</span>}<Maximize2 size={14} /></button>)}</div><div className='sequence-footer'><div><span>Predicción de la secuencia completa</span><strong>{pct(data.winProbability)}% victoria <i>·</i> {pct(data.lossProbability)}% derrota</strong></div><span>Actualizado {time(data.timestamp)}</span></div></>}</Panel>
}

function vitalValue(data: HealthShieldData, kind: 'health' | 'shield'): number | null {
  const reading = kind === 'health' ? data.healthReading : data.shieldReading
  const nested = kind === 'health' ? data.health : data.shield
  const legacy = kind === 'health' ? data.healthValue : data.shieldValue
  if (reading?.status === 'stale' || reading?.status === 'no_reading') return null
  const value = reading?.value ?? legacy ?? (typeof nested === 'object' && nested ? nested.current : nested)
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null
}

export function HealthPanel({ data }: { data: HealthShieldData | null }) {
  const valueBlock = (kind: 'health' | 'shield', label: string, Icon: typeof HeartPulse) => {
    const value = data ? vitalValue(data, kind) : null
    const reading = data ? (kind === 'health' ? data.healthReading : data.shieldReading) : undefined
    const state = kind === 'health' ? 'health' : 'shield'
    const text = value == null ? (kind === 'health' ? 'Verificando vida' : 'Verificando escudo') : kind === 'health' ? value >= 70 ? 'Vida estable' : value >= 40 ? 'Vida moderada' : value > 0 ? 'Vida baja' : 'Eliminado' : value >= 70 ? 'Escudo alto' : value >= 30 ? 'Escudo moderado' : value > 0 ? 'Escudo bajo' : 'Sin escudo'
    const trend = data?.trend && data.trend.length > 1 ? data.trend[data.trend.length - 1] - data.trend[0] : 0
    const trendText = trend > 2 ? 'subiendo' : trend < -2 ? 'bajando' : 'estable'
    return <div className={'health-reading health-reading-' + state}><div className='vital-row'><span><Icon size={15} aria-hidden='true' /> {label}</span><strong>{value == null ? '—' : Math.round(value)}<small>{value == null ? '' : '/100'}</small></strong></div><div className='health-reading-meta'><span className='health-reading-dot' /> {text}{reading?.ageMs != null ? ` · hace ${(reading.ageMs / 1000).toFixed(1)} s` : ''}</div><div className={'vital-track ' + state}><span style={{ width: `${value == null ? 0 : value}%` }} /></div><small className='vital-trend'>Tendencia reciente: {trendText}</small></div>
  }
  const status = data?.status ?? 'waiting'
  return <Panel title='Vida y escudo' icon={<HeartPulse size={17} />} action={<StatusBadge status={status} />}><div className='vitals'>{valueBlock('health', 'Vida', HeartPulse)}{valueBlock('shield', 'Escudo', Shield)}</div>{data?.healthAlertActive && <div className='inline-alert critical'><AlertTriangle size={14} /> Vida baja: busca cobertura.</div>}<div className='panel-foot'>Lectura del HUD · Actualizado {time(data?.timestamp)}</div></Panel>
}

export function InventoryPanel({ data }: { data: InventoryData | null }) {
  const status = data?.status ?? 'waiting'
  const image = data?.inventoryImage ?? data?.image
  const items = data?.items ?? []
  const occupied = items.filter((item) => item?.occupied).length
  const categories = [...new Set(items.filter((item) => item?.occupied && item.category).map((item) => item?.category))]
  const message = !data ? 'Esperando captura del inventario.' : !image ? (status === 'processing' ? 'Analizando inventario' : 'Inventario no visible') : data.recommendation ?? (occupied <= 1 ? 'Poca munición u objetos detectados.' : 'Inventario equilibrado')
  return <Panel title='Inventario' icon={<Box size={17} />} action={<StatusBadge status={status} />}>
    {image ? <div className='inventory-preview'><img src={image} alt='Captura horizontal del inventario completo de Fortnite' /></div> : <EmptyState text={message} />}
    <div className='inventory-summary'><strong>{occupied}/{items.length || 5} espacios ocupados</strong>{categories.length > 0 && <span>Equipamiento: {categories.slice(0, 2).join(' · ')}</span>}<span>{message}</span></div>
    <div className='panel-foot'>Actualizado {time(data?.timestamp)}</div>
  </Panel>
}

export function BinaryModelPanel({ title, icon, data, empty }: { title: string; icon: ReactNode; data: BinaryPrediction | null; empty: string }) {
  return <Panel title={title} icon={icon} action={data && <StatusBadge status={data.status} />}>{!data ? <EmptyState text={empty} /> : <><EmptyState compact text={data.reason ?? (data.status === 'ready' ? 'Módulo activo y alimentando el análisis general.' : statusText[data.status] ?? 'Esperando datos')} /><div className='panel-foot'>Actualizado {time(data.timestamp)}</div></>}</Panel>
}

export function MapPanel({ data }: { data: BinaryPrediction & { image?: string } | null }) {
  const status = data?.status ?? 'waiting'
  const mapText = !data?.image ? 'Mapa no visible' : data.status === 'ready' ? 'Analizando ubicación' : statusText[data.status] ?? 'Esperando datos'
  return <Panel title='Mapa' icon={<Activity size={17} />} action={<StatusBadge status={status} />}><div className='map-card-preview'>{data?.image ? <img src={data.image} alt='Captura clara del minimapa de Fortnite' /> : <EmptyState text={mapText} />}</div><div className='map-summary'><strong>{mapText}</strong><span>Zona y posición: información disponible en la captura</span></div><div className='panel-foot'>Actualizado {time(data?.timestamp)}</div></Panel>
}

export function AudioPanel({ data }: { data: BinaryPrediction | null }) {
  const status = data?.status ?? 'unavailable'
  const label = !data ? 'Esperando captura de audio del sistema' : status === 'silence' ? 'Ambiente tranquilo' : status === 'ready' || status === 'available' ? data.predictedClass ? `Evento detectado: ${data.predictedClass}` : 'Capturando audio' : status === 'device_unavailable' ? 'Dispositivo no disponible' : status === 'device_search' ? 'Esperando dispositivo' : status === 'inference' ? 'Procesando audio' : status === 'model_missing' ? 'Modelo no disponible' : 'Sin señal'
  const waveform = data?.waveform ?? []
  return <Panel title='Audio' icon={<Volume2 size={17} />} action={<StatusBadge status={status} />}>
    {!data ? <EmptyState text='Esperando captura de audio del sistema.' /> : <><div className='audio-status-line'><strong>{label}</strong><span>Fuente: WASAPI Loopback{data.device ? ` · ${data.device}` : ''}</span></div><div className='audio-meter'><span>Intensidad</span><div><i style={{ width: `${Math.min(100, Math.max(0, data.level ?? 0))}%` }} /></div><b>{Math.round(data.level ?? 0)}%</b></div>{waveform.length > 0 ? <div className='audio-waveform' aria-label='Forma de onda capturada' style={{ display: 'flex', alignItems: 'center', gap: 2, height: 28, marginTop: 10, overflow: 'hidden' }}>{waveform.map((value, index) => <i key={index} style={{ display: 'block', flex: 1, minWidth: 1, height: `${Math.max(4, Math.min(100, Math.abs(value) * 1000))}%`, background: 'var(--cyan)', opacity: 0.75 }} />)}</div> : <EmptyState compact text='Sin señal de audio reciente.' />}<div className='panel-foot'>Actualizado {time(data.timestamp)}</div></>}
  </Panel>
}

export function SequencePanel({ data, onOpen }: { data: SequenceData | null; onOpen: (image: string, label: string) => void }) {
  const total = data?.frames.length ?? 0
  const complete = total >= 6
  return <Panel title='Secuencia de seis frames' icon={<Activity size={17} />} action={<StatusBadge status={data?.status ?? 'waiting'} />}>{!data ? <EmptyState text='Esperando nuevos frames.' /> : <><div className='frames-grid'>{data.frames.map((frame) => <button className={'frame-card frame-' + frame.status} key={frame.id} onClick={() => onOpen(frame.image, 'Frame ' + frame.index)} aria-label={'Ampliar Frame ' + frame.index}><img src={frame.image} alt={'Frame ' + frame.index} /><span className='frame-number'>0{frame.index}</span><span className='frame-time'>{time(frame.timestamp)}</span>{frame.index === total && <span className='frame-latest'>Más reciente</span>}{frame.status === 'processing' && <span className='frame-processing'>Procesando</span>}<Maximize2 size={14} /></button>)}</div><div className='sequence-footer'><div><span>{complete ? 'Secuencia completa · Analizando movimiento' : `Recopilando secuencia: ${total} de 6`}</span><strong>{complete ? 'Esperando nuevos frames' : 'Esperando datos'}</strong></div><span>Actualizado {time(data.timestamp)}</span></div></>}</Panel>
}

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  return <Panel title='Alertas' eyebrow='SEÑALES DE ANÁLISIS' icon={<AlertTriangle size={17} />}><div className='alerts-list'>{alerts.length ? alerts.slice(0, 3).map((alert) => <div className={'alert-item ' + alert.severity} key={alert.id}><AlertTriangle size={16} /><div><strong>{alert.title}</strong><span>{alert.message}</span><small>{'repeatCount' in alert && Number(alert.repeatCount) > 1 ? `Detectado ${alert.repeatCount} veces` : 'Primera detección'}</small></div><time>{time(alert.timestamp)}</time></div>) : <EmptyState text='Sin alertas activas.' compact />}</div></Panel>
}

export function RecommendationsPanel({ recommendations }: { recommendations: Recommendation[] }) {
  return <Panel title='Recomendaciones' eyebrow='ASISTENCIA ACCIONABLE' icon={<Sparkles size={17} />}><div className='recommendations-list'>{recommendations.length ? recommendations.map((item) => <div className='recommendation-item' key={item.id}><div className={'priority priority-' + item.priority}>{item.priority}</div><div className='recommendation-copy'><strong>{item.text}</strong><span>{item.explanation}</span><small>{item.source} · {time(item.timestamp)} · Vigencia {item.validity}{'repeatCount' in item && Number(item.repeatCount) > 1 ? ` · ${item.repeatCount} detecciones` : ''}</small></div><ChevronRight size={16} /></div>) : <EmptyState text='Esperando recomendaciones del backend.' compact />}</div></Panel>
}

export function Modal({ image, label, onClose }: { image: string; label: string; onClose: () => void }) {
  return <div className='modal-backdrop' role='dialog' aria-modal='true' aria-label={label} onClick={onClose}><div className='modal-card' onClick={(event) => event.stopPropagation()}><button className='icon-button modal-close' onClick={onClose} aria-label='Cerrar visor'><XCircle size={20} /></button><img src={image} alt={label} /><strong>{label}</strong></div></div>
}
