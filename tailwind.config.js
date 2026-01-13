/** @type {import('tailwindcss').Config} */
const defaultTheme = require('tailwindcss/defaultTheme');
const colors = require('tailwindcss/colors');

module.exports = {
  // Define the paths to all of your template files so Tailwind can tree-shake unused styles in production
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx}',
  ],

  // Enable dark mode via a class on the HTML element (usually 'dark')
  darkMode: 'class',

  theme: {
    // Overriding screens or container if necessary, otherwise extending
    container: {
      center: true,
      padding: {
        DEFAULT: '1rem',
        sm: '2rem',
        lg: '4rem',
        xl: '5rem',
        '2xl': '6rem',
      },
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      // Extend the default font stack
      fontFamily: {
        sans: ['var(--font-sans)', ...defaultTheme.fontFamily.sans],
        mono: ['var(--font-mono)', ...defaultTheme.fontFamily.mono],
        heading: ['var(--font-heading)', ...defaultTheme.fontFamily.sans],
      },
      
      // Extend colors with semantic naming conventions
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          950: '#082f49',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
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
        success: {
          DEFAULT: '#10b981', // emerald-500
          foreground: '#ffffff',
        },
        warning: {
          DEFAULT: '#f59e0b', // amber-500
          foreground: '#ffffff',
        },
        info: {
          DEFAULT: '#3b82f6', // blue-500
          foreground: '#ffffff',
        },
      },

      // Custom border radius values
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },

      // Custom keyframes for animations
      keyframes: {
        'accordion-down': {
          from: { height: 0 },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: 0 },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'fade-out': {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
        'slide-in-from-top': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        'slide-in-from-bottom': {
          '0%': { transform: 'translateY(100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        'spin-slow': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        shimmer: {
          '100%': {
            transform: 'translateX(100%)',
          },
        },
      },

      // Custom animation utilities
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'fade-in': 'fade-in 0.3s ease-in-out',
        'fade-out': 'fade-out 0.3s ease-in-out',
        'slide-in-top': 'slide-in-from-top 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-bottom': 'slide-in-from-bottom 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'spin-slow': 'spin-slow 3s linear infinite',
        shimmer: 'shimmer 2s infinite',
      },

      // Z-index extension for complex layering
      zIndex: {
        '60': '60',
        '70': '70',
        '80': '80',
        '90': '90',
        '100': '100',
      },

      // Typography customization (requires @tailwindcss/typography)
      typography: (theme) => ({
        DEFAULT: {
          css: {
            maxWidth: '65ch',
            color: theme('colors.foreground'),
            '[class~="lead"]': {
              color: theme('colors.muted.foreground'),
            },
            a: {
              color: theme('colors.primary.DEFAULT'),
              textDecoration: 'underline',
              fontWeight: '500',
              '&:hover': {
                color: theme('colors.primary.600'),
              },
            },
            strong: {
              color: theme('colors.foreground'),
              fontWeight: '600',
            },
            'ol > li::marker': {
              color: theme('colors.muted.foreground'),
            },
            'ul > li::marker': {
              color: theme('colors.muted.foreground'),
            },
            hr: {
              borderColor: theme('colors.border'),
            },
            blockquote: {
              borderLeftColor: theme('colors.border'),
              color: theme('colors.muted.foreground'),
            },
            h1: {
              color: theme('colors.foreground'),
              fontWeight: '800',
            },
            h2: {
              color: theme('colors.foreground'),
              fontWeight: '700',
            },
            h3: {
              color: theme('colors.foreground'),
              fontWeight: '600',
            },
            h4: {
              color: theme('colors.foreground'),
              fontWeight: '600',
            },
            code: {
              color: theme('colors.foreground'),
              backgroundColor: theme('colors.muted.DEFAULT'),
              paddingLeft: '0.25rem',
              paddingRight: '0.25rem',
              paddingTop: '0.125rem',
              paddingBottom: '0.125rem',
              borderRadius: '0.25rem',
              fontWeight: '400',
            },
            'code::before': {
              content: '""',
            },
            'code::after': {
              content: '""',
            },
            pre: {
              backgroundColor: theme('colors.secondary.900'),
              color: theme('colors.secondary.50'),
            },
          },
        },
        dark: {
          css: {
            color: theme('colors.secondary.100'),
            a: {
              color: theme('colors.primary.400'),
              '&:hover': {
                color: theme('colors.primary.300'),
              },
            },
            h1: {
              color: theme('colors.secondary.50'),
            },
            h2: {
              color: theme('colors.secondary.50'),
            },
            h3: {
              color: theme('colors.secondary.50'),
            },
            h4: {
              color: theme('colors.secondary.50'),
            },
            hr: {
              borderColor: theme('colors.secondary.700'),
            },
            blockquote: {
              borderLeftColor: theme('colors.secondary.700'),
              color: theme('colors.secondary.300'),
            },
          },
        },
      }),
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('@tailwindcss/aspect-ratio'),
    require('tailwindcss-animate'), // Useful for Radix UI primitives
    
    // Custom plugin for adding utility classes
    function ({ addUtilities }) {
      const newUtilities = {
        '.text-shadow': {
          textShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
        },
        '.text-shadow-md': {
          textShadow: '0 4px 8px rgba(0, 0, 0, 0.12), 0 2px 4px rgba(0, 0, 0, 0.08)',
        },
        '.text-shadow-lg': {
          textShadow: '0 15px 30px rgba(0, 0, 0, 0.11), 0 5px 15px rgba(0, 0, 0, 0.08)',
        },
        '.text-shadow-none': {
          textShadow: 'none',
        },
      };
      addUtilities(newUtilities);
    },
  ],
};
