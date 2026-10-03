import { describe, expect, it } from 'vitest'
import { EventManager } from '../eventManager'

describe('EventManager', () => {
  it('deduplica cualquier cantidad de repeticiones consecutivas', () => {
    const manager = new EventManager()
    for (let index = 0; index < 10; index += 1) manager.ingest({ code: 'LOW_SHIELD', title: 'Escudo bajo', message: `Escudo bajo (${28 - index})` }, 'alert')
    const events = manager.takeSpeechEvents()
    expect(events).toHaveLength(1)
    expect(manager.activeAlerts()[0].repeatCount).toBe(10)
  })

  it('permite escalar de escudo bajo a sin escudo', () => {
    const manager = new EventManager()
    manager.ingest({ code: 'LOW_SHIELD', title: 'Escudo bajo' }, 'alert')
    manager.takeSpeechEvents()
    manager.ingest({ code: 'SHIELD_EMPTY', title: 'Sin escudo' }, 'alert')
    expect(manager.takeSpeechEvents().map((item) => item.semanticKey)).toEqual(['shield.empty'])
  })

  it('permite reaparecer tras resolución y agrupa salud con riesgo', () => {
    const manager = new EventManager()
    manager.ingest({ code: 'LOW_SHIELD', title: 'Escudo bajo' }, 'alert')
    manager.takeSpeechEvents()
    manager.resolve('shield.low', 'alert')
    manager.ingest({ code: 'LOW_SHIELD', title: 'Te queda poco escudo' }, 'alert')
    expect(manager.takeSpeechEvents()).toHaveLength(1)
    manager.ingest({ code: 'LOW_HEALTH', title: 'Vida baja' }, 'alert')
    manager.ingest({ code: 'HIGH_ELIMINATION_RISK', title: 'Riesgo alto' }, 'alert')
    manager.ingest({ code: 'recommendation.seek_cover', text: 'Busca cobertura' }, 'recommendation')
    expect(manager.takeSpeechEvents()[0].semanticKey).toBe('group.health_risk')
  })

  it('no duplica voz cuando alerta y recomendación comparten semántica', () => {
    const manager = new EventManager()
    manager.ingest({ code: 'LOW_SHIELD', title: 'Escudo bajo' }, 'alert')
    manager.ingest({ code: 'LOW_SHIELD', title: 'Escudo bajo', text: 'Busca protección' }, 'recommendation')
    expect(manager.takeSpeechEvents()).toHaveLength(1)
  })
})
