import { sveltekit } from '@sveltejs/kit/vite';
import adapter from '@sveltejs/adapter-static';
import { defineConfig } from 'vite';

// El backend FastAPI corre en :8000. En dev, /api y /health se reenvían allí (sin CORS).
const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000';

export default defineConfig({
	// MapLibre 6 carga su worker con new URL(import.meta.url): no pre-empaquetar.
	optimizeDeps: { exclude: ['maplibre-gl'] },
	plugins: [sveltekit({ adapter: adapter({ fallback: 'index.html' }) })],
	// 0.0.0.0:8767 → visible en la red local. /api se reenvía al backend, así los
	// demás equipos no necesitan acceso directo a :8000 ni CORS.
	server: { host: '0.0.0.0', port: 8767, strictPort: true, proxy: { '/api': BACKEND, '/health': BACKEND } },
	preview: { host: '0.0.0.0', port: 8767, strictPort: true, proxy: { '/api': BACKEND, '/health': BACKEND } }
});
