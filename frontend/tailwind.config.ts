import type { Config } from "tailwindcss";

const config: Config = {
    darkMode: ["class"],
    content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
  	extend: {
  		colors: {
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			},
  			violet: {
  				glow: 'rgba(124, 58, 237, 0.2)',
  			},
  			success: 'var(--success)',
  		},
  		borderRadius: {
  			xl: 'calc(var(--radius) + 8px)',
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		animation: {
  			'pulse-ring': 'pulse-ring 2s ease-out infinite',
  			'waveform': 'waveform 1.2s ease-in-out infinite',
  			'blink-cursor': 'blink-cursor 1s step-end infinite',
  			'slide-in-top': 'slide-in-top 0.4s ease-out forwards',
  			'float-particle': 'float-particle 4s ease-in-out infinite',
  		},
  		keyframes: {
  			'pulse-ring': {
  				'0%': { transform: 'translate(-50%, -50%) scale(1)', opacity: '0.4' },
  				'100%': { transform: 'translate(-50%, -50%) scale(1.4)', opacity: '0' },
  			},
  			'waveform': {
  				'0%, 100%': { height: '12px' },
  				'50%': { height: 'var(--wave-height, 32px)' },
  			},
  			'blink-cursor': {
  				'0%, 100%': { opacity: '1' },
  				'50%': { opacity: '0' },
  			},
  			'slide-in-top': {
  				from: { opacity: '0', transform: 'translateY(-16px)' },
  				to: { opacity: '1', transform: 'translateY(0)' },
  			},
  			'float-particle': {
  				'0%, 100%': { transform: 'translateY(0) translateX(0)', opacity: '0.3' },
  				'25%': { opacity: '0.6' },
  				'50%': { transform: 'translateY(-12px) translateX(4px)', opacity: '0.3' },
  				'75%': { opacity: '0.5' },
  			},
  		},
  	}
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
