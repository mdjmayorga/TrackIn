import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { EntradaContrasena } from '@/components/EntradaContrasena'

function Campo({ onEnviar = vi.fn() }: { onEnviar?: () => void }) {
  const [valor, setValor] = useState('')
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onEnviar()
      }}
    >
      <label htmlFor="nueva">Contraseña nueva</label>
      <EntradaContrasena id="nueva" nombre="contraseña nueva" valor={valor} onCambio={setValor} />
    </form>
  )
}

describe('campo de contraseña con el ojo del login', () => {
  it('oculta por omisión y el ojo la muestra y la vuelve a ocultar', async () => {
    render(<Campo />)
    const campo = screen.getByLabelText('Contraseña nueva')
    await userEvent.type(campo, 'una-clave-larga')

    expect(campo).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña nueva' }))
    expect(campo).toHaveAttribute('type', 'text')
    expect(campo).toHaveValue('una-clave-larga')
    const ocultar = screen.getByRole('button', { name: 'Ocultar contraseña nueva' })
    expect(ocultar).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(ocultar)
    expect(campo).toHaveAttribute('type', 'password')
  })

  it('el ojo no envía el formulario', async () => {
    const onEnviar = vi.fn()
    render(<Campo onEnviar={onEnviar} />)

    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña nueva' }))

    expect(onEnviar).not.toHaveBeenCalled()
  })
})
