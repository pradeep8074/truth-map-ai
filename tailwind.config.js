/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#0B1220',
          secondary: '#111B2E',
          surface: '#172338',
          surfaceHover: '#1E2D47',
          surfaceActive: '#243654',
          accent: '#3B82F6',
          accentHover: '#2563EB',
          teal: '#14B8A6',
          tealHover: '#0D9488',
          text: '#F8FAFC',
          textMuted: '#94A3B8',
          textDim: '#64748B',
          border: '#263449',
          borderHighlight: '#3B82F6',
        },
        dark: {
          950: '#060B14',
          900: '#0B1220',
          850: '#0E1726',
          800: '#111B2E',
          750: '#172338',
          700: '#1E2D47',
          600: '#2A3C5B',
        },
        background: '#0B1220',
        foreground: '#F8FAFC',
        muted: {
          DEFAULT: '#111B2E',
          foreground: '#94A3B8',
        },
        status: {
          supported: {
            DEFAULT: '#22C55E',
            bg: 'rgba(34, 197, 94, 0.1)',
            border: 'rgba(34, 197, 94, 0.25)',
          },
          conflict: {
            DEFAULT: '#EF4444',
            bg: 'rgba(239, 68, 68, 0.1)',
            border: 'rgba(239, 68, 68, 0.25)',
          },
          gap: {
            DEFAULT: '#F59E0B',
            bg: 'rgba(245, 158, 11, 0.1)',
            border: 'rgba(245, 158, 11, 0.25)',
          },
          unverified: {
            DEFAULT: '#94A3B8',
            bg: 'rgba(148, 163, 184, 0.1)',
            border: 'rgba(148, 163, 184, 0.25)',
          },
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          '"JetBrains Mono"',
          '"Fira Code"',
          'Menlo',
          'monospace',
        ],
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.35)',
        'elevated': '0 4px 20px -2px rgba(5, 10, 20, 0.7)',
        'modal': '0 20px 40px -15px rgba(0, 0, 0, 0.8)',
        'glow-blue': '0 0 20px -5px rgba(59, 130, 246, 0.3)',
        'glow-teal': '0 0 20px -5px rgba(20, 184, 166, 0.3)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-down': 'slideDown 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
