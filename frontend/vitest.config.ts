import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    server: {
      deps: {
        inline: [/@csstools\//, /@asamuzakjp\//, /jsdom/],
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@asamuzakjp/css-color': path.resolve(__dirname, './src/test/css-color-stub.cjs'),
    },
  },
});
