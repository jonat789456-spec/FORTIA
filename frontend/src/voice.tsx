/* eslint-disable react-refresh/only-export-components */
import { useEffect, useRef, useState } from 'react'
import { Pause, Play, Settings2, Volume2, VolumeX, X } from 'lucide-react'
import { useDashboardStore } from './store'
import type { DashboardState, MainClass } from './types'

export type VoiceMode = 'critical' | 'alerts' | 'full'
export type VoicePriority = 'critical' | 'high' | 'medium' | 'low'

export interface VoiceSettings {
  enabled: boolean
  volume: number
  rate: number
  pitch: number
  mode: VoiceMode
  normalCooldownMs: number
  criticalCooldownMs: number
  duplicateWindowMs: number
  probabilityDelta: number
  maxMessagesPerMinute: number
  voiceName: string
}

export interface VoiceViewState {
  supported: boolean
  speaking: boolean
  currentMessage: string
  voices: SpeechSynthesisVoice[]
  settings: VoiceSettings
}

const STORAGE_KEY = 'fortia.voice.settings'
const DEFAULT_SETTINGS: VoiceSettings = { enabled: false, volume: 0.7, rate: 1, pitch: 1, mode: 'alerts', normalCooldownMs: 8000, criticalCooldownMs: 4000, duplicateWindowMs: 30000, probabilityDelta: 0.1, maxMessagesPerMinute: 6, voiceName: '' }
const classLabels: Record<MainClass, string> = { eliminated: 'Eliminado', elimination: 'Eliminación', victory: 'Victoria' }

function loadSettings(): VoiceSettings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<VoiceSettings>
    return { ...DEFAULT_SETTINGS, ...saved }
  } catch { return DEFAULT_SETTINGS }
}

function saveSettings(settings: VoiceSettings) {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)) } catch { /* almacenamiento opcional */ }
}

function percentage(value: number) { return Math.round(Math.max(0, Math.min(1, value)) * 100) }
function riskLevel(value: number) { return value >= 0.8 ? 'critical' : value >= 0.6 ? 'high' : value >= 0.4 ? 'medium' : 'low' }
function riskText(value: number) {
  const level = riskLevel(value)
  if (level === 'critical') return 'Riesgo crítico de eliminación. Busca cobertura inmediatamente.'
  if (level === 'high') return 'Hay una alta probabilidad de ser eliminado. Busca cobertura.'
  if (level === 'medium') return 'El riesgo de ser eliminado está aumentando. Mantente atento y busca una posición segura.'
  return 'El riesgo de ser eliminado es bajo. La situación se mantiene favorable.'
}
function isCritical(priority: VoicePriority) { return priority === 'critical' }

type VoiceMessage = { text: string; priority: VoicePriority; key: string; createdAt: number; expiresAt: number }
type Listener = (state: VoiceViewState) => void

export class VoiceAssistant {
  private settings: VoiceSettings = loadSettings()
  private readonly listener: Listener
  private readonly supported = typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
  private voices: SpeechSynthesisVoice[] = []
  private queue: VoiceMessage[] = []
  private recent = new Map<string, number>()
  private spokenAt: number[] = []
  private speaking = false
  private currentMessage = ''
  private previousState: DashboardState | null = null
  private candidateClass: MainClass | null = null
  private candidateCount = 0
  private announcedClass: MainClass | null = null
  private lastRisk: string | null = null
  private lastHealthLevel: string | null = null
  private lastShieldLevel: string | null = null
  private lastInventoryRecommendation = ''
  private seenAlerts = new Set<string>()
  private seenRecommendations = new Set<string>()
  private announcedModalities = new Set<string>()
  private lastCaptureAvailable = false
  private readonly onVoicesChanged = () => this.refreshVoices()

  constructor(listener: Listener) {
    this.listener = listener
    this.refreshVoices()
    if (this.supported) window.speechSynthesis.addEventListener('voiceschanged', this.onVoicesChanged)
    this.publish()
  }

  get settingsValue() { return this.settings }
  get viewState(): VoiceViewState { return { supported: this.supported, speaking: this.speaking, currentMessage: this.currentMessage, voices: this.voices, settings: this.settings } }

