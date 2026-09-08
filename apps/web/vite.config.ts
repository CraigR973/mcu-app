/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { sentryVitePlugin } from '@sentry/vite-plugin'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  build: {
    sourcemap: 'hidden',
  },
  plugins: [
    react(),
    VitePWA({
      // `injectManifest`, not `generateSW`: the routing rules in `src/sw.ts` are the
      // batch — a generated worker could not express the poster cache or the API
      // network-first policy without a config that is harder to read than the worker.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      // The worker calls `skipWaiting()` itself, so a new build takes over without
      // waiting to be told — see the comment in `src/sw.ts` for the iOS deadlock this
      // avoids. `autoUpdate` keeps the registration side consistent with that.
      registerType: 'autoUpdate',
      includeAssets: [
        'favicon.svg',
        'apple-touch-icon.png',
        'icon-64.png',
        'icon-128.png',
        'icon-192.png',
        'icon-384.png',
        'icon-512.png',
        'icon-1024.png',
        'placeholder-poster.svg',
      ],
      manifest: {
        name: "Mark's Cinematic Universe",
        short_name: 'The Real MCU',
        description: 'The film collection — what we own, and which shelf it is on.',
        theme_color: '#0B1220',
        background_color: '#0B1220',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/movies',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-384.png', sizes: '384x384', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icon-1024.png', sizes: '1024x1024', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      injectManifest: {
        // The bundle is a single ~560 kB chunk plus lazy routes; the default 2 MiB cap
        // would silently drop it from the precache and leave the shell unavailable
        // offline — the exact thing this batch exists to provide.
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
      devOptions: {
        // Off by default: a service worker caching a dev server's module graph makes
        // every subsequent edit a debugging exercise. Set VITE_PWA_DEV=true to exercise
        // the worker locally.
        enabled: process.env.VITE_PWA_DEV === 'true',
        type: 'module',
      },
    }),
    sentryVitePlugin({
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: process.env.SENTRY_AUTH_TOKEN,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
  },
})
