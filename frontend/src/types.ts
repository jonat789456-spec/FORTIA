export type ModuleStatus = 'idle' | 'waiting' | 'processing' | 'ready' | 'available' | 'stale' | 'low_confidence' | 'not_detected' | 'not_applicable' | 'unavailable' | 'error' | 'offline' | 'reconnecting'
export type SessionStatus = 'idle' | 'waiting' | 'analyzing' | 'paused' | 'finished' | 'offline' | 'reconnecting'
export type MainClass = 'eliminated' | 'elimination' | 'victory'
export interface Meta { sessionId: string; predictionId: string; timestamp: string; source: string; status: ModuleStatus; modelVersion?: string }
export interface BinaryPrediction extends Meta { winProbability?: number; lossProbability?: number; reason?: string; dataStale?: boolean; predictionConfidence?: number }
export interface MainPrediction extends Meta { predictedClass: MainClass; eliminatedProbability: number; eliminationProbability: number; victoryProbability: number; confidence: number; latencyMs: number }
export interface HealthReading { value: number | null; rawValue?: number | null; confidence: number; quality?: 'high' | 'medium' | 'low' | 'none'; method?: string; source?: string; status: string; reason?: string | null; stableCount?: number; validCount?: number; ageMs?: number | null }
export interface VitalState { current: number | null; max: number | null; confidence: number; status: string; ageMs?: number | null; source?: string; reason?: string | null }
export interface HealthShieldData extends BinaryPrediction { health?: VitalState | number | null; shield?: VitalState | number | null; overshield?: VitalState | null; healthCurrent?: number | null; healthMax?: number | null; shieldCurrent?: number | null; shieldMax?: number | null; overshieldCurrent?: number | null; overshieldMax?: number | null; healthValue?: number | null; shieldValue?: number | null; confidence?: number; healthConfidence?: number; shieldConfidence?: number; healthReading?: HealthReading; shieldReading?: HealthReading; healthAlertActive?: boolean; shieldAlertActive?: boolean; trend?: number[]; regionUsed?: string; processingMs?: number; capturedAt?: number; processedAt?: number; healthFramesDropped?: number }
export interface InventoryItem { id: string; name: string; rarity: string; quantity: number; ammo?: number; icon: string; position?: number; occupied?: boolean; category?: string | null; confidence?: number }
export interface InventoryData extends BinaryPrediction { items: Array<InventoryItem | null>; recommendation?: string; historicalEvidence?: string[] }
export interface FrameData { id: string; index: number; timestamp: string; status: ModuleStatus; image: string }
export interface SequenceData extends BinaryPrediction { frames: FrameData[] }
export interface MapData extends BinaryPrediction { image: string }
export interface StreamData extends Meta { available: boolean; resolution: string; fps: number; message: string; image?: string; frameId?: number; captureState?: string; captureMode?: string; framesDropped?: number }
export interface Alert { id: string; severity: 'info' | 'warning' | 'critical'; title: string; message: string; timestamp: string }
export interface Recommendation { id: string; priority: 'alta' | 'media' | 'baja'; text: string; explanation?: string; source: string; timestamp: string; validity: string }
export interface DashboardState {
  sessionStatus: SessionStatus; connection: ModuleStatus; sessionId: string | null; soundEnabled: boolean; lastUpdate: string | null
  stream: StreamData; mainPrediction: MainPrediction | null; healthShield: HealthShieldData | null; inventory: InventoryData | null
  audio: BinaryPrediction | null; sequence: SequenceData | null; map: MapData | null; alerts: Alert[]; recommendations: Recommendation[]
}
