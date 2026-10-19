import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  base: '/demo/',
  plugins: [react()],
  publicDir: 'public',
  build: {
    outDir: '../src/witness_fleet/hosting/static',
    emptyOutDir: false,
    assetsDir: 'assets',
  },
  resolve: { alias: { '@': resolve(fileURLToPath(new URL('.', import.meta.url)), 'src') } },
  test: {
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
  },
});
