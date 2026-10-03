export type EventPriority = 'critical' | 'high' | 'medium' | 'low'

export interface EventPolicy {
  priority: EventPriority
  cooldownMs: number
  reminderMs: number
  interrupt: boolean
}

export const EVENT_POLICIES: Record<string, EventPolicy> = {
  'health.critical': { priority: 'critical', cooldownMs: 8000, reminderMs: 45000, interrupt: true },
  'health.low': { priority: 'high', cooldownMs: 20000, reminderMs: 60000, interrupt: false },
  'shield.empty': { priority: 'high', cooldownMs: 10000, reminderMs: 45000, interrupt: true },
  'shield.low': { priority: 'medium', cooldownMs: 30000, reminderMs: 60000, interrupt: false },
  'prediction.eliminated_risk': { priority: 'critical', cooldownMs: 10000, reminderMs: 45000, interrupt: true },
  'recommendation.seek_cover': { priority: 'high', cooldownMs: 30000, reminderMs: 60000, interrupt: false },
  'recommendation.heal': { priority: 'high', cooldownMs: 30000, reminderMs: 60000, interrupt: false },
  'recommendation.reload': { priority: 'medium', cooldownMs: 30000, reminderMs: 60000, interrupt: false },
  'inventory.no_healing': { priority: 'medium', cooldownMs: 45000, reminderMs: 90000, interrupt: false },
  'audio.unavailable': { priority: 'low', cooldownMs: 60000, reminderMs: 0, interrupt: false },
  'model.unavailable': { priority: 'low', cooldownMs: 60000, reminderMs: 0, interrupt: false },
}

export const EVENT_RUNTIME_CONFIG = {
  maxPendingSpeech: 6,
  maxDiagnostics: 300,
  maxRecommendations: 2,
  maxVoiceAgeMs: 30000,
  voiceDefaults: { normalCooldownMs: 8000, criticalCooldownMs: 4000, duplicateWindowMs: 30000, maxMessagesPerMinute: 6 },
}

export const RECOMMENDATION_CONFLICTS: Array<[string, string]> = [
  ['recommendation.seek_cover', 'recommendation.maintain_position'],
  ['recommendation.seek_cover', 'recommendation.attack'],
  ['recommendation.heal', 'recommendation.attack'],
]

export function recommendationsConflict(a: string, b: string) {
  return RECOMMENDATION_CONFLICTS.some(([left, right]) => (left === a && right === b) || (left === b && right === a))
}
