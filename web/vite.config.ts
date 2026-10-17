import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8090' },
  },
  build: { emptyOutDir: false },
  test: { include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'], environment: 'jsdom', setupFiles: ['./tests/setup.ts'] },
});
