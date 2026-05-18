import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const devHost = process.env.VITE_DEV_HOST ?? '127.0.0.1';
const apiProxy = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		host: devHost,
		proxy: {
			'/api': {
				target: apiProxy,
				changeOrigin: true
			}
		}
	}
});