  private publish() { this.listener(this.viewState) }
  private refreshVoices() { if (this.supported) this.voices = window.speechSynthesis.getVoices().filter((voice) => /^es(-|_)/i.test(voice.lang) || /español|spanish/i.test(voice.name)); this.publish() }

  updateSettings(patch: Partial<VoiceSettings>) {
    this.settings = { ...this.settings, ...patch }
    saveSettings(this.settings)
    if (!this.settings.enabled || this.settings.volume === 0) this.stop()
    this.publish()
  }

  activate() {
    this.updateSettings({ enabled: true })
    this.enqueue({ text: 'FORTIA está listo. El análisis en tiempo real ha comenzado.', priority: 'medium', key: 'assistant-ready', expiresAt: Date.now() + 15000 })
  }

  test() { this.enqueue({ text: 'Asistente de voz de FORTIA activado. Las alertas importantes se comunicarán en español.', priority: 'high', key: `voice-test-${Date.now()}`, expiresAt: Date.now() + 15000 }) }
  stop() { if (this.supported) window.speechSynthesis.cancel(); this.queue = []; this.speaking = false; this.currentMessage = ''; this.publish() }
  dispose() { this.stop(); if (this.supported) window.speechSynthesis.removeEventListener('voiceschanged', this.onVoicesChanged) }

  private allowed(priority: VoicePriority) {
    if (this.settings.mode === 'critical') return isCritical(priority)
    if (this.settings.mode === 'alerts') return priority === 'critical' || priority === 'high' || priority === 'medium'
    return true
  }

  private enqueue(input: Omit<VoiceMessage, 'createdAt'>) {
    if (!this.supported || !this.settings.enabled || !this.allowed(input.priority)) return
    const now = Date.now()
    const recentTime = this.recent.get(input.key) ?? 0
    if (now - recentTime < this.settings.duplicateWindowMs) return
    this.spokenAt = this.spokenAt.filter((time) => now - time < 60000)
    if (!isCritical(input.priority) && this.spokenAt.length >= this.settings.maxMessagesPerMinute) return
    this.recent.set(input.key, now)
    const message: VoiceMessage = { ...input, createdAt: now, expiresAt: input.expiresAt ?? now + 30000 }
    if (isCritical(input.priority)) this.queue = this.queue.filter((item) => isCritical(item.priority))
    this.queue.push(message)
    this.queue.sort((a, b) => ({ critical: 0, high: 1, medium: 2, low: 3 }[a.priority] - ({ critical: 0, high: 1, medium: 2, low: 3 }[b.priority]) || a.createdAt - b.createdAt))
    this.processQueue()
  }

  private processQueue() {
    if (this.speaking || !this.supported || !this.settings.enabled) return
    const next = this.queue.find((item) => item.expiresAt > Date.now())
    this.queue = this.queue.filter((item) => item.expiresAt > Date.now())
    if (!next) return
    const last = this.spokenAt.at(-1) ?? 0
    const cooldown = isCritical(next.priority) ? this.settings.criticalCooldownMs : this.settings.normalCooldownMs
    if (Date.now() - last < cooldown && !isCritical(next.priority)) { window.setTimeout(() => this.processQueue(), cooldown - (Date.now() - last)); return }
    this.queue = this.queue.filter((item) => item !== next)
    const utterance = new SpeechSynthesisUtterance(next.text)
    utterance.lang = this.settings.voiceName ? (this.voices.find((voice) => voice.name === this.settings.voiceName)?.lang ?? 'es-MX') : 'es-MX'
    utterance.voice = this.voices.find((voice) => voice.name === this.settings.voiceName) ?? this.voices[0] ?? null
    utterance.volume = this.settings.volume
    utterance.rate = this.settings.rate
    utterance.pitch = this.settings.pitch
    this.speaking = true; this.currentMessage = next.text; this.spokenAt.push(Date.now()); this.publish()
    utterance.onend = () => { this.speaking = false; this.currentMessage = ''; this.publish(); this.processQueue() }
    utterance.onerror = () => { this.speaking = false; this.currentMessage = ''; this.publish(); this.processQueue() }
    window.speechSynthesis.speak(utterance)
  }

