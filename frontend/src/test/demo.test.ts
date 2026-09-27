import { describe, expect, it } from 'vitest'
import { createDemoSnapshot } from '../demo'

describe('modo demostración', () => {
  it('genera exactamente seis frames en orden', () => {
    const snapshot = createDemoSnapshot(1)
    expect(snapshot.sequence?.frames).toHaveLength(6)
    expect(snapshot.sequence?.frames.map((frame) => frame.index)).toEqual([1, 2, 3, 4, 5, 6])
  })
  it('genera probabilidades principales cercanas a 100%', () => {
    const main = createDemoSnapshot(3).mainPrediction!
    expect(main.eliminatedProbability + main.eliminationProbability + main.victoryProbability).toBeCloseTo(1)
  })
})
