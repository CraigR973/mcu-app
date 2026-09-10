import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
    '../../packages/shared/src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        surface: {
          raised: 'hsl(var(--surface-raised))',
          sunken: 'hsl(var(--surface-sunken))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))',
        },
        info: {
          DEFAULT: 'hsl(var(--info))',
          foreground: 'hsl(var(--info-foreground))',
        },
        brand: {
          ink: 'hsl(var(--brand-ink))',
          cream: 'hsl(var(--brand-cream))',
          burgundy: 'hsl(var(--brand-burgundy))',
          champagne: 'hsl(var(--brand-champagne))',
        },
        quality: {
          '4k': 'hsl(var(--quality-4k))',
          bluray: 'hsl(var(--quality-bluray))',
          dvd: 'hsl(var(--quality-dvd))',
          digital: 'hsl(var(--quality-digital))',
          hdr: 'hsl(var(--quality-hdr))',
          audio: 'hsl(var(--quality-audio))',
        },
      },
      /**
       * Tone colours serve two jobs with different contrast rules: a filled surface
       * (`bg-destructive` under white) and a status word on a page or card
       * (`text-destructive` in an error). One value cannot satisfy both — champagne is
       * legible on ink and invisible on cream; the dark rose that carries a button
       * label falls to 3.1:1 as error text on a dark card.
       *
       * Tailwind keeps `textColor` as its own scale, so `text-*` reads a text-safe
       * variant while `bg-*`, `border-*`, `ring-*` keep the surface value. Every
       * pairing is asserted at >= 4.5:1 in both themes by `theme/contrast.test.ts`.
       * `foreground` is re-declared on each tone so `text-primary-foreground` and its
       * siblings survive the override.
       */
      textColor: {
        primary: {
          DEFAULT: 'hsl(var(--primary-text))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive-text))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        success: {
          DEFAULT: 'hsl(var(--success-text))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning-text))',
          foreground: 'hsl(var(--warning-foreground))',
        },
        info: {
          DEFAULT: 'hsl(var(--info-text))',
          foreground: 'hsl(var(--info-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent-text))',
          foreground: 'hsl(var(--accent-foreground))',
        },
      },
      // The rating star is drawn with both `fill-` and `text-`; keep the two scales
      // agreed so it never renders a champagne body with a bronze rim in light mode.
      fill: {
        accent: 'hsl(var(--accent-text))',
      },
      fontFamily: {
        sans: [
          'ui-sans-serif',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'sans-serif',
        ],
        display: [
          '"Iowan Old Style"',
          '"Baskerville"',
          '"Times New Roman"',
          'serif',
        ],
        mono: ['ui-monospace', '"SFMono-Regular"', 'Menlo', 'Consolas', 'monospace'],
      },
      borderRadius: {
        xl: 'var(--radius-xl)',
        lg: 'var(--radius-lg)',
        md: 'var(--radius-md)',
        sm: 'var(--radius-sm)',
      },
      boxShadow: {
        soft: '0 16px 45px -28px hsl(var(--shadow-colour) / 0.45)',
        lift: '0 18px 50px -24px hsl(var(--shadow-colour) / 0.55)',
      },
    },
  },
  plugins: [],
}

export default config