  handleState(next: DashboardState, previous: DashboardState | null = this.previousState) {
    this.previousState = next
    if (!previous) return
    if (next.connection === 'ready' && ['offline', 'reconnecting', 'error'].includes(previous.connection)) this.enqueue({ text: 'Conexión recuperada. El análisis continúa.', priority: 'high', key: 'connection-recovered', expiresAt: Date.now() + 15000 })
    if (['offline', 'reconnecting', 'error'].includes(next.connection) && !['offline', 'reconnecting', 'error'].includes(previous.connection)) this.enqueue({ text: 'Se perdió la conexión con el servidor. Intentando reconectar.', priority: 'high', key: 'connection-lost', expiresAt: Date.now() + 15000 })
    if (next.sessionStatus === 'analyzing' && previous.sessionStatus !== 'analyzing') this.enqueue({ text: 'FORTIA fue detectado. El análisis en tiempo real ha comenzado.', priority: 'medium', key: 'analysis-started', expiresAt: Date.now() + 15000 })
    this.handleCapture(next)
    this.handlePrediction(next.mainPrediction, previous.mainPrediction)
    this.handleHealth(next.healthShield, previous.healthShield)
    this.handleInventory(next.inventory)
    this.handleModalities(next)
    this.handleAlerts(next)
    this.handleRecommendations(next)
  }

  private handleCapture(state: DashboardState) {
    if (state.stream.available && !this.lastCaptureAvailable) this.enqueue({ text: 'Captura de Fortnite disponible. El análisis visual está activo.', priority: 'high', key: 'capture-started', expiresAt: Date.now() + 15000 })
    if (!state.stream.available && this.lastCaptureAvailable && state.sessionStatus === 'analyzing') this.enqueue({ text: 'No se detectó la ventana de Fortnite. Verifica que el juego esté abierto.', priority: 'high', key: 'capture-lost', expiresAt: Date.now() + 15000 })
    this.lastCaptureAvailable = state.stream.available
  }

  private handlePrediction(data: DashboardState['mainPrediction'], previous: DashboardState['mainPrediction']) {
    if (!data || !['ready', 'available'].includes(data.status) || (data.confidence ?? 0) < 0.75) return
    if (data.predictedClass !== this.candidateClass) { this.candidateClass = data.predictedClass; this.candidateCount = 1 } else this.candidateCount += 1
    const margin = data.predictedClass === 'eliminated' ? data.eliminatedProbability : data.predictedClass === 'elimination' ? data.eliminationProbability : data.victoryProbability
    const previousMargin = previous?.predictedClass === 'eliminated' ? previous.eliminatedProbability : previous?.predictedClass === 'elimination' ? previous.eliminationProbability : previous?.victoryProbability
    const firstAnnouncement = this.announcedClass === null
    if (this.candidateCount >= 3 && this.announcedClass !== data.predictedClass && (firstAnnouncement || !previous || margin - (previousMargin ?? 0) >= 0.08)) { this.announcedClass = data.predictedClass; this.enqueue({ text: `${firstAnnouncement ? 'La predicción principal es' : 'La predicción principal cambió a'} ${classLabels[data.predictedClass]}, con una confianza del ${percentage(data.confidence)} por ciento.`, priority: 'high', key: `class-${data.predictedClass}`, expiresAt: Date.now() + 20000 }) }
    const risk = data.eliminatedProbability
    const level = riskLevel(risk)
    if (this.lastRisk === null || (level !== this.lastRisk && (level === 'critical' || level === 'high' || this.lastRisk === 'critical' || Math.abs(risk - (previous?.eliminatedProbability ?? risk)) >= this.settings.probabilityDelta))) { this.enqueue({ text: riskText(risk), priority: level === 'critical' ? 'critical' : level === 'high' ? 'high' : 'medium', key: `risk-${level}`, expiresAt: Date.now() + 20000 }) }
    if (previous && Math.abs(data.eliminationProbability - previous.eliminationProbability) >= this.settings.probabilityDelta) this.enqueue({ text: `La probabilidad de conseguir una eliminación ${data.eliminationProbability > previous.eliminationProbability ? 'aumentó' : 'disminuyó'} al ${percentage(data.eliminationProbability)} por ciento.`, priority: 'medium', key: `elimination-prob-${Math.round(data.eliminationProbability * 10)}`, expiresAt: Date.now() + 20000 })
    if (previous && Math.abs(data.victoryProbability - previous.victoryProbability) >= this.settings.probabilityDelta) this.enqueue({ text: `La probabilidad de victoria ${data.victoryProbability > previous.victoryProbability ? 'aumentó' : 'disminuyó'} al ${percentage(data.victoryProbability)} por ciento.`, priority: 'medium', key: `victory-prob-${Math.round(data.victoryProbability * 10)}`, expiresAt: Date.now() + 20000 })
    this.lastRisk = level
  }

