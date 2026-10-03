import type { Alert, Recommendation, HealthShieldData } from './types'
import { EVENT_POLICIES, EVENT_RUNTIME_CONFIG, recommendationsConflict } from './eventConfig'
import type { EventPriority } from './eventConfig'

export type ManagedKind = 'alert' | 'recommendation'
export type ManagedPriority = EventPriority
export type ManagedState = 'active' | 'resolved'

export interface ManagedEvent {
  id: string
  semanticKey: string
  kind: ManagedKind
  category: string
  severity: ManagedPriority
  visualTitle: string
  visualMessage: string
  spokenMessage: string
  timestamp: string
  source: string
  state: ManagedState
  firstSeen: string
  lastSeen: string
  repeatCount: number
  lastSpokenAt: number | null
  cooldownMs: number
  resolvedAt?: string
  context: Record<string, unknown>
}

export interface ManagedAlert extends Alert {
  semanticKey: string
  repeatCount: number
  firstSeen: string
  lastSeen: string
  state: ManagedState
  source: string
}

export interface ManagedRecommendation extends Recommendation {
  semanticKey: string
  repeatCount: number
  firstSeen: string
  lastSeen: string
  state: ManagedState
}

type Incoming = Omit<Partial<ManagedEvent>, 'severity'> & {
  id?: string
  code?: string
  title?: string
  text?: string
  explanation?: string
  message?: string
  priority?: string
  severity?: string
  category?: string
  source?: string
  timestamp?: string
  triggerData?: Record<string, unknown>
  context?: Record<string, unknown>
}

const PRIORITY_RANK: Record<ManagedPriority, number> = { critical: 4, high: 3, medium: 2, low: 1 }
export { EVENT_POLICIES }

export interface EventDiagnostic { timestamp: string; action: string; semanticKey?: string; kind?: ManagedKind; reason?: string; priority?: ManagedPriority; repeatCount?: number; cooldownRemainingMs?: number; message?: string }

const CATEGORY_ALIASES: Array<[string, RegExp]> = [
  ['health.critical', /vida.*(cr[ií]tica|cr[ií]tico)|vida.*0|vida.*muy baja/],
  ['health.low', /vida.*(baja|poca)|salud.*baja/],
  ['shield.empty', /sin escudo|escudo.*(agotado|0|cero)/],
  ['shield.low', /escudo.*(bajo|poco)|protecci[oó]n.*disminuy/],
  ['storm.outside', /tormenta.*(fuera|da[nñ]o)|fuera.*zona/],
  ['inventory.no_healing', /sin curaci[oó]n|no.*(curaci[oó]n|consumible)/],
  ['recommendation.seek_cover', /busca cobertura|buscar cobertura|ponte a cubierto|posici[oó]n segura/],
  ['recommendation.heal', /c[uú]rate|usa curaci[oó]n|recupera.*vida/],
  ['recommendation.reload', /recarga|poca munici[oó]n|sin munici[oó]n/],
  ['audio.unavailable', /audio.*(no disponible|indisponible)|sonido.*no disponible/],
  ['model.unavailable', /modelo.*no disponible|modalidad.*no disponible/],
]

function priority(value: string | undefined, fallback: ManagedPriority): ManagedPriority {
  if (value === 'critical' || value === 'alta' || value === 'high') return value === 'alta' ? 'high' : value
  if (value === 'media' || value === 'medium') return 'medium'
  if (value === 'baja' || value === 'low') return 'low'
  return fallback
}

