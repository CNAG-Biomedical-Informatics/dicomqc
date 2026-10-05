import {defineConfig} from 'vitest/config';
import react from '@vitejs/plugin-react';
import {fileURLToPath} from 'node:url';
export default defineConfig({plugins: [react()], clearScreen: false, build: {target: 'es2022'},
  server: {fs: {allow: [
    fileURLToPath(new URL('.', import.meta.url)),
    fileURLToPath(new URL('../docs-site/static/img/dicomqc-symbol.png', import.meta.url)),
  ]}},
  test: {environment: 'jsdom', clearMocks: true, setupFiles: './src/test/setup.ts', include: ['src/**/*.test.{ts,tsx}']}});
