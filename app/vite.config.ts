import {defineConfig} from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins: [react()], clearScreen: false, build: {target: 'es2022'},
  test: {environment: 'jsdom', clearMocks: true, include: ['src/**/*.test.{ts,tsx}']}});
