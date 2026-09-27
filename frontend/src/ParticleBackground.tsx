import { useEffect, useRef } from 'react'

type Particle = { x: number; y: number; radius: number; alpha: number; speedX: number; speedY: number; interactionX: number; interactionY: number; color: string; highlighted: boolean }

const colors = ['#22d3ee', '#3b82f6', '#8b5cf6', '#2ce5a7', '#d9f7ff']
const diagnosticsEnabled = false
const pointerConfig = { enabled: true, radius: 150, force: 0.16, friction: 0.94, recovery: 0.08, lineGlow: 0.03 }

export default function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    let context: CanvasRenderingContext2D | null = null
    try { context = canvas.getContext('2d') } catch { return }
    if (!context) return

    let animationFrame = 0
    let particles: Particle[] = []
    let width = 0
    let height = 0
    const motionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    let reducedMotion = motionQuery?.matches ?? false
    let frameCount = 0
    let fps = 0
    let fpsTimestamp = performance.now()
    const pointer = { x: 0, y: 0, active: false, pointerType: 'mouse' }

    const createParticles = () => {
      // Duplica exactamente la densidad anterior: clamp(round(área / 13000) × 2, 100, 360).
      const viewportArea = width * height
      const count = Math.max(200, Math.min(720, Math.round(viewportArea / 13000) * 4))
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        radius: Math.random() < 0.16 ? 3 + Math.random() : 1.5 + Math.random() * 1.5,
        alpha: Math.random() < 0.16 ? 0.55 + Math.random() * 0.2 : 0.35 + Math.random() * 0.3,
        speedX: (Math.random() - 0.5) * 0.1,
        speedY: (Math.random() - 0.5) * 0.08,
        interactionX: 0,
        interactionY: 0,
        color: colors[Math.floor(Math.random() * colors.length)],
        highlighted: Math.random() < 0.16,
      }))
    }

    const drawConnections = () => {
      const maxDistance = Math.min(180, Math.max(120, width * 0.12))
      const cellSize = maxDistance
      const grid = new Map<string, number[]>()
      const candidates: Array<{ from: number; to: number; distance: number }> = []
      const lineColors = ['rgba(34, 211, 238, ', 'rgba(59, 130, 246, ', 'rgba(139, 92, 246, ', 'rgba(44, 229, 167, ']

      for (let index = 0; index < particles.length; index += 1) {
        const cellX = Math.floor(particles[index].x / cellSize)
        const cellY = Math.floor(particles[index].y / cellSize)
        const key = `${cellX}:${cellY}`
        const cell = grid.get(key)
        if (cell) cell.push(index)
        else grid.set(key, [index])
      }

      for (let from = 0; from < particles.length; from += 1) {
        const cellX = Math.floor(particles[from].x / cellSize)
        const cellY = Math.floor(particles[from].y / cellSize)
        for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
          for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
            const neighbors = grid.get(`${cellX + offsetX}:${cellY + offsetY}`)
            if (!neighbors) continue
            for (const to of neighbors) {
              if (to <= from) continue
              const dx = particles[from].x - particles[to].x
              const dy = particles[from].y - particles[to].y
              const distance = Math.hypot(dx, dy)
              if (distance < maxDistance) candidates.push({ from, to, distance })
            }
          }
        }
      }
      candidates.sort((a, b) => a.distance - b.distance)
      const connections = new Array(particles.length).fill(0) as number[]
      for (const connection of candidates) {
        if (connections[connection.from] >= 2 || connections[connection.to] >= 2) continue
        const proximity = 1 - connection.distance / maxDistance
        const currentStrength = Math.min(0.28, (0.05 + proximity * 0.08) * 2)
        const midpointX = (particles[connection.from].x + particles[connection.to].x) / 2
        const midpointY = (particles[connection.from].y + particles[connection.to].y) / 2
        const cursorDistance = pointer.active ? Math.hypot(midpointX - pointer.x, midpointY - pointer.y) : pointerConfig.radius
        const cursorGlow = cursorDistance < pointerConfig.radius ? (1 - cursorDistance / pointerConfig.radius) * pointerConfig.lineGlow : 0
        const strength = Math.min(0.6, currentStrength * 2 + cursorGlow)
        context.beginPath()
        context.strokeStyle = `${lineColors[connection.from % lineColors.length]}${strength})`
        context.lineWidth = Math.min(2, (0.7 + proximity * 0.3) * 2)
        context.moveTo(particles[connection.from].x, particles[connection.from].y)
        context.lineTo(particles[connection.to].x, particles[connection.to].y)
        context.stroke()
        connections[connection.from] += 1
        connections[connection.to] += 1
      }
    }

    const draw = () => {
      context.clearRect(0, 0, width, height)
      context.globalAlpha = 1
      drawConnections()
      for (const particle of particles) {
        context.beginPath()
        context.fillStyle = particle.color
        context.globalAlpha = particle.alpha
        context.shadowBlur = particle.highlighted ? 8 : 0
        context.shadowColor = particle.color
        context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2)
        context.fill()
      }
      context.shadowBlur = 0
      context.globalAlpha = 1
      if (diagnosticsEnabled) {
        frameCount += 1
        const now = performance.now()
        if (now - fpsTimestamp >= 1000) { fps = frameCount; frameCount = 0; fpsTimestamp = now }
        context.strokeStyle = 'rgba(34, 211, 238, .35)'
        context.strokeRect(0, 0, width, height)
        context.fillStyle = '#d9f7ff'
        context.font = '12px monospace'
        context.fillText(`particles: ${particles.length} · viewport: ${width}×${height} · fps: ${fps} · reduced: ${reducedMotion}`, 12, 20)
      }
      if (reducedMotion || document.hidden) return
      for (const particle of particles) {
        let targetX = 0
        let targetY = 0
        if (pointerConfig.enabled && pointer.active) {
          const dx = particle.x - pointer.x
          const dy = particle.y - pointer.y
          const distance = Math.hypot(dx, dy)
          if (distance > 0 && distance < pointerConfig.radius) {
            const falloff = 1 - distance / pointerConfig.radius
            const force = pointerConfig.force * falloff * falloff
            targetX = dx / distance * force
            targetY = dy / distance * force
          }
        }
        particle.interactionX += (targetX - particle.interactionX) * pointerConfig.recovery
        particle.interactionY += (targetY - particle.interactionY) * pointerConfig.recovery
        particle.interactionX *= pointerConfig.friction
        particle.interactionY *= pointerConfig.friction
        particle.x += particle.speedX + particle.interactionX
        particle.y += particle.speedY + particle.interactionY
        if (particle.x < -8) particle.x = width + 8
        if (particle.x > width + 8) particle.x = -8
        if (particle.y < -8) particle.y = height + 8
        if (particle.y > height + 8) particle.y = -8
      }
      animationFrame = window.requestAnimationFrame(draw)
    }

    const resize = () => {
      window.cancelAnimationFrame(animationFrame)
      animationFrame = 0
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5)
      width = window.innerWidth
      height = window.innerHeight
      canvas.width = Math.floor(width * ratio)
      canvas.height = Math.floor(height * ratio)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      createParticles()
      draw()
    }

    const handleVisibility = () => {
      if (document.hidden) {
        window.cancelAnimationFrame(animationFrame)
        animationFrame = 0
      } else if (!reducedMotion && !animationFrame) {
        animationFrame = window.requestAnimationFrame(draw)
      }
    }

    const handleMotionChange = (event: MediaQueryListEvent) => {
      reducedMotion = event.matches
      window.cancelAnimationFrame(animationFrame)
      animationFrame = 0
      draw()
    }

    const handlePointerMove = (event: PointerEvent) => {
      if (event.pointerType === 'touch' && event.buttons === 0) return
      pointer.x = event.clientX
      pointer.y = event.clientY
      pointer.pointerType = event.pointerType || 'mouse'
      pointer.active = true
    }
    const clearPointer = () => { pointer.active = false }

    resize()
    window.addEventListener('resize', resize, { passive: true })
    window.addEventListener('pointermove', handlePointerMove, { passive: true })
    window.addEventListener('pointerup', clearPointer, { passive: true })
    window.addEventListener('pointercancel', clearPointer, { passive: true })
    window.addEventListener('blur', clearPointer)
    document.addEventListener('mouseleave', clearPointer)
    document.addEventListener('visibilitychange', handleVisibility)
    motionQuery?.addEventListener('change', handleMotionChange)

    return () => {
      window.cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', clearPointer)
      window.removeEventListener('pointercancel', clearPointer)
      window.removeEventListener('blur', clearPointer)
      document.removeEventListener('mouseleave', clearPointer)
      document.removeEventListener('visibilitychange', handleVisibility)
      motionQuery?.removeEventListener('change', handleMotionChange)
      context.clearRect(0, 0, width, height)
    }
  }, [])

  return <canvas ref={canvasRef} className='particle-background' aria-hidden='true' />
}
