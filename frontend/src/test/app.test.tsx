import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('dashboard principal', () => {
  it('muestra identidad, API en tiempo real y áreas esenciales', () => {
    render(<App />)
    expect(screen.getByText('FORTIA')).toBeInTheDocument()
    expect(screen.getByAltText('Logo de FORTIA')).toBeInTheDocument()
    expect(document.querySelector('canvas.particle-background')).toBeInTheDocument()
    expect(screen.getAllByText('API EN TIEMPO REAL').length).toBeGreaterThan(0)
    expect(screen.queryByText('Modo demo')).not.toBeInTheDocument()
    expect(screen.queryByText('Cambiar a API')).not.toBeInTheDocument()
    expect(screen.getByText('Vista de la partida')).toBeInTheDocument()
    expect(screen.getByText('Secuencia de seis frames')).toBeInTheDocument()
  })
})
