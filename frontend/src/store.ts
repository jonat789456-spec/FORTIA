import { create } from 'zustand'
import type { DashboardState, MainPrediction, HealthShieldData, InventoryData, BinaryPrediction, SequenceData, MapData, StreamData, Alert, Recommendation, SessionStatus, ModuleStatus } from './types'

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
  reset: () => set({ ...initialState }), toggleSound: () => set((state) => ({ soundEnabled: !state.soundEnabled })), setSessionId: (sessionId) => set({ sessionId }),
  setConnection: (connection) => set({ connection }), setSessionStatus: (sessionStatus) => set({ sessionStatus }),
  setStream: (stream) => set({ stream, lastUpdate: stream.timestamp }), setMainPrediction: (mainPrediction) => set({ mainPrediction, lastUpdate: mainPrediction.timestamp }),
  setHealthShield: (healthShield) => set((state) => {
    const previousCapturedAt = state.healthShield?.capturedAt
    if (previousCapturedAt !== undefined && healthShield.capturedAt !== undefined && healthShield.capturedAt < previousCapturedAt) return state
    return { healthShield, lastUpdate: healthShield.timestamp }
  }), setInventory: (inventory) => set({ inventory, lastUpdate: inventory.timestamp }),
  setAudio: (audio) => set({ audio, lastUpdate: audio.timestamp }), setSequence: (sequence) => set({ sequence, lastUpdate: sequence.timestamp }), setMap: (map) => set({ map, lastUpdate: map.timestamp }),
  addAlert: (alert) => set((state) => ({ alerts: [alert, ...state.alerts].slice(0, 5) })), setRecommendations: (recommendations) => set({ recommendations }), addRecommendation: (recommendation) => set((state) => ({ recommendations: [recommendation, ...state.recommendations].slice(0, 10) })),
}))
