import { PALETA_ESTADOS } from './src/components/paleta.ts'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Paleta provisional. Ajustar a los colores institucionales de
        // Laboratorios Gutis cuando se definan los lineamientos de marca.
        marca: {
          50: '#eef6ff',
          100: '#d9ebff',
          200: '#bcdcff',
          300: '#8ec7ff',
          400: '#59a8ff',
          500: '#3386fc',
          600: '#1d66f1',
          700: '#1650de',
          800: '#1842b4',
          900: '#1a3b8e',
        },
        // Semáforo de RNF-08: vive en `src/components/paleta.ts`, que también
        // leen los mapas, para que la grilla y los mapas coincidan (`US-24`).
        estado: PALETA_ESTADOS,
        // Superficies del panel oscuro del Figma.
        panel: {
          fondo: '#111317',
          superficie: '#1b1e24',
          cabecera: '#3a3b3e',
          borde: '#3a3f4b',
          mapa: '#2b2c2f',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