  private handleHealth(data: DashboardState['healthShield'], previous: DashboardState['healthShield']) {
    const valid = (reading: NonNullable<DashboardState['healthShield']>['healthReading']) => !!reading && ['current', 'estimated'].includes(reading.status) && reading.value != null && reading.confidence >= 0.55
    if (!data || (!valid(data.healthReading) && !valid(data.shieldReading))) return
    const health = data.healthReading?.value ?? data.healthValue ?? data.health
    const shield = data.shieldReading?.value ?? data.shieldValue ?? data.shield
    const healthLevel = !valid(data.healthReading) || health == null ? 'unknown' : data.healthAlertActive ? (health < 20 ? 'critical' : 'low') : 'safe'
    const shieldLevel = !valid(data.shieldReading) || shield == null ? 'unknown' : data.shieldAlertActive ? 'low' : 'safe'
    if (healthLevel !== this.lastHealthLevel && (healthLevel === 'critical' || healthLevel === 'low')) this.enqueue({ text: healthLevel === 'critical' ? 'Tu vida está en nivel crítico. Evita un nuevo enfrentamiento.' : 'Tu vida está baja. Busca recuperación y evita exponerte.', priority: healthLevel === 'critical' ? 'critical' : 'high', key: `health-${healthLevel}`, expiresAt: Date.now() + 20000 })
    if (shieldLevel !== this.lastShieldLevel && shieldLevel === 'low') this.enqueue({ text: 'Tu escudo está por debajo del nivel recomendado. Busca protección antes de continuar.', priority: 'high', key: 'shield-low', expiresAt: Date.now() + 20000 })
    if (previous && healthLevel === 'safe' && this.lastHealthLevel && this.lastHealthLevel !== 'safe') this.enqueue({ text: 'Tu nivel de vida se ha estabilizado.', priority: 'medium', key: 'health-recovered', expiresAt: Date.now() + 20000 })
    this.lastHealthLevel = healthLevel; this.lastShieldLevel = shieldLevel
  }

  private handleModalities(state: DashboardState) {
    for (const [name, data] of [['audio', state.audio], ['mapa', state.map]] as const) {
      if (data && ['unavailable', 'error', 'offline'].includes(data.status) && !this.announcedModalities.has(name)) { this.announcedModalities.add(name); this.enqueue({ text: `El modelo de ${name} no está disponible. El análisis continuará con las demás señales.`, priority: 'high', key: `modality-${name}`, expiresAt: Date.now() + 20000 }) }
    }
  }

  private handleInventory(data: DashboardState['inventory']) {
    if (!data?.recommendation || data.recommendation === this.lastInventoryRecommendation) return
    this.lastInventoryRecommendation = data.recommendation
    this.enqueue({ text: `El inventario actual indica lo siguiente: ${data.recommendation}`, priority: 'medium', key: `inventory-${data.recommendation}`, expiresAt: Date.now() + 30000 })
  }

  private handleAlerts(state: DashboardState) { for (const alert of state.alerts) if (!this.seenAlerts.has(alert.id)) { this.seenAlerts.add(alert.id); this.enqueue({ text: `${alert.title}. ${alert.message}`, priority: alert.severity === 'critical' ? 'critical' : alert.severity === 'warning' ? 'high' : 'medium', key: `alert-${alert.id}`, expiresAt: Date.now() + 30000 }) } }
  private handleRecommendations(state: DashboardState) { for (const item of state.recommendations) if (!this.seenRecommendations.has(item.id)) { this.seenRecommendations.add(item.id); this.enqueue({ text: item.text + (item.explanation ? `. ${item.explanation}` : ''), priority: item.priority === 'alta' ? 'high' : item.priority === 'media' ? 'medium' : 'low', key: `recommendation-${item.id}`, expiresAt: Date.now() + 30000 }) } }
}

