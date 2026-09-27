import type { ModuleStatus } from './types'

export const pct = (value: number | undefined) => Math.round((value ?? 0) * 100)
export const time = (value?: string | null) => value ? new Date(value).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'
export const statusText: Partial<Record<ModuleStatus, string>> = { idle: 'Sin iniciar', waiting: 'Esperando datos', processing: 'Procesando', ready: 'Disponible', available: 'Disponible', stale: 'Desactualizado', low_confidence: 'Baja confianza', not_detected: 'No detectado', not_applicable: 'No aplica', unavailable: 'No disponible', error: 'Error', offline: 'Sin conexión', reconnecting: 'Reconectando' }
