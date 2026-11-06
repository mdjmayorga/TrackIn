/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// La versión del panel es la del package.json, la misma que la del backend
// (`PROD-06`; una prueba del backend verifica que coincidan).
const paquete = JSON.parse(
  readFileSync(fileURLToPath(new URL('./package.json', import.meta.url)), 'utf-8'),
) as { version: string }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  define: {
    __APP_VERSION__: JSON.stringify(paquete.version),
  },

  resolve: {
    alias: {
      // Permite `import { api } from '@/services/api'` en vez de '../../services/api'.
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    port: 5173,
    // host: true escucha en 0.0.0.0, necesario para que el puerto publicado
    // del contenedor sea alcanzable desde el host.
    host: true,
    strictPort: true,
    watch: {
      // Los eventos de filesystem no cruzan bien el límite Windows/contenedor.
      usePolling: process.env.CHOKIDAR_USEPOLLING === 'true',
    },
  },

  preview: {
    port: 4173,
    host: true,
  },

  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    include: ['tests/**/*.{test,spec}.{ts,tsx}', 'src/**/*.{test,spec}.{ts,tsx}'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/**/*.d.ts'],
      // La Definition of Done exige 70 %. Con el umbral aquí, `npm run
      // test:coverage` falla si se baja de ese mínimo (TASK-05).
      thresholds: {
        statements: 70,
        branches: 70,
        functions: 70,
        lines: 70,
      },
    },
  },
})
