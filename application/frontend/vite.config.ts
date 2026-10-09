import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/** Build the React client with same-origin local API routing; proxy failures surface in the UI. */
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } } },
});
