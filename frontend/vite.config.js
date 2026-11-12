import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Browser requests go to localhost:5173/api, and Vite forwards them to Flask.
// No Flask CORS changes are needed for local course demonstrations.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
});
