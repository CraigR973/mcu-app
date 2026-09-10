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
      // The approved identity, installed from the design system by
      // `scripts/brand-sync.mjs`. Precached because an installed PWA that cannot draw its
      // own icon offline is worse than one that cannot draw a poster. The interface marks
      // and lockups are here too: the login screen and the app shell both render one
      // before any network request completes.
      includeAssets: [
        'brand/favicon.ico',
        'brand/apple-touch-icon.png',
        'brand/app-icon-concept-art-192.png',
        'brand/app-icon-concept-art-384.png',
        'brand/app-icon-concept-art-512.png',
        'brand/app-icon-concept-art-maskable-192.png',
        'brand/app-icon-concept-art-maskable-512.png',
        'brand/notification-badge-96.png',
        'brand/social-card-1200x630.png',
        'brand/stack-mark.svg',
        'brand/stack-mark-light.svg',
        'brand/stack-mark-compact.svg',
        'brand/stack-mark-compact-light.svg',
        'brand/micro-mark-16.svg',
        'brand/horizontal-lockup-dark.svg',
        'brand/horizontal-lockup-light.svg',
        'brand/stacked-lockup-dark.svg',
        'brand/stacked-lockup-light.svg',
        'placeholder-poster.svg',
      ],
      manifest: {
        name: "Mark's Cinematic Universe",
        short_name: 'The Real MCU',
        description: 'The film collection — what we own, and which shelf it is on.',
        // The interface's own dark background. `#0B1220` was the placeholder identity's
        // blue and appeared nowhere in the shipped theme, so an installed app opened on a
        // splash colour the app never draws.
        theme_color: '#120F0D',
        background_color: '#120F0D',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/movies',
        // `any` and `maskable` are separate entries on purpose: a maskable icon holds its
        // artwork inside a 72% safe area, so a platform that used it unmasked would draw
        // the emblem small in a field of ink. Declaring one icon as both makes every
        // launcher guess.
        icons: [
          { src: '/brand/app-icon-concept-art-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/brand/app-icon-concept-art-384.png', sizes: '384x384', type: 'image/png', purpose: 'any' },
          { src: '/brand/app-icon-concept-art-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/brand/app-icon-concept-art-maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: '/brand/app-icon-concept-art-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
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
