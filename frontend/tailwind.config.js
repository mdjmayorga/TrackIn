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
        // Semáforo de estados de pedido (se formaliza en Sprint 1 con Greivin).
        estado: {
          transito: '#3386fc',
          demorado: '#f59e0b',
          critico: '#ef4444',
          entregado: '#10b981',
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
