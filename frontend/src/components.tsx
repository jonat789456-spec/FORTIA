import { Activity, AlertTriangle, Box, ChevronRight, Crosshair, Gamepad2, Gauge, HeartPulse, Maximize2, Radio, Shield, Sparkles, Wifi, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { BinaryPrediction, ModuleStatus, Recommendation, MainPrediction, HealthShieldData, InventoryData, SequenceData, StreamData, Alert } from './types'

import { pct } from './ui'
const time = (value?: string | null) => value ? new Date(value).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'
const statusText: Partial<Record<ModuleStatus, string>> = { idle: 'Sin iniciar', waiting: 'Esperando datos', processing: 'Procesando', ready: 'Disponible', available: 'Disponible', stale: 'Desactualizado', low_confidence: 'Baja confianza', not_detected: 'No detectado', not_applicable: 'No aplica', unavailable: 'No disponible', error: 'Error', offline: 'Sin conexión', reconnecting: 'Reconectando' }

statusText.low_confidence = 'Baja confianza'

export function Panel({ title, eyebrow, icon, children, className = '', action }: { title: string; eyebrow?: string; icon?: ReactNode; children: ReactNode; className?: string; action?: ReactNode }) {
  return <section className={'panel ' + className}><div className='panel-heading'><div className='heading-title'>{icon}<div><span className='eyebrow'>{eyebrow}</span><h2>{title}</h2></div></div>{action}</div>{children}</section>
}

export function StatusBadge({ status }: { status: ModuleStatus }) {
  return <span className={'status-badge status-' + status}><i />{statusText[status]}</span>
}

export function BinaryPredictionView({ data }: { data: BinaryPrediction | null }) {
  if (data && (data.winProbability == null || data.lossProbability == null || data.status !== 'ready')) return <EmptyState text={data.reason ?? statusText[data.status] ?? 'No disponible'} />
  if (!data) return <EmptyState text='Aún no hay predicción disponible.' />
  return <div className='binary-prediction'><div><span>Victoria</span><strong className='text-green'>{pct(data.winProbability!)}%</strong></div><div><span>Derrota</span><strong className='text-red'>{pct(data.lossProbability!)}%</strong></div></div>
}

export function ProbabilityBar({ label, value, color }: { label: string; value: number; color: string }) {
  return <div className='prob-row'><div><span>{label}</span><strong>{pct(value)}%</strong></div><div className='prob-track'><span style={{ width: pct(value) + '%', background: color }} /></div></div>
}

export function EmptyState({ text, compact = false }: { text: string; compact?: boolean }) {
  return <div className={'empty-state ' + (compact ? 'compact' : '')}><Activity size={16} /><span>{text}</span></div>
}

export function MainPredictionCard({ data }: { data: MainPrediction | null }) {
  if (!data) return <Panel title='Predicción multimodal' eyebrow='MODELO PRINCIPAL' icon={<Sparkles size={17} />}><EmptyState text='Esperando el primer resultado del modelo principal.' /></Panel>
  const label = data.predictedClass === 'victory' ? 'Victoria' : data.predictedClass === 'elimination' ? 'Eliminación' : 'Eliminado'
  return <Panel title='Predicción multimodal' eyebrow='MODELO PRINCIPAL' icon={<Sparkles size={17} />} className='main-prediction'>
    <div className={'predicted-class class-' + data.predictedClass}><div className='prediction-orb'><Crosshair size={26} /></div><div><span>Clase predicha</span><strong>{label}</strong></div><div className='confidence'><small>Confianza</small><b>{pct(data.confidence)}%</b></div></div>
    <div className='main-bars'><ProbabilityBar label='Eliminado' value={data.eliminatedProbability} color='var(--pred-eliminated)' /><ProbabilityBar label='Eliminación' value={data.eliminationProbability} color='var(--pred-elimination)' /><ProbabilityBar label='Victoria' value={data.victoryProbability} color='var(--pred-victory)' /></div>
    <div className='prediction-meta'><span><Gauge size={14} /> {data.latencyMs} ms</span><span><Activity size={14} /> Actualizado {time(data.timestamp)}</span></div>
    <p className='disclaimer'>Esta predicción es una herramienta de apoyo y no garantiza el resultado de la partida.</p>
  </Panel>
}

export function StreamViewer({ data }: { data: StreamData }) {
  return <Panel title='Vista de la partida' eyebrow='CAPTURA EN TIEMPO REAL' icon={<Radio size={17} />} className='stream-panel'>
    <div className={'stream-view ' + (data.available ? 'is-live' : '')}><div className='stream-art'>{data.image && <img src={data.image} alt='Captura actual de Fortnite' className='stream-image' />}<div className='scanline' /><div className='stream-crosshair'><Crosshair size={40} /></div><div className='stream-overlay'><span className='live-dot' /> LIVE // CAPTURE FEED</div>{!data.image && <div className='stream-placeholder'><Gamepad2 size={42} /><strong>{data.available ? 'CAPTURA ACTIVA' : 'ESPERANDO TRANSMISIÓN'}</strong><span>{data.message}</span></div>}<div className='stream-hud'><span>HP 82</span><span>SH 73</span><span>ZONE 04:18</span></div></div></div>
    <div className='stream-footer'><span><Wifi size={14} /> {data.available ? data.message : 'Señal no disponible'}</span><span>{data.resolution} · {data.fps ? data.fps + ' FPS' : 'FPS —'}</span></div>
  </Panel>
}

export function HealthPanel({ data }: { data: HealthShieldData | null }) {
  if (!data) return <Panel title='Vida y escudo' eyebrow='MODELO INDEPENDIENTE' icon={<HeartPulse size={17} />}><EmptyState text='Detectando HUD de Fortnite.' /></Panel>
  const reading = (kind: 'health' | 'shield') => kind === 'health' ? data.healthReading : data.shieldReading
  const valueFor = (kind: 'health' | 'shield') => { const legacy = kind === 'health' ? data.healthValue : data.shieldValue; const nested = kind === 'health' ? data.health : data.shield; return reading(kind)?.value ?? legacy ?? (typeof nested === 'object' && nested ? nested.current : nested) }
  const labelFor = (kind: 'health' | 'shield') => { const item = reading(kind); if (!item || item.value == null || item.status === 'stale' || item.status === 'no_reading') return 'Sin lectura reciente'; if (item.status === 'last_stable') return 'Última lectura estable'; if (item.status === 'estimated') return 'Estimado'; return 'Actual' }
  const statusClass = (kind: 'health' | 'shield') => { const item = reading(kind); if (!item || item.value == null || item.status === 'stale' || item.status === 'no_reading') return 'none'; if (item.status === 'last_stable') return 'stable'; if (item.status === 'estimated') return 'estimated'; return 'current' }
  const ageFor = (kind: 'health' | 'shield') => { const age = reading(kind)?.ageMs; return age == null ? '' : ` · hace ${(age / 1000).toFixed(1)} s` }
  const valueBlock = (kind: 'health' | 'shield', label: string, Icon: typeof HeartPulse) => { const value = valueFor(kind); const state = kind === 'health' ? data.health : data.shield; const max = typeof state === 'object' && state?.max != null ? state.max : kind === 'health' ? data.healthMax ?? 100 : data.shieldMax ?? 100; const visible = value != null && !['stale', 'no_reading'].includes(reading(kind)?.status ?? ''); const rounded = visible ? Math.round(value as number) : 0; const roundedMax = Math.round(max as number); return <div className='health-reading'><div className='vital-row'><span><Icon size={15} /> {label}</span><strong>{visible ? rounded : '—'}<small>{visible ? '/' + roundedMax : ''}</small></strong></div><div className={'health-reading-meta quality-' + statusClass(kind)}><span className='health-reading-dot' /> {labelFor(kind)}{ageFor(kind)}</div><div className={'vital-track ' + kind}><span style={{ width: (visible ? Math.min(100, rounded / Math.max(1, roundedMax) * 100) : 0) + '%' }} /></div></div> }
  const overall = data.status === 'not_detected' && valueFor('health') == null && valueFor('shield') == null ? 'not_detected' : 'available'
  return <Panel title='Vida y escudo' eyebrow='MODELO INDEPENDIENTE' icon={<HeartPulse size={17} />} action={<StatusBadge status={overall} />}><div className='vitals'>{valueBlock('health', 'Vida', HeartPulse)}{valueBlock('shield', 'Escudo', Shield)}</div>{data.healthAlertActive && <div className='inline-alert critical'><AlertTriangle size={14} /> Vida baja: busca cobertura.</div>}<div className='panel-foot'>Lecturas independientes · Actualizado {time(data.timestamp)}</div></Panel>
}

/* Legacy implementation retained only in source history; the independent reader above is the active panel.
function LegacyHealthPanel({ data }: { data: HealthShieldData | null }) {
  const readable = data?.status === 'ready' || data?.status === 'available'
  const health = data?.healthValue ?? data?.health
  const shield = data?.shieldValue ?? data?.shield
  const confidence = data?.confidence ?? 0
  if (!data || !readable || health == null || shield == null || confidence < 0.75) return <Panel title='Vida y escudo' eyebrow='MODELO INDEPENDIENTE' icon={<HeartPulse size={17} />} action={data && <StatusBadge status={data.status} />}><EmptyState text={!data ? 'Esperando datos de vida y escudo.' : data.status === 'low_confidence' ? 'Lectura de vida y escudo con baja confianza.' : data.reason ?? 'Vida y escudo no disponibles.'} />{data && <div className='panel-foot'>Actualizado {time(data.timestamp)}</div>}</Panel>
  const healthValue = Math.round(health); const shieldValue = Math.round(shield)
  return <Panel title='Vida y escudo' eyebrow='MODELO INDEPENDIENTE' icon={<HeartPulse size={17} />} action={<StatusBadge status={data.status} />}><div className='vitals'><div className='vital-row'><span><HeartPulse size={15} /> Vida</span><strong>{healthValue}<small>/100</small></strong></div><div className='vital-track health'><span style={{ width: healthValue + '%' }} /></div><div className='vital-row'><span><Shield size={15} /> Escudo</span><strong>{shieldValue}<small>/100</small></strong></div><div className='vital-track shield'><span style={{ width: shieldValue + '%' }} /></div></div>{data.healthAlertActive && <div className='inline-alert critical'><AlertTriangle size={14} /> Vida baja: busca cobertura.</div>}<div className='panel-foot'>Confianza {Math.round(confidence * 100)}% · Actualizado {time(data.timestamp)}</div></Panel>
} */

export function InventoryPanel({ data }: { data: InventoryData | null }) {
  return <Panel title='Inventario' eyebrow='MODELO INDEPENDIENTE' icon={<Box size={17} />} action={data && <StatusBadge status={data.status} />}>{!data ? <EmptyState text='Esperando inventario detectado.' /> : <><div className='inventory-grid'>{data.items.map((item, index) => <div className={'inventory-slot ' + (!item ? 'empty' : '')} data-rarity={item?.rarity} key={index}>{item ? <><img src={item.icon} alt='' /><b>{item.name}</b><small>{item.rarity}</small>{item.ammo ? <em>{item.ammo} mun.</em> : <em>x{item.quantity}</em>}</> : <><span>+</span><small>Vacío</small></>}</div>)}</div><BinaryPredictionView data={data} /><div className='recommendation-mini'><Sparkles size={14} /><span>{data.recommendation}</span></div><div className='history-note'>Evidencia histórica: ejemplos del conjunto de entrenamiento, no garantía.</div><div className='panel-foot'>Actualizado {time(data.timestamp)}</div></>}</Panel>
}

export function BinaryModelPanel({ title, icon, data, empty }: { title: string; icon: ReactNode; data: BinaryPrediction | null; empty: string }) {
  return <Panel title={title} eyebrow='MODELO INDEPENDIENTE' icon={icon} action={data && <StatusBadge status={data.status} />}>{!data ? <EmptyState text={empty} /> : <><BinaryPredictionView data={data} /><div className='panel-foot'>Actualizado {time(data.timestamp)}</div></>}</Panel>
}

export function SequencePanel({ data, onOpen }: { data: SequenceData | null; onOpen: (image: string, label: string) => void }) {
  return <Panel title='Secuencia de seis frames' eyebrow='MODELO TEMPORAL' icon={<Activity size={17} />} action={data && <StatusBadge status={data.status} />}>{!data ? <EmptyState text='Esperando la secuencia de frames.' /> : <><div className='frames-grid'>{data.frames.map((frame) => <button className={'frame-card frame-' + frame.status} key={frame.id} onClick={() => onOpen(frame.image, 'Frame ' + frame.index)} aria-label={'Ampliar Frame ' + frame.index}><img src={frame.image} alt={'Frame ' + frame.index} /><span className='frame-number'>0{frame.index}</span><span className='frame-time'>{time(frame.timestamp)}</span>{frame.status === 'processing' && <span className='frame-processing'>Procesando</span>}<Maximize2 size={14} /></button>)}</div><div className='sequence-footer'><div><span>Predicción de la secuencia completa</span><strong>{pct(data.winProbability)}% victoria <i>·</i> {pct(data.lossProbability)}% derrota</strong></div><span>Actualizado {time(data.timestamp)}</span></div></>}</Panel>
}

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  return <Panel title='Alertas' eyebrow='SEÑALES DEL SISTEMA' icon={<AlertTriangle size={17} />}><div className='alerts-list'>{alerts.length ? alerts.slice(0, 3).map((alert) => <div className={'alert-item ' + alert.severity} key={alert.id}><AlertTriangle size={16} /><div><strong>{alert.title}</strong><span>{alert.message}</span></div><time>{time(alert.timestamp)}</time></div>) : <EmptyState text='Sin alertas activas.' compact />}</div></Panel>
}

export function RecommendationsPanel({ recommendations }: { recommendations: Recommendation[] }) {
  return <Panel title='Recomendaciones' eyebrow='ASISTENCIA ACCIONABLE' icon={<Sparkles size={17} />}><div className='recommendations-list'>{recommendations.length ? recommendations.map((item) => <div className='recommendation-item' key={item.id}><div className={'priority priority-' + item.priority}>{item.priority}</div><div className='recommendation-copy'><strong>{item.text}</strong><span>{item.explanation}</span><small>{item.source} · {time(item.timestamp)} · Vigencia {item.validity}</small></div><ChevronRight size={16} /></div>) : <EmptyState text='Esperando recomendaciones del backend.' compact />}</div></Panel>
}

export function Modal({ image, label, onClose }: { image: string; label: string; onClose: () => void }) {
  return <div className='modal-backdrop' role='dialog' aria-modal='true' aria-label={label} onClick={onClose}><div className='modal-card' onClick={(event) => event.stopPropagation()}><button className='icon-button modal-close' onClick={onClose} aria-label='Cerrar visor'><XCircle size={20} /></button><img src={image} alt={label} /><strong>{label}</strong></div></div>
}
