import { validateBinary, validateMain } from './schemas'

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'
const wsBase = import.meta.env.VITE_WS_BASE_URL ?? 'ws://127.0.0.1:8000/api/v1/ws'

export class ApiError extends Error { constructor(message: string, readonly status?: number) { super(message); this.name = 'ApiError' } }
export async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController(); const timeout = window.setTimeout(() => controller.abort(), 8000)
  try {
    const response = await fetch(apiBase + path, { ...options, signal: controller.signal, headers: { 'Content-Type': 'application/json', ...options?.headers } })
    if (!response.ok) { let detail = ''; try { detail = String((await response.json() as { detail?: unknown }).detail ?? '') } catch { /* respuesta no JSON */ }; throw new ApiError(detail || `La API respondió con HTTP ${response.status}.`, response.status) }
    return await response.json() as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('La API tardó demasiado en responder.')
    throw new ApiError('No se pudo establecer conexión con la API.')
  } finally { window.clearTimeout(timeout) }
}
export interface SystemStatus { status: 'ok' | 'degraded'; captureAvailable: boolean; gpuAvailable: boolean; loadedModels: string[]; unavailableModels: string[] }
export const api = { status: () => apiRequest<SystemStatus>('/system/status'), createSession: () => apiRequest<{ sessionId: string }>('/sessions', { method: 'POST' }), start: (id: string) => apiRequest('/sessions/' + id + '/start', { method: 'POST' }), pause: (id: string) => apiRequest('/sessions/' + id + '/pause', { method: 'POST' }), resume: (id: string) => apiRequest('/sessions/' + id + '/resume', { method: 'POST' }), finish: (id: string) => apiRequest('/sessions/' + id + '/finish', { method: 'POST' }), reset: (id: string) => apiRequest('/sessions/' + id + '/reset', { method: 'POST' }) }
export function connectWebSocket(sessionId: string, onMessage: (payload: unknown) => void, onStatus: (status: 'open' | 'close' | 'error' | 'reconnecting') => void) {
  let socket: WebSocket | undefined; let stopped = false; let retry = 0; let timer: number | undefined
  const connect = () => { if (stopped) return; socket = new WebSocket(wsBase + '/sessions/' + sessionId); socket.onopen = () => { retry = 0; onStatus('open') }; socket.onclose = () => { if (!stopped) { onStatus('reconnecting'); timer = window.setTimeout(connect, Math.min(5000, 1000 + retry++ * 500)) } else onStatus('close') }; socket.onerror = () => onStatus('error'); socket.onmessage = (event) => { try { onMessage(JSON.parse(event.data)) } catch { onStatus('error') } } }
  connect(); return () => { stopped = true; if (timer) window.clearTimeout(timer); socket?.close() }
}
export function validateExternalEvent(event: unknown) { if (typeof event !== 'object' || event === null) throw new Error('Evento inválido'); const item = event as { type?: string; data?: unknown }; if (item.type === 'main_prediction.updated') return validateMain(item.data); if (item.type === 'audio_prediction.updated') return validateBinary(item.data); return item.data }
