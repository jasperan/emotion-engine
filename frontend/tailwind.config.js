/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			fontFamily: {
				sans: ['DM Sans', 'system-ui', 'sans-serif'],
				display: ['Fraunces', 'Georgia', 'serif'],
				mono: ['JetBrains Mono', 'monospace']
			},
			colors: {
				storm: {
					50: '#f0f3f8',
					100: '#dfe5ef',
					200: '#c5cedf',
					300: '#9ba8c4',
					400: '#7080a8',
					500: '#53608c',
					600: '#3f4a75',
					700: '#353d64',
					800: '#2a3050',
					900: '#262a42',
					950: '#171a2e'
				},
				flood: {
					50: '#effbfc',
					100: '#d6f4f7',
					200: '#b2e8ef',
					300: '#7dd6e3',
					400: '#40bace',
					500: '#249eb3',
					600: '#218097',
					700: '#21677b',
					800: '#235565',
					900: '#214856',
					950: '#102e3a'
				},
				background: '#0e0f14',
				surface: '#181a22',
				surface_alt: '#22252e',
				primary: '#8fb4e0',
				on_primary: '#0a2a4a',
				on_background: '#e2e2e6',
				on_surface: '#a8aab8',
				outline: '#3a3d48',
				accent: {
					blue: '#8fb4e0',
					purple: '#b8a6d9',
					teal: '#5cd4c4'
				}
			},
			backgroundImage: {
				'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
				'subtle-glow': 'conic-gradient(from 180deg at 50% 50%, #181a2200 0deg, #8fb4e008 180deg, #181a2200 360deg)',
			},
			borderRadius: {
				'2xl': '1rem',
				'3xl': '1.25rem',
			}
		}
	},
	plugins: []
};
