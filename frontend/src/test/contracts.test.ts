import { describe, expect, it } from 'vitest'
import { validateBinary, validateMain } from '../schemas'

describe('contratos de predicción', () => {
  const meta = { sessionId: 's1', predictionId: 'p1', timestamp: new Date().toISOString(), source: 'test', status: 'ready' as const }
  it('acepta una predicción binaria válida', () => {
    expect(validateBinary({ ...meta, winProbability: 0.7, lossProbability: 0.3 }).winProbability).toBe(0.7)
  })
  it('acepta el modelo principal cuando suma 100%', () => {
    const value = validateMain({ ...meta, predictedClass: 'victory', eliminatedProbability: 0.2, eliminationProbability: 0.3, victoryProbability: 0.5, confidence: 0.5, latencyMs: 120 })
    expect(value.eliminatedProbability + value.eliminationProbability + value.victoryProbability).toBeCloseTo(1)
  })
  it('rechaza porcentajes fuera de rango', () => {
    expect(() => validateBinary({ ...meta, winProbability: 1.4, lossProbability: 0 })).toThrow()
  })
})