function semanticKey(input: Incoming): string {
  const code = String(input.code ?? input.semanticKey ?? '').trim().toLowerCase()
  const codeAliases: Record<string, string> = { low_health: 'health.low', low_shield: 'shield.low', high_elimination_risk: 'prediction.eliminated_risk', no_healing: 'inventory.no_healing', missing_modality: 'model.unavailable' }
  if (codeAliases[code]) return codeAliases[code]
  const known = Object.keys(EVENT_POLICIES).find((key) => code === key || code.replaceAll('_', '.') === key)
  if (known) return known
  const text = `${input.title ?? ''} ${input.text ?? ''} ${input.message ?? ''} ${input.explanation ?? ''}`.toLowerCase().replace(/\d+(?:[.,]\d+)?\s*%?/g, ' ')
  const match = CATEGORY_ALIASES.find(([, pattern]) => pattern.test(text))
  if (match) return match[0]
  return `generic.${String(input.category ?? input.source ?? 'event').toLowerCase().replace(/[^a-z0-9]+/g, '_')}.${text.trim().replace(/[^a-z0-9áéíóúüñ]+/gi, '_').slice(0, 48) || 'unknown'}`
}

function spokenFor(key: string, input: Incoming): string {
  const custom = String(input.spokenMessage ?? '').trim()
  if (custom) return custom
  return {
    'health.critical': 'Tu vida está crítica. Cúrate y busca cobertura.',
    'health.low': 'Tu vida está baja. Busca cobertura y cúrate.',
    'shield.empty': 'Te quedaste sin escudo. Busca cobertura.',
    'shield.low': 'Tu escudo está bajo.',
    'prediction.eliminated_risk': 'El riesgo de ser eliminado aumentó. Busca cobertura.',
    'recommendation.seek_cover': 'Busca cobertura.',
    'recommendation.heal': 'Cúrate en cuanto puedas.',
    'recommendation.reload': 'Tienes poca munición. Recarga.',
    'inventory.no_healing': 'No se detectó curación disponible.',
    'audio.unavailable': 'El audio no está disponible; continuaré con las demás señales.',
    'model.unavailable': 'Una modalidad no está disponible; el análisis continúa.',
  }[key] ?? String(input.text ?? input.title ?? input.message ?? 'Nueva alerta')
}

function nowIso() { return new Date().toISOString() }

export class EventManager {
  private events = new Map<string, ManagedEvent>()
  private pendingSpeech: ManagedEvent[] = []
  private diagnostics: EventDiagnostic[] = []

  private log(entry: Omit<EventDiagnostic, 'timestamp'>) {
    this.diagnostics.push({ timestamp: nowIso(), ...entry })
    if (this.diagnostics.length > EVENT_RUNTIME_CONFIG.maxDiagnostics) this.diagnostics.splice(0, this.diagnostics.length - EVENT_RUNTIME_CONFIG.maxDiagnostics)
  }

  getDiagnostics() { return [...this.diagnostics] }
  recordVoicePlayback(action: 'speech_start' | 'speech_end' | 'speech_interrupted', event: { semanticKey?: string; message?: string }) { this.log({ action, semanticKey: event.semanticKey, message: event.message }) }

  reset() { this.events.clear(); this.pendingSpeech = []; this.diagnostics = [] }

