import { create } from 'zustand'
import type { DashboardState, MainPrediction, HealthShieldData, InventoryData, BinaryPrediction, SequenceData, MapData, StreamData, Alert, Recommendation, SessionStatus, ModuleStatus } from './types'
import { eventManager } from './eventManager'

const LEGACY_MODE_KEYS = ['fortia.data.mode', 'fortia.mode', 'dataMode', 'apiMode']
for (const key of LEGACY_MODE_KEYS) {
  try { window.localStorage.removeItem(key); window.sessionStorage.removeItem(key) } catch { /* almacenamiento opcional */ }
}

const initialStream: StreamData = { sessionId: 'none', predictionId: 'none', timestamp: '', source: 'api', status: 'idle', available: false, resolution: '—', fps: 0, message: 'Presiona iniciar para conectarte a la transmisión.' }
interface DashboardActions {
  pause: () => void; resume: () => void; finish: () => void; reset: () => void; toggleSound: () => void
  setSessionId: (sessionId: string | null) => void
  setConnection: (connection: ModuleStatus) => void; setSessionStatus: (status: SessionStatus) => void; setStream: (data: StreamData) => void
  setMainPrediction: (data: MainPrediction) => void; setHealthShield: (data: HealthShieldData) => void; setInventory: (data: InventoryData) => void
  setAudio: (data: BinaryPrediction) => void; setSequence: (data: SequenceData) => void; setMap: (data: MapData) => void
  addAlert: (alert: Alert) => void; setRecommendations: (recommendations: Recommendation[]) => void; addRecommendation: (recommendation: Recommendation) => void
}
const initialState: DashboardState = { sessionStatus: 'idle', connection: 'waiting', sessionId: null, soundEnabled: true, lastUpdate: null, stream: initialStream, mainPrediction: null, healthShield: null, inventory: null, audio: null, sequence: null, map: null, alerts: [], recommendations: [] }
export const useDashboardStore = create<DashboardState & DashboardActions>((set) => ({
  ...initialState,
  pause: () => set({ sessionStatus: 'paused' }), resume: () => set({ sessionStatus: 'analyzing' }), finish: () => set({ sessionStatus: 'finished' }),
  reset: () => { eventManager.reset(); set({ ...initialState }) }, toggleSound: () => set((state) => ({ soundEnabled: !state.soundEnabled })), setSessionId: (sessionId) => set((state) => { if (sessionId && sessionId !== state.sessionId) eventManager.reset(); return { sessionId } }),
  setConnection: (connection) => set({ connection }), setSessionStatus: (sessionStatus) => set({ sessionStatus }),
  setStream: (stream) => set({ stream, lastUpdate: stream.timestamp }), setMainPrediction: (mainPrediction) => set(() => {
    if (mainPrediction.riskStatus === 'high') eventManager.ingest({ code: 'prediction.eliminated_risk', title: 'Riesgo alto de eliminación', message: 'Riesgo alto de ser eliminado', source: 'multimodal', context: { riskProbability: mainPrediction.riskProbability } }, 'alert')
    else eventManager.resolve('prediction.eliminated_risk', 'alert')
    return { mainPrediction, alerts: eventManager.activeAlerts(), lastUpdate: mainPrediction.timestamp }
  }),
  setHealthShield: (healthShield) => set((state) => {
    eventManager.syncVitals(healthShield)
    const previousCapturedAt = state.healthShield?.capturedAt
    if (previousCapturedAt !== undefined && healthShield.capturedAt !== undefined && healthShield.capturedAt < previousCapturedAt) return state
    return { healthShield, alerts: eventManager.activeAlerts(), lastUpdate: healthShield.timestamp }
  }), setInventory: (inventory) => set(() => {
    if (inventory.recommendation) eventManager.ingest({ text: inventory.recommendation, source: 'inventory', context: { explanation: inventory.recommendation } }, 'recommendation')
    return { inventory, recommendations: eventManager.activeRecommendations(), lastUpdate: inventory.timestamp }
  }),
  setAudio: (audio) => set({ audio, lastUpdate: audio.timestamp }), setSequence: (sequence) => set({ sequence, lastUpdate: sequence.timestamp }), setMap: (map) => set({ map, lastUpdate: map.timestamp }),
  addAlert: (alert) => set(() => { eventManager.ingest(alert, 'alert'); return { alerts: eventManager.activeAlerts() } }), setRecommendations: (recommendations) => set(() => { for (const item of recommendations) eventManager.ingest(item, 'recommendation'); return { recommendations: eventManager.activeRecommendations() } }), addRecommendation: (recommendation) => set(() => { eventManager.ingest(recommendation, 'recommendation'); return { recommendations: eventManager.activeRecommendations() } }),
}))
