import tailwindcss from '@tailwindcss/postcss';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

const repositoryBasePath = '/matchbridge-creator-selection-agent/';

export default defineConfig({
  root: 'pages',
  base: repositoryBasePath,
  publicDir: '../public',
  build: {
    outDir: '../dist-pages',
    emptyOutDir: true,
  },
  css: { postcss: { plugins: [tailwindcss()] } },
  define: {
    'process.env.NEXT_PUBLIC_API_BASE_URL': JSON.stringify(''),
    'process.env.NEXT_PUBLIC_DEMO_MODE': JSON.stringify('true'),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./', import.meta.url)),
    },
  },
  plugins: [react()],
});