  ingest(input: Incoming, kind: ManagedKind): ManagedEvent {
    const timestamp = input.timestamp ?? nowIso()
    const key = semanticKey(input)
    const policy = EVENT_POLICIES[key] ?? { priority: priority(input.priority ?? input.severity, 'medium'), cooldownMs: 30000, reminderMs: 60000, interrupt: false }
    const incomingPriority = priority(input.priority ?? input.severity, policy.priority)
    const previous = this.events.get(`${kind}:${key}`)
    const event: ManagedEvent = previous && previous.state === 'active' ? {
      ...previous,
      severity: PRIORITY_RANK[incomingPriority] > PRIORITY_RANK[previous.severity] ? incomingPriority : previous.severity,
      visualTitle: String(input.title ?? previous.visualTitle),
      visualMessage: String(input.message ?? input.text ?? input.title ?? previous.visualMessage),
      spokenMessage: spokenFor(key, input),
      timestamp,
      lastSeen: timestamp,
      repeatCount: previous.repeatCount + 1,
      context: { ...previous.context, ...(input.context ?? input.triggerData ?? {}) },
    } : {
      id: String(input.id ?? `${kind}-${key}-${Date.now()}`),
      semanticKey: key,
      kind,
      category: String(input.category ?? key.split('.')[0]),
      severity: incomingPriority,
      visualTitle: String(input.title ?? key),
      visualMessage: String(input.message ?? input.text ?? input.explanation ?? input.title ?? 'Evento del sistema'),
      spokenMessage: spokenFor(key, input),
      timestamp,
      source: String(input.source ?? 'FORTIA'),
      state: 'active',
      firstSeen: timestamp,
      lastSeen: timestamp,
      repeatCount: 1,
      lastSpokenAt: null,
      cooldownMs: policy.cooldownMs,
      context: { ...(input.context ?? input.triggerData ?? {}) },
    }
    const escalated = previous && PRIORITY_RANK[event.severity] > PRIORITY_RANK[previous.severity]
    const shouldSpeak = !previous || previous.state === 'resolved' || Boolean(escalated) || (event.lastSpokenAt != null && Date.now() - event.lastSpokenAt >= policy.reminderMs && policy.reminderMs > 0)
    this.events.set(`${kind}:${key}`, event)
    this.log({ action: shouldSpeak ? 'queued' : 'suppressed', semanticKey: key, kind, priority: event.severity, repeatCount: event.repeatCount, reason: !previous ? 'first_seen' : escalated ? 'severity_escalation' : shouldSpeak ? 'reminder' : 'consecutive_duplicate' })
    if (shouldSpeak) {
      this.pendingSpeech = this.pendingSpeech.filter((item) => !(item.kind === kind && item.semanticKey === key))
      this.pendingSpeech.push({ ...event, lastSpokenAt: Date.now() })
      this.pendingSpeech.sort((a, b) => PRIORITY_RANK[b.severity] - PRIORITY_RANK[a.severity] || b.lastSeen.localeCompare(a.lastSeen))
      if (this.pendingSpeech.length > EVENT_RUNTIME_CONFIG.maxPendingSpeech) this.pendingSpeech.splice(EVENT_RUNTIME_CONFIG.maxPendingSpeech)
    }
    return event
  }

  resolve(key: string, kind?: ManagedKind) {
    for (const [id, event] of this.events) if ((!kind || event.kind === kind) && (event.semanticKey === key || id === key)) { this.events.set(id, { ...event, state: 'resolved', resolvedAt: nowIso() }); this.log({ action: 'resolved', semanticKey: event.semanticKey, kind: event.kind, reason: 'condition_cleared', repeatCount: event.repeatCount }) }
  }

  syncVitals(data: HealthShieldData) {
    const health = data.healthReading?.value ?? data.healthValue ?? null
    const shield = data.shieldReading?.value ?? data.shieldValue ?? null
    const healthCritical = health != null && health < 20
    const healthLow = health != null && (Boolean(data.healthAlertActive) || health < 40)
    const shieldEmpty = shield != null && shield <= 0
    const shieldLow = shield != null && (Boolean(data.shieldAlertActive) || shield < 30)
    if (healthCritical) this.ingest({ code: 'health.critical', title: 'Vida crítica', message: 'Vida crítica', source: 'health_shield', context: { health } }, 'alert')
    else if (healthLow) this.ingest({ code: 'health.low', title: 'Vida baja', message: `Vida baja (${Math.round(health ?? 0)})`, source: 'health_shield', context: { health } }, 'alert')
    if (shieldEmpty) this.ingest({ code: 'shield.empty', title: 'Sin escudo', message: 'Sin escudo', source: 'health_shield', context: { shield } }, 'alert')
    else if (shieldLow) this.ingest({ code: 'shield.low', title: 'Escudo bajo', message: `Escudo bajo (${Math.round(shield ?? 0)})`, source: 'health_shield', context: { shield } }, 'alert')
    if (!healthCritical && !healthLow) this.resolve('health.low', 'alert')
    if (!healthCritical) this.resolve('health.critical', 'alert')
    if (!shieldLow) this.resolve('shield.low', 'alert')
    if (!shieldEmpty) this.resolve('shield.empty', 'alert')
  }

