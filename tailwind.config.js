/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.html",
    "./apps/**/*.py",
    "./config/**/*.py",
    "./dev_tools/**/*.py",
    "./static/**/*.js",
  ],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: '#FFFFFF',
      paper: {
        DEFAULT: '#F8F5EE',
        deep: '#F0EBDD',
      },
      card: '#FFFFFF',
      line: '#E4DECF',
      ink: {
        DEFAULT: '#141B34',
        muted: '#566074',
      },
      brand: {
        DEFAULT: '#1F45C4',
        hover: '#17369F',
        tint: '#E6ECFB',
      },
      saffron: '#F2A900',
      pine: {
        DEFAULT: '#0E7C5A',
        dark: '#0A5C43',
        tint: '#DDF1E8',
      },
      amber: {
        text: '#9A5B00',
        tint: '#FFF0D1',
      },
      brick: {
        DEFAULT: '#B42318',
        tint: '#FDE7E4',
      },
      // Token Ubin Ilustrasi Placeholder (AGENT.md 5A revisi - Khusus ubin ilustrasi)
      tile: {
        blue: '#8EA8F7',
        saffron: '#FFD66B',
        mint: '#7ACFAC',
        coral: '#FFA68C',
      },
      // Token Ornamen Budaya (FASE 7F - HANYA sebagai latar panel ornamen momen budaya)
      'marun-tapis': '#5B1A24',
    },
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        heading: ['"Bricolage Grotesque"', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(20, 27, 52, 0.08)',
        float: '0 1px 2px rgba(20, 27, 52, 0.08)',
      },
      screens: {
        'xs': '360px',
        'phone': '390px',
        'sm': '640px',
        'md': '768px',
        'lg': '1024px',
        'xl': '1280px',
      },
    },
  },
  plugins: [],
  safelist: [
    'h-40',
    'h-44',
    'h-52',
    'sm:h-52',
    'lg:h-44',
    'min-h-[160px]',
    'max-h-[220px]',
    'h-[160px]',
    'h-[180px]',
    'h-[200px]',
    'h-[300px]',
    'md:h-[300px]',
  ],
}
