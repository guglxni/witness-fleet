import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], root: 'toolchain-smoke', build: { outDir: '../toolchain-dist', emptyOutDir: true } });