  activeAlerts(): ManagedAlert[] { return [...this.events.values()].filter((event) => event.kind === 'alert' && event.state === 'active').sort((a, b) => PRIORITY_RANK[b.severity] - PRIORITY_RANK[a.severity] || b.lastSeen.localeCompare(a.lastSeen)).map((event) => ({ id: event.id, title: event.visualTitle, message: event.visualMessage, severity: event.severity === 'critical' ? 'critical' : event.severity === 'low' ? 'info' : 'warning', timestamp: event.lastSeen, semanticKey: event.semanticKey, repeatCount: event.repeatCount, firstSeen: event.firstSeen, lastSeen: event.lastSeen, state: event.state, source: event.source })) }
  activeRecommendations(): ManagedRecommendation[] {
    const active = [...this.events.values()].filter((event) => event.kind === 'recommendation' && event.state === 'active').sort((a, b) => PRIORITY_RANK[b.severity] - PRIORITY_RANK[a.severity] || b.lastSeen.localeCompare(a.lastSeen))
    const selected = active.filter((event, index) => index === 0 || !recommendationsConflict(active[0]?.semanticKey ?? '', event.semanticKey)).slice(0, EVENT_RUNTIME_CONFIG.maxRecommendations)
    return selected.map((event) => ({ id: event.id, text: event.visualMessage, explanation: event.context.explanation as string | undefined, priority: event.severity === 'critical' || event.severity === 'high' ? 'alta' : event.severity === 'medium' ? 'media' : 'baja', source: event.source, timestamp: event.lastSeen, validity: `${Math.round(event.cooldownMs / 1000)} s`, semanticKey: event.semanticKey, repeatCount: event.repeatCount, firstSeen: event.firstSeen, lastSeen: event.lastSeen, state: event.state }))
  }

  takeSpeechEvents(): ManagedEvent[] {
    if (!this.pendingSpeech.length) return []
    const pending = this.pendingSpeech.splice(0).filter((event) => {
      const current = this.events.get(`${event.kind}:${event.semanticKey}`)
      return event.state === 'active' && (!current || current.state === 'active')
    })
    const spokenAt = Date.now()
    for (const event of pending) {
      const id = [...this.events.entries()].find(([, current]) => current.kind === event.kind && current.semanticKey === event.semanticKey)?.[0]
      if (id) this.events.set(id, { ...this.events.get(id) as ManagedEvent, lastSpokenAt: spokenAt })
    }
    const grouped = new Map<string, ManagedEvent>()
    for (const event of pending) {
      const current = grouped.get(event.semanticKey)
      if (!current || PRIORITY_RANK[event.severity] >= PRIORITY_RANK[current.severity]) grouped.set(event.semanticKey, event)
    }
    const items = [...grouped.values()]
    const health = items.find((event) => event.semanticKey === 'health.low' || event.semanticKey === 'health.critical')
    const risk = items.find((event) => event.semanticKey === 'prediction.eliminated_risk')
    const cover = items.find((event) => event.semanticKey === 'recommendation.seek_cover')
    const heal = items.find((event) => event.semanticKey === 'recommendation.heal')
    if (health && (risk || cover || heal)) {
      const combined: ManagedEvent = { ...health, id: `group-${Date.now()}`, semanticKey: 'group.health_risk', spokenMessage: `${health.semanticKey === 'health.critical' ? 'Tu vida está crítica' : 'Tu vida está baja'}${risk ? ' y el riesgo de ser eliminado aumentó' : ''}.${cover ? ' Busca cobertura' : ''}${heal ? ' y cúrate' : ''}.`, repeatCount: Math.max(...items.map((item) => item.repeatCount)) }
      this.log({ action: 'grouped', semanticKey: 'group.health_risk', kind: 'alert', reason: 'related_events', message: combined.spokenMessage })
      return [combined, ...items.filter((event) => ![health, risk, cover, heal].includes(event))]
    }
    for (const event of items) this.log({ action: 'dispatch', semanticKey: event.semanticKey, kind: event.kind, priority: event.severity, repeatCount: event.repeatCount, message: event.spokenMessage })
    return items
  }
}

export const eventManager = new EventManager()