export function useVoiceAssistant() {
  const [, forceRender] = useState(0)
  const assistantRef = useRef<VoiceAssistant | null>(null)
  if (!assistantRef.current) assistantRef.current = new VoiceAssistant(() => forceRender((value) => value + 1))
  useEffect(() => {
    const assistant = assistantRef.current as VoiceAssistant
    const unsubscribe = useDashboardStore.subscribe((state, previous) => assistant.handleState(state, previous))
    assistant.handleState(useDashboardStore.getState(), null)
    return () => { unsubscribe(); assistant.dispose() }
  }, [])
  const assistant = assistantRef.current as VoiceAssistant
  return { assistant, state: assistant.viewState }
}

function statusLabel(view: VoiceViewState) { if (!view.supported) return 'Voz no disponible'; if (view.speaking) return 'FORTIA está hablando'; return view.settings.enabled ? 'Asistente activo' : 'Asistente desactivado' }

export function VoiceControlPanel() {
  const { assistant, state } = useVoiceAssistant()
  const [open, setOpen] = useState(false)
  const update = (patch: Partial<VoiceSettings>) => assistant.updateSettings(patch)
  return <div className='voice-control-wrap'>
    <button className={'icon-button voice-toggle ' + (state.settings.enabled ? 'active' : '')} onClick={() => setOpen((value) => !value)} aria-label='Configurar asistente de voz' title={statusLabel(state)}>{state.settings.enabled ? <Volume2 size={17} /> : <VolumeX size={17} />}</button>
    {state.speaking && <div className='voice-speaking' role='status'><Volume2 size={13} /> <span><strong>FORTIA está hablando</strong><small>{state.currentMessage}</small></span><button className='voice-stop' onClick={() => assistant.stop()} aria-label='Detener mensaje'><X size={13} /></button></div>}
    {open && <div className='voice-popover' role='dialog' aria-label='Configuración del asistente de voz'>
      <div className='voice-popover-head'><div><strong>Asistente de voz</strong><small>{statusLabel(state)}</small></div><Settings2 size={16} /></div>
      {!state.supported && <p className='voice-note'>Este navegador no ofrece síntesis de voz.</p>}
      {!state.settings.enabled ? <button className='primary-button voice-activate' onClick={() => assistant.activate()} disabled={!state.supported}><Play size={14} /> Activar asistente de voz</button> : <>
        <label className='voice-field'><span>Voz</span><select value={state.settings.voiceName} onChange={(event) => update({ voiceName: event.target.value })}><option value=''>Español predeterminada</option>{state.voices.map((voice) => <option key={voice.name} value={voice.name}>{voice.name} ({voice.lang})</option>)}</select></label>
        <label className='voice-field'><span>Volumen <b>{Math.round(state.settings.volume * 100)}%</b></span><input type='range' min='0' max='1' step='0.05' value={state.settings.volume} onChange={(event) => update({ volume: Number(event.target.value) })} /></label>
        <label className='voice-field'><span>Velocidad <b>{state.settings.rate.toFixed(1)}</b></span><input type='range' min='0.7' max='1.3' step='0.1' value={state.settings.rate} onChange={(event) => update({ rate: Number(event.target.value) })} /></label>
        <label className='voice-field'><span>Tono <b>{state.settings.pitch.toFixed(1)}</b></span><input type='range' min='0.7' max='1.3' step='0.1' value={state.settings.pitch} onChange={(event) => update({ pitch: Number(event.target.value) })} /></label>
        <label className='voice-field'><span>Frecuencia</span><select value={state.settings.mode} onChange={(event) => update({ mode: event.target.value as VoiceMode })}><option value='critical'>Solo alertas críticas</option><option value='alerts'>Alertas y recomendaciones</option><option value='full'>Narración completa</option></select></label>
        <div className='voice-actions'><button className='secondary-button' onClick={() => assistant.test()}><Play size={13} /> Probar voz</button><button className='secondary-button' onClick={() => update({ enabled: false })}><Pause size={13} /> Silenciar</button></div>
      </>}
    </div>}
  </div>
}
