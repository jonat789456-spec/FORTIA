import { validateBinary, validateMain } from './schemas'

const apiBase = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000/api/v1' : '')
const wsBase = import.meta.env.VITE_WS_BASE_URL ?? (import.meta.env.DEV ? 'ws://127.0.0.1:8000/api/v1/ws' : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws`)
const activeSockets = new Map<string, WebSocket>()
const activeVisualSockets = new Map<string, WebSocket>()

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
export const api = {
  status: () => apiRequest<SystemStatus>('/system/status'),
  createSession: () => apiRequest<{ sessionId: string }>('/sessions', { method: 'POST' }),
  start: (id: string) => apiRequest('/sessions/' + id + '/start', { method: 'POST' }),
  ingestFrame: async (id: string, frame: Blob) => {
    const controller = new AbortController(); const timeout = window.setTimeout(() => controller.abort(), 5000)
    const response = await fetch(apiBase + '/sessions/' + id + '/frames', { method: 'POST', body: frame, signal: controller.signal, headers: { 'Content-Type': frame.type || 'image/jpeg' } }).finally(() => window.clearTimeout(timeout))
    if (!response.ok) throw new ApiError('No se pudo enviar el frame al backend.', response.status)
    return await response.json() as { accepted: boolean; frameId: number; framesDropped: number; fps: number }
  },
  pause: (id: string) => apiRequest('/sessions/' + id + '/pause', { method: 'POST' }),
  resume: (id: string) => apiRequest('/sessions/' + id + '/resume', { method: 'POST' }),
  finish: (id: string) => apiRequest('/sessions/' + id + '/finish', { method: 'POST' }),
  reset: (id: string) => apiRequest('/sessions/' + id + '/reset', { method: 'POST' }),
}
export function connectWebSocket(sessionId: string, onMessage: (payload: unknown) => void, onStatus: (status: 'open' | 'close' | 'error' | 'reconnecting') => void) {
  let socket: WebSocket | undefined; let stopped = false; let retry = 0; let timer: number | undefined; let previousStreamUrl: string | undefined
  const decodeMessage = async (event: MessageEvent<string | ArrayBuffer | Blob>) => {
    if (typeof event.data === 'string') { onMessage(JSON.parse(event.data)); return }
    const bytes = event.data instanceof Blob ? new Uint8Array(await event.data.arrayBuffer()) : new Uint8Array(event.data)
    const separator = bytes.indexOf(10)
    if (separator < 1) throw new Error('Frame binario sin cabecera')
    const metadata = JSON.parse(new TextDecoder().decode(bytes.slice(0, separator))) as { data?: Record<string, unknown> }
    const objectUrl = URL.createObjectURL(new Blob([bytes.slice(separator + 1)], { type: 'image/jpeg' }))
    if (previousStreamUrl) URL.revokeObjectURL(previousStreamUrl)
    previousStreamUrl = objectUrl
    metadata.data = { ...(metadata.data ?? {}), image: objectUrl }
    onMessage(metadata)
  }
  const connect = () => { if (stopped) return; socket = new WebSocket(wsBase + '/sessions/' + sessionId); socket.binaryType = 'arraybuffer'; activeSockets.set(sessionId, socket); socket.onopen = () => { retry = 0; onStatus('open') }; socket.onclose = () => { if (!stopped) { onStatus('reconnecting'); timer = window.setTimeout(connect, Math.min(5000, 1000 + retry++ * 500)) } else onStatus('close') }; socket.onerror = () => onStatus('error'); socket.onmessage = (event) => { void decodeMessage(event).catch(() => onStatus('error')) } }
    connect(); return () => { stopped = true; if (timer) window.clearTimeout(timer); activeSockets.delete(sessionId); socket?.close(); if (previousStreamUrl) URL.revokeObjectURL(previousStreamUrl) }
}
export function sendWebSocketCommand(sessionId: string, message: Record<string, unknown>) { const socket = activeSockets.get(sessionId); if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message)) }
export function connectVisualWebSocket(sessionId: string, onFrame: (payload: Record<string, unknown>) => void, onStatus: (status: 'open' | 'close' | 'error' | 'reconnecting') => void) {
  let socket: WebSocket | undefined; let stopped = false; let retry = 0; let timer: number | undefined; let previousStreamUrl: string | undefined; let lastSequence = 0; let discardedFrames = 0
  const decodeFrame = (event: MessageEvent<ArrayBuffer>) => {
    const bytes = new Uint8Array(event.data)
    const separator = bytes.indexOf(10)
    if (separator < 1) throw new Error('Frame binario sin cabecera')
    const metadata = JSON.parse(new TextDecoder().decode(bytes.slice(0, separator))) as { type?: string; data?: Record<string, unknown> }
    const data = metadata.data ?? {}
    const sequence = Number(data.frameId ?? 0)
    if (metadata.type !== 'stream.updated' || !Number.isFinite(sequence)) return
    if (sequence <= lastSequence) { discardedFrames += 1; return }
    lastSequence = sequence
    const objectUrl = URL.createObjectURL(new Blob([bytes.slice(separator + 1)], { type: 'image/jpeg' }))
    if (previousStreamUrl) URL.revokeObjectURL(previousStreamUrl)
    previousStreamUrl = objectUrl
    onFrame({ ...data, image: objectUrl, receivedAt: Date.now() / 1000, receivedBytes: bytes.length - separator - 1, framesDuplicated: discardedFrames, transport: 'binary' })
  }
  const connect = () => { if (stopped) return; socket = new WebSocket(wsBase + '/sessions/' + sessionId + '/visual'); socket.binaryType = 'arraybuffer'; activeVisualSockets.set(sessionId, socket); socket.onopen = () => { retry = 0; onStatus('open') }; socket.onclose = () => { if (!stopped) { onStatus('reconnecting'); timer = window.setTimeout(connect, Math.min(5000, 1000 + retry++ * 500)) } else onStatus('close') }; socket.onerror = () => onStatus('error'); socket.onmessage = (event) => { try { decodeFrame(event) } catch { onStatus('error') } } }
  connect(); return () => { stopped = true; if (timer) window.clearTimeout(timer); activeVisualSockets.delete(sessionId); socket?.close(); if (previousStreamUrl) URL.revokeObjectURL(previousStreamUrl) }
}
export function validateExternalEvent(event: unknown) { if (typeof event !== 'object' || event === null) throw new Error('Evento inválido'); const item = event as { type?: string; data?: unknown }; if (item.type === 'main_prediction.updated') return validateMain(item.data); if (item.type === 'audio_prediction.updated') return validateBinary(item.data); return item.data }
